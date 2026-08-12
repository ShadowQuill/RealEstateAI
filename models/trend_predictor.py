"""
时间序列趋势预测模型
基于城市历史均价数据，拟合价格趋势并进行未来预测
使用多项式回归 + 线性回归组合方法

数据来源分三类，均为真实数据，不使用任何合成房源：
1. 真实成交：城市房源覆盖多个年份时，直接按年聚合真实成交均价（如北京 2010-2018）。
2. 官方指数折算：城市房源仅覆盖单一年份且该城在统计局 70 城样本内时，
   以该年真实成交均价为锚点，用国家统计局 70 城二手住宅价格
   同比指数链式折算出历年真实价格水平。
3. 邻城指数代理：城市房源仅覆盖单一年份且本城不在 70 城样本内（如中山、
   东莞、苏州等），则借用同城市群、走势高度相关的邻近大城市官方同比指数
   作为涨跌幅，以本城单年真实均价为锚点链式折算出历年价格水平。
   方向由真实官方指数驱动，但绝对价格水平是缩放近似，故置信度低于前两类。

样本量少于 min_year_samples 的年份均价不具统计意义，不参与拟合。
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sqlalchemy import func
from utils.database import SessionLocal, House, CityIndex
import joblib
from datetime import datetime

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

SOURCE_REAL_DEAL = '真实成交'
SOURCE_INDEX_ADJUSTED = '官方指数折算'
SOURCE_NEIGHBOR_INDEX = '邻城指数代理'
SOURCE_REAL_DEAL_SINGLE = '真实成交（单年）'

# 单年城市 -> 邻近大城市（均在 CityIndex 官方指数表中，同城市群、走势相关）。
# 本城不在 70 城样本内时，借用邻城官方同比指数代为折算历年价格水平。
NEIGHBOR_MAP = {
    '中山': ['广州', '深圳'],
    '东莞': ['广州', '深圳'],
    '佛山': ['广州', '深圳'],
    '珠海': ['广州', '深圳'],
    '苏州': ['上海', '南京'],
    '南通': ['上海', '南京'],
    '嘉兴': ['上海', '杭州'],
    '昆山': ['上海'],
    '保定': ['北京', '石家庄'],
    '廊坊': ['北京'],
    '绍兴': ['杭州', '宁波'],
    '芜湖': ['南京', '合肥'],
    '镇江': ['南京'],
    '潍坊': ['青岛', '济南'],
    '泰州': ['南京', '上海'],
}


class TrendPredictor:
    """城市房价趋势预测器"""

    # 类属性：定义在类上，使旧版本反序列化得到的实例
    # （__dict__ 中没有这些字段）也能正常取值。
    fit_window = 10        # 指数折算序列的最近年数窗口
    min_year_samples = 30  # 年度均价参与趋势拟合所需的最小成交样本数

    def __init__(self):
        self.city_models = {}  # {city: {'model': LinearRegression, 'poly': PolynomialFeatures, 'avg_prices': [...]}}
        self.poly_degree = 2   # 二次多项式拟合趋势
    
    def _yearly_yoy_index(self, city: str):
        """取城市二手住宅同比指数的年度序列 {year: yoy}。

        同比指数以上年同月为 100，按每年最后一个可得月份取值，
        即 yoy[y] 表示 y 年末价格水平相对 y-1 年末的百分比。
        """
        db = SessionLocal()
        try:
            rows = db.query(
                CityIndex.year, CityIndex.month, CityIndex.secondhand_idx
            ).filter(
                CityIndex.city == city,
                CityIndex.base_type == '同比',
                CityIndex.secondhand_idx.isnot(None)
            ).order_by(CityIndex.year, CityIndex.month).all()
        finally:
            db.close()

        # 同年多月，保留月份最大的一条
        yoy = {}
        for year, month, idx in rows:
            if year is None or idx is None:
                continue
            prev = yoy.get(year)
            if prev is None or month > prev[0]:
                yoy[year] = (month, float(idx))
        return {y: v[1] for y, v in yoy.items()}

    def index_adjusted_series(self, city: str, anchor_year: int, anchor_price: float):
        """以锚点年真实均价为基准，用官方同比指数链式折算历年均价。

        向前：price[y-1] = price[y] / (yoy[y] / 100)
        向后：price[y]   = price[y-1] * (yoy[y] / 100)

        统计局指数是质量调整后的同质可比价格，链式累乘年数过多会
        低估名义涨幅，因此回溯范围限制在最近 fit_window 年内。
        """
        yoy = self._yearly_yoy_index(city)
        if not yoy:
            return []

        latest = max(yoy)
        window_start = max(min(yoy), latest - self.fit_window + 1)
        window_start = min(window_start, anchor_year)

        series = {anchor_year: float(anchor_price)}

        # 向前回溯至窗口下界
        year = anchor_year
        while (year in yoy) and (year - 1 >= window_start):
            ratio = yoy[year] / 100.0
            if ratio <= 0:
                break
            series[year - 1] = series[year] / ratio
            year -= 1

        # 向后推算至最新可得年份
        year = anchor_year + 1
        while year in yoy:
            ratio = yoy[year] / 100.0
            if ratio <= 0:
                break
            series[year] = series[year - 1] * ratio
            year += 1

        return [{'year': y, 'price': round(series[y], 2)} for y in sorted(series)]

    def neighbor_index_adjusted_series(self, city: str, anchor_year: int, anchor_price: float):
        """本城无官方指数时，借用邻近大城市官方同比指数链式折算历年均价。

        以本城单年真实均价为锚点，遍历 NEIGHBOR_MAP 中的邻城，取首个
        在 CityIndex 中有同比指数数据的邻城，用其历年涨跌幅回溯/推算本城
        价格水平。返回 (series, neighbor_city)，无可用邻城时返回 ([], None)。
        """
        for nb in NEIGHBOR_MAP.get(city, []):
            yoy = self._yearly_yoy_index(nb)
            if not yoy:
                continue
            latest = max(yoy)
            window_start = max(min(yoy), latest - self.fit_window + 1)
            window_start = min(window_start, anchor_year)

            series = {anchor_year: float(anchor_price)}
            # 向前回溯至窗口下界
            year = anchor_year
            while year in yoy and year - 1 >= window_start:
                ratio = yoy[year] / 100.0
                if ratio <= 0:
                    break
                series[year - 1] = series[year] / ratio
                year -= 1
            # 向后推算至最新可得年份
            year = anchor_year + 1
            while year in yoy:
                ratio = yoy[year] / 100.0
                if ratio <= 0:
                    break
                series[year] = series[year - 1] * ratio
                year += 1

            if len(series) >= 2:
                return [{'year': y, 'price': round(series[y], 2)} for y in sorted(series)], nb
        return [], None

    def fit_city(self, city: str):
        """为指定城市训练趋势预测模型"""
        db = SessionLocal()
        try:
            # 样本量过少的年份（个别数据集早年只有一两条记录）均价不具
            # 统计意义，会扭曲趋势拟合，故排除
            rows = db.query(
                House.year, func.avg(House.price)
            ).filter(
                House.city == city, House.year > 0
            ).group_by(House.year).having(
                func.count(House.id) >= self.min_year_samples
            ).order_by(House.year).all()
        finally:
            db.close()

        yearly_avg = [
            {'year': int(y), 'price': round(float(p), 2)}
            for y, p in rows if y is not None and p is not None
        ]
        if not yearly_avg:
            return None

        data_source = SOURCE_REAL_DEAL
        full_series = yearly_avg
        anchor_year = yearly_avg[-1]['year']
        single_year = False
        neighbor_city = None

        if len(yearly_avg) < 2:
            # 房源仅覆盖单一年份，先尝试用本城官方同比指数折算历年真实价格水平
            full_series = self.index_adjusted_series(
                city, anchor_year, yearly_avg[0]['price']
            )
            if len(full_series) >= 2:
                data_source = SOURCE_INDEX_ADJUSTED
            else:
                # 本城无官方指数（如中山、东莞等不在 70 城样本的城市），
                # 尝试用邻近大城市的官方同比指数代为折算历年价格水平
                nb_series, nb = self.neighbor_index_adjusted_series(
                    city, anchor_year, yearly_avg[0]['price']
                )
                if len(nb_series) >= 2:
                    full_series = nb_series
                    data_source = SOURCE_NEIGHBOR_INDEX
                    neighbor_city = nb
                else:
                    # 既无多年真实成交、也无（本城/邻城）指数可折算：保留单年
                    # 真实快照，不拟合趋势（趋势模型需 ≥2 个数据点），由 predict
                    # 阶段给出持平预测
                    full_series = yearly_avg
                    data_source = SOURCE_REAL_DEAL_SINGLE
                    single_year = True

        if single_year:
            self.city_models[city] = {
                'model': None,
                'poly': None,
                'years': [anchor_year],
                'prices': [float(yearly_avg[0]['price'])],
                'avg_prices': full_series,
                'data_source': data_source,
                'anchor_year': anchor_year,
                'neighbor_city': neighbor_city,
                'fit_year_range': [anchor_year, anchor_year],
                'single_year': True,
            }
            return {
                'city': city,
                'historical_years': 1,
                'latest_avg_price': float(yearly_avg[0]['price']),
                'data_source': data_source,
                'neighbor_city': neighbor_city,
                'r2_score': None,
                'single_year': True,
            }

        years = np.array([r['year'] for r in full_series], dtype=float).reshape(-1, 1)
        prices = np.array([r['price'] for r in full_series], dtype=float)
        
        # 多项式特征 + 线性回归
        poly = PolynomialFeatures(degree=self.poly_degree)
        X_poly = poly.fit_transform(years)
        
        model = LinearRegression()
        model.fit(X_poly, prices)
        
        self.city_models[city] = {
            'model': model,
            'poly': poly,
            'years': years.flatten().astype(int).tolist(),
            'prices': prices.tolist(),
            'avg_prices': full_series,
            'data_source': data_source,
            'anchor_year': anchor_year,
            'neighbor_city': neighbor_city,
            'fit_year_range': [int(years[0][0]), int(years[-1][0])]
        }
        
        return {
            'city': city,
            'historical_years': len(full_series),
            'latest_avg_price': float(prices[-1]),
            'data_source': data_source,
            'neighbor_city': neighbor_city,
            'r2_score': model.score(X_poly, prices)
        }
    
    def predict_future(self, city: str, future_years: int = 5) -> dict:
        """预测城市未来N年价格趋势"""
        if city not in self.city_models:
            result = self.fit_city(city)
            if result is None:
                return {'error': f'城市 {city} 数据不足，无法预测'}
        
        model_info = self.city_models[city]

        if model_info.get('single_year'):
            # 单年真实快照：无趋势可拟合，按当年真实均价持平给出预测并明确提示
            anchor_price = model_info['prices'][0]
            current_year = datetime.now().year
            years_to_predict = list(range(current_year + 1, current_year + future_years + 1))
            predictions = [
                {'year': yr, 'predicted_price': round(float(anchor_price), 2), 'yoy_growth': 0.0}
                for yr in years_to_predict
            ]
            return {
                'city': city,
                'predictions': predictions,
                'historical': model_info['avg_prices'],
                'model_type': 'single_year_snapshot',
                'data_source': model_info['data_source'],
                'anchor_year': model_info['anchor_year'],
                'fit_year_range': model_info['fit_year_range'],
                'confidence': 'none',
                'single_year': True,
                'note': (f'该城市仅有{model_info["anchor_year"]}年单年真实成交快照'
                         f'（约30套在售房源），缺乏多年历史成交数据，无法拟合趋势，'
                         f'预测值按当年真实均价持平给出，未使用任何模拟数据。')
            }

        model = model_info['model']
        poly = model_info['poly']
        
        current_year = datetime.now().year
        years_to_predict = list(range(current_year + 1, current_year + future_years + 1))
        
        X_future = np.array(years_to_predict).reshape(-1, 1).astype(float)
        X_future_poly = poly.transform(X_future)
        predictions = model.predict(X_future_poly)
        
        # 计算年化增长率
        growth_rates = []
        for i, yr in enumerate(years_to_predict):
            if i == 0:
                prev_price = model_info['prices'][-1]
            else:
                prev_price = predictions[i-1]
            rate = (predictions[i] - prev_price) / prev_price * 100
            growth_rates.append(round(rate, 2))
        
        data_source = model_info.get('data_source', SOURCE_REAL_DEAL)
        return {
            'city': city,
            'predictions': [
                {'year': yr, 'predicted_price': round(float(pred), 2), 'yoy_growth': growth_rates[i]}
                for i, (yr, pred) in enumerate(zip(years_to_predict, predictions))
            ],
            'historical': model_info['avg_prices'],
            'model_type': 'polynomial_regression',
            'data_source': data_source,
            'anchor_year': model_info.get('anchor_year'),
            'neighbor_city': model_info.get('neighbor_city'),
            'fit_year_range': model_info.get('fit_year_range'),
            'confidence': 'medium' if data_source == SOURCE_REAL_DEAL else 'low'
        }
    
    def predict_listing_future(self, city: str, current_price: float, area: float, 
                               future_years: int = 5) -> dict:
        """基于城市趋势 + 当前房源价格，预测该房源未来价格"""
        city_trend = self.predict_future(city, future_years)
        if 'error' in city_trend:
            return city_trend
        
        # 用城市趋势的增长率应用到当前房源价格
        predictions = city_trend['predictions']
        listing_predictions = []
        running_price = current_price
        
        for pred in predictions:
            growth_rate = pred['yoy_growth'] / 100
            running_price = running_price * (1 + growth_rate)
            listing_predictions.append({
                'year': pred['year'],
                'predicted_price': round(running_price, 2),
                'yoy_growth': pred['yoy_growth']
            })
        
        return {
            'city': city,
            'current_price': current_price,
            'area': area,
            'predictions': listing_predictions,
            'city_trend': city_trend,
            'total_growth': round((listing_predictions[-1]['predicted_price'] / current_price - 1) * 100, 2)
        }
    
    def fit_all_cities(self):
        """训练所有有数据的城市"""
        from utils.database import SessionLocal, House
        from sqlalchemy import distinct, func
        
        db = SessionLocal()
        try:
            cities = [row[0] for row in db.query(distinct(House.city)).all()]
        finally:
            db.close()
        
        results = {}
        for city in cities:
            res = self.fit_city(city)
            if res:
                results[city] = res
        return results
    
    def save_model(self):
        """保存趋势预测器"""
        filepath = os.path.join(MODEL_DIR, 'trend_predictor.pkl')
        joblib.dump(self, filepath)
        print(f"✅ 趋势预测模型已保存至 {filepath}")
        return filepath
    
    @staticmethod
    def load_model():
        """加载趋势预测器"""
        filepath = os.path.join(MODEL_DIR, 'trend_predictor.pkl')
        if os.path.exists(filepath):
            return joblib.load(filepath)
        return None


if __name__ == "__main__":
    predictor = TrendPredictor()
    predictor.fit_all_cities()
    predictor.save_model()
    
    # 测试预测
    result = predictor.predict_future('北京', 5)
    print(f"北京未来5年预测:", result)
    
    listing_pred = predictor.predict_listing_future('北京', 500, 89, 5)
    print(f"北京某房源500万/89平 未来预测:", listing_pred)
