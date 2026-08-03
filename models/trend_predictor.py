"""
时间序列趋势预测模型
基于城市历史均价数据，拟合价格趋势并进行未来预测
使用多项式回归 + 线性回归组合方法
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from utils.database import SessionLocal, House
import joblib
from datetime import datetime

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

class TrendPredictor:
    """城市房价趋势预测器"""
    
    def __init__(self):
        self.city_models = {}  # {city: {'model': LinearRegression, 'poly': PolynomialFeatures, 'avg_prices': [...]}}
        self.poly_degree = 2   # 二次多项式拟合趋势
    
    def fit_city(self, city: str):
        """为指定城市训练趋势预测模型"""
        db = SessionLocal()
        try:
            df = pd.read_sql(
                db.query(House).filter(House.city == city).statement,
                db.bind
            )
        finally:
            db.close()
        
        if df.empty:
            return None
        
        # 按年份计算均价
        yearly_avg = df.groupby('year')['price'].mean().reset_index()
        yearly_avg = yearly_avg.sort_values('year')
        
        if len(yearly_avg) < 2:
            return None
        
        years = yearly_avg['year'].values.reshape(-1, 1)
        prices = yearly_avg['price'].values
        
        # 多项式特征 + 线性回归
        poly = PolynomialFeatures(degree=self.poly_degree)
        X_poly = poly.fit_transform(years.astype(float))
        
        model = LinearRegression()
        model.fit(X_poly, prices)
        
        self.city_models[city] = {
            'model': model,
            'poly': poly,
            'years': years.flatten().tolist(),
            'prices': prices.tolist(),
            'avg_prices': yearly_avg.to_dict('records')
        }
        
        return {
            'city': city,
            'historical_years': len(yearly_avg),
            'latest_avg_price': float(prices[-1]),
            'r2_score': model.score(X_poly, prices)
        }
    
    def predict_future(self, city: str, future_years: int = 5) -> dict:
        """预测城市未来N年价格趋势"""
        if city not in self.city_models:
            result = self.fit_city(city)
            if result is None:
                return {'error': f'城市 {city} 数据不足，无法预测'}
        
        model_info = self.city_models[city]
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
        
        return {
            'city': city,
            'predictions': [
                {'year': yr, 'predicted_price': round(float(pred), 2), 'yoy_growth': growth_rates[i]}
                for i, (yr, pred) in enumerate(zip(years_to_predict, predictions))
            ],
            'historical': model_info['avg_prices'],
            'model_type': 'polynomial_regression',
            'confidence': 'medium'
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
