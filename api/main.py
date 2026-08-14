"""
RealEstateAI API - 增强版
提供城市房源查询、价格预测、文本分析等功能
"""
import sys, os, re, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from dotenv import load_dotenv

# 加载项目根目录的 .env 配置文件（含国内镜像 HF_ENDPOINT，加速模型加载）
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, distinct

from utils.constants import ALL_CITIES, SUPPORTED_LAYOUTS, SUPPORTED_FLOORS, SUPPORTED_DECORATIONS, SUPPORTED_ORIENTATIONS, build_feature_cols
from utils.database import SessionLocal, House, CityIndex, init_db, migrate_db
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    # 启动阶段：预热所有模型，加载完成前 uvicorn 不会对外提供服务
    print("🔄 正在预热模型（趋势预测 + NLP 引擎）...")
    try:
        get_trend_predictor()
    except Exception as e:
        print(f"⚠️ 趋势模型预热失败: {e}")
    try:
        get_nlp_analyzer()
    except Exception as e:
        print(f"⚠️ NLP 引擎预热失败: {e}")
    # 价格模型较大，预热但不阻塞主流程太久；首次请求时也会懒加载
    try:
        get_price_model()
    except Exception as e:
        print(f"⚠️ 价格模型预热失败: {e}")
    print("✅ 模型预热完成，服务就绪")
    yield
    # 关闭阶段（可选清理）
    print("👋 后端正在关闭")


app = FastAPI(title="RealEstateAI API", version="2.0", description="智能房产数据分析平台", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
init_db()
migrate_db()

# 全局模型实例（延迟加载）
trend_predictor = None
nlp_analyzer = None

def get_trend_predictor():
    global trend_predictor
    if trend_predictor is None:
        try:
            from models.trend_predictor import TrendPredictor
            trend_predictor = TrendPredictor.load_model()
            if trend_predictor is None:
                trend_predictor = TrendPredictor()
                trend_predictor.fit_all_cities()
                trend_predictor.save_model()
            print("✅ 趋势预测模型已加载")
        except Exception as e:
            print(f"⚠️ 趋势预测模型加载失败: {e}")
            trend_predictor = None
    return trend_predictor

def get_nlp_analyzer():
    global nlp_analyzer
    if nlp_analyzer is None:
        try:
            # 惰性导入：仅在该分析器首次被请求时才加载 torch/sentence_transformers，
            # 避免后端主流程（价格/趋势/房源/指数）被沉重的 NLP 依赖拖垮。
            # 若 torchvision 与 torch 版本不匹配导致加载失败，仅 NLP 接口降级，
            # 不影响其它接口。
            from nlp_module.ai_analyzer import AIRealEstateAnalyzer
            nlp_analyzer = AIRealEstateAnalyzer()
            print("✅ NLP分析器已加载")
        except Exception as e:
            print(f"⚠️ NLP分析器加载失败（NLP 接口将不可用，核心功能不受影响）: {e}")
            nlp_analyzer = None
    return nlp_analyzer

# 价格预测模型（xgb + rf 融合），延迟加载
price_model = None

def get_price_model():
    global price_model
    if price_model is None:
        try:
            import joblib
            MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
            xgb = joblib.load(os.path.join(MODEL_DIR, 'xgb_model.pkl'))
            rf = joblib.load(os.path.join(MODEL_DIR, 'rf_model.pkl'))
            blend = joblib.load(os.path.join(MODEL_DIR, 'blend_model.pkl'))
            scaler = joblib.load(os.path.join(MODEL_DIR, 'scaler.pkl'))
            feature_cols = joblib.load(os.path.join(MODEL_DIR, 'feature_cols.pkl'))
            price_model = {
                'xgb': xgb, 'rf': rf, 'blend': blend,
                'scaler': scaler, 'feature_cols': feature_cols,
            }
            print("✅ 价格预测模型已加载")
        except Exception as e:
            print(f"⚠️ 价格预测模型加载失败: {e}")
            price_model = None
    return price_model

# ==================== 数据模型 ====================

class TextAnalysisRequest(BaseModel):
    text: str

class ListingFuturePredictRequest(BaseModel):
    city: str
    current_price: float
    area: float = 100.0
    future_years: int = 5

# ==================== 健康检查 ====================

@app.get("/health")
def health():
    models_loaded = {
        "trend_predictor": trend_predictor is not None,
        "price_model": price_model is not None,
    }
    nlp_ok = nlp_analyzer is not None
    ready = nlp_ok and models_loaded["trend_predictor"] and models_loaded["price_model"]
    status = "ok" if ready else "loading"
    return {"status": status, "models_loaded": models_loaded, "nlp_engine": nlp_ok}


# ==================== 全局数据 API ====================

@app.get("/api/cities")
def get_cities(
    property_type: str | None = Query(None, description="房源类型：二手房 / 新房；不传则返回全部")
):
    """获取所有城市列表及统计信息（可按房源类型过滤）"""
    db = SessionLocal()
    try:
        query = db.query(
            House.city,
            func.count(House.id).label('count'),
            func.avg(House.price).label('avg_price'),
            func.min(House.price).label('min_price'),
            func.max(House.price).label('max_price')
        )
        if property_type:
            pt_col = getattr(House, 'property_type', None)
            if pt_col is not None:
                query = query.filter(pt_col == property_type)
        cities = query.group_by(House.city).all()

        result_cities = []
        for c in cities:
            result_cities.append({
                "name": c.city,
                "count": c.count,
                "avg_price": round(float(c.avg_price), 2) if c.avg_price else None,
                "min_price": round(float(c.min_price), 2) if c.min_price else None,
                "max_price": round(float(c.max_price), 2) if c.max_price else None,
            })
        # 按记录数降序，方便前端展示
        result_cities.sort(key=lambda x: x['count'], reverse=True)

        return {
            "cities": result_cities,
            "total_cities": len(result_cities),
            "property_type": property_type,
        }
    finally:
        db.close()


def _house_to_dict(h):
    return {
        "id": h.id, "title": h.title, "city": h.city,
        "region": getattr(h, 'region', None),
        "community": getattr(h, 'community', None),
        "price": float(h.price) if h.price else None,
        "unit_price": float(h.unit_price) if h.unit_price else None,
        "area": float(h.area) if h.area else None,
        "rooms": getattr(h, 'rooms', None),
        "floor_info": getattr(h, 'floor_info', None),
        "orientation": getattr(h, 'orientation', None),
        "decoration": getattr(h, 'decoration', None),
        "year": h.year,
        "building_year": getattr(h, 'building_year', None),
        "property_type": getattr(h, 'property_type', None),
        "description": getattr(h, 'description', None),
        "url": h.url,
        "crawled_at": str(getattr(h, 'crawled_at', None) or getattr(h, 'created_at', None)),
    }


@app.get("/api/cities/{city}/listings")
def get_city_listings(
    city: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("price", pattern="^(price|unit_price|area|year)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    min_price: float | None = None,
    max_price: float | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    region: str | None = None,
    property_type: str = Query("二手房", description="房源类型：二手房 / 新房"),
):
    """获取指定城市的房源列表（分页、排序、筛选），可按房源类型过滤"""
    db = SessionLocal()
    try:
        query = db.query(House).filter(House.city == city)
        pt_col = getattr(House, 'property_type', None)
        if pt_col is not None:
            query = query.filter(pt_col == property_type)
        
        if min_price is not None:
            query = query.filter(House.price >= min_price)
        if max_price is not None:
            query = query.filter(House.price <= max_price)
        if min_area is not None:
            query = query.filter(House.area >= min_area)
        if max_area is not None:
            query = query.filter(House.area <= max_area)
        if region:
            region_col = getattr(House, 'region', None)
            if region_col is not None:
                query = query.filter(region_col.ilike(f'%{region}%'))
        
        total = query.count()
        
        sort_col = getattr(House, sort_by)
        if sort_order == 'desc':
            query = query.order_by(sort_col.desc().nullslast())
        else:
            query = query.order_by(sort_col.asc().nullslast())
        
        houses = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return {
            "data": [_house_to_dict(h) for h in houses],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, -(-total // page_size))
        }
    finally:
        db.close()


@app.get("/api/cities/{city}/stats")
def get_city_stats(city: str, property_type: str = Query("二手房", description="房源类型：二手房 / 新房")):
    """获取城市房源统计信息（可按房源类型过滤）"""
    db = SessionLocal()
    try:
        base = db.query(House).filter(House.city == city)
        pt_col = getattr(House, 'property_type', None)
        if pt_col is not None:
            base = base.filter(pt_col == property_type)
        total = base.count()
        
        price_stats = db.query(
            func.avg(House.price).label('avg_price'),
            func.min(House.price).label('min_price'),
            func.max(House.price).label('max_price'),
            func.avg(House.unit_price).label('avg_unit_price'),
            func.avg(House.area).label('avg_area'),
        ).filter(House.city == city)
        if pt_col is not None:
            price_stats = price_stats.filter(pt_col == property_type)
        price_stats = price_stats.first()
        
        region_col = getattr(House, 'region', None)
        rooms_col = getattr(House, 'rooms', None)
        decoration_col = getattr(House, 'decoration', None)
        pt_filter = (pt_col == property_type) if pt_col is not None else None

        regions = []
        if region_col is not None:
            q = db.query(region_col, func.count(House.id).label('cnt')).filter(House.city == city)
            if pt_filter is not None:
                q = q.filter(pt_filter)
            regions = q.group_by(region_col).order_by(func.count(House.id).desc()).all()

        room_dist = []
        if rooms_col is not None:
            q = db.query(rooms_col, func.count(House.id).label('cnt')).filter(House.city == city)
            if pt_filter is not None:
                q = q.filter(pt_filter)
            room_dist = q.group_by(rooms_col).order_by(func.count(House.id).desc()).all()

        q = db.query(House.year, func.count(House.id).label('cnt')).filter(House.city == city)
        if pt_filter is not None:
            q = q.filter(pt_filter)
        year_dist = q.group_by(House.year).order_by(House.year).all()

        deco_dist = []
        if decoration_col is not None:
            q = db.query(decoration_col, func.count(House.id).label('cnt')).filter(House.city == city)
            if pt_filter is not None:
                q = q.filter(pt_filter)
            deco_dist = q.group_by(decoration_col).all()
        
        return {
            "city": city,
            "total_listings": total,
            "avg_price": round(float(price_stats.avg_price), 2) if price_stats.avg_price else None,
            "min_price": round(float(price_stats.min_price), 2) if price_stats.min_price else None,
            "max_price": round(float(price_stats.max_price), 2) if price_stats.max_price else None,
            "avg_unit_price": round(float(price_stats.avg_unit_price), 2) if price_stats.avg_unit_price else None,
            "avg_area": round(float(price_stats.avg_area), 2) if price_stats.avg_area else None,
            "region_distribution": [{"region": str(r[0]), "count": r[1]} for r in regions if r[0]],
            "room_distribution": [{"rooms": str(r[0]), "count": r[1]} for r in room_dist if r[0]],
            "year_distribution": [{"year": r[0], "count": r[1]} for r in year_dist if r[0]],
            "decoration_distribution": [{"type": str(d[0]), "count": d[1]} for d in deco_dist if d[0]],
        }
    finally:
        db.close()


@app.get("/api/listings/{listing_id}")
def get_listing_detail(listing_id: int):
    """获取单个房源详情"""
    db = SessionLocal()
    try:
        h = db.query(House).filter(House.id == listing_id).first()
        if not h:
            raise HTTPException(status_code=404, detail="房源不存在")
        
        result = _house_to_dict(h)
        
        community = getattr(h, 'community', None)
        result["same_community"] = []
        if community:
            same = db.query(House).filter(
                getattr(House, 'community', None) == community,
                House.id != h.id
            ).limit(10).all()
            result["same_community"] = [
                {"id": s.id, "title": s.title, "price": float(s.price) if s.price else None,
                 "area": float(s.area) if s.area else None, "rooms": getattr(s, 'rooms', None)}
                for s in same
            ]
        
        return result
    finally:
        db.close()


# ==================== 新房 / 二手房指数 API ====================
# 数据源：国家统计局 70 城房价指数（city_index 表）。
# 新房页使用官方指数（商品住宅价格指数），因其挂牌价≠成交价、受政策影响大，
# 房源级新房价格失真；官方指数基于真实成交，最适合政策/走势分析。

@app.get("/api/index/cities")
def get_index_cities():
    """返回 70 城指数覆盖的城市及其时间范围（新房/二手房指数）。"""
    db = SessionLocal()
    try:
        rows = db.query(
            CityIndex.city,
            func.min(CityIndex.year), func.max(CityIndex.year),
            func.count(CityIndex.id),
        ).group_by(CityIndex.city).order_by(func.count(CityIndex.id).desc()).all()
        return {
            "cities": [
                {"name": r[0], "min_year": r[1], "max_year": r[2], "count": r[3]}
                for r in rows
            ],
            "total": len(rows),
        }
    finally:
        db.close()


@app.get("/api/index/city/{city}")
def get_city_index(
    city: str,
    base_type: str = Query("同比", pattern="^(同比|环比)$"),
):
    """返回某城市的房价指数月度序列（新房/二手房，含各面积段）。"""
    db = SessionLocal()
    try:
        rows = db.query(
            CityIndex.year, CityIndex.month, CityIndex.date_str,
            CityIndex.commodity_idx, CityIndex.secondhand_idx, CityIndex.resident_idx,
            CityIndex.commodity_below90, CityIndex.commodity_144, CityIndex.commodity_above144,
            CityIndex.secondhand_below90, CityIndex.secondhand_144, CityIndex.secondhand_above144,
        ).filter(CityIndex.city == city, CityIndex.base_type == base_type).order_by(
            CityIndex.year, CityIndex.month
        ).all()

        series = [{
            "year": r.year, "month": r.month, "date": r.date_str,
            "commodity_idx": r.commodity_idx,        # 新房（商品住宅）价格指数
            "secondhand_idx": r.secondhand_idx,      # 二手房价格指数
            "resident_idx": r.resident_idx,          # 二手住宅（总）
            "commodity_below90": r.commodity_below90,
            "commodity_144": r.commodity_144,
            "commodity_above144": r.commodity_above144,
            "secondhand_below90": r.secondhand_below90,
            "secondhand_144": r.secondhand_144,
            "secondhand_above144": r.secondhand_above144,
        } for r in rows]

        meta = db.query(
            func.min(CityIndex.year), func.max(CityIndex.year), func.count(CityIndex.id)
        ).filter(CityIndex.city == city, CityIndex.base_type == base_type).first()

        return {
            "city": city,
            "base_type": base_type,
            "date_range": {"min_year": meta[0], "max_year": meta[1], "count": meta[2]},
            "series": series,
        }
    finally:
        db.close()


@app.get("/api/index/compare")
def compare_index(
    cities: str = Query(..., description="逗号分隔城市名，如 北京,上海,深圳"),
    base_type: str = Query("同比", pattern="^(同比|环比)$"),
    metric: str = Query("commodity_idx", pattern="^(commodity_idx|secondhand_idx|resident_idx)$"),
):
    """多城市指数对比（跨城新房/二手房走势）。"""
    db = SessionLocal()
    try:
        city_list = [c.strip() for c in cities.split(",") if c.strip()]
        metric_col = getattr(CityIndex, metric)
        series = {}
        for city in city_list:
            rows = db.query(
                CityIndex.year, CityIndex.month, metric_col
            ).filter(
                CityIndex.city == city, CityIndex.base_type == base_type
            ).order_by(CityIndex.year, CityIndex.month).all()
            series[city] = [{"year": y, "month": m, "value": v} for (y, m, v) in rows]
        return {"base_type": base_type, "metric": metric, "series": series}
    finally:
        db.close()


# ==================== 价格预测 API ====================

@app.post("/api/predict/price")
def predict_price(features: dict):
    """给定房源特征，返回 AI 预测总价（万元）。特征格式与 Dashboard 调用一致。"""
    model = get_price_model()
    if model is None:
        raise HTTPException(status_code=503, detail="价格预测模型未就绪")
    try:
        import numpy as np
        feature_cols = model['feature_cols']
        # 兼容前端传 building_year，需换算 house_age = year - building_year
        row = {}
        for col in feature_cols:
            row[col] = features.get(col, 0.0)
        if 'house_age' in feature_cols:
            yr = features.get('year', 2020)
            by = features.get('building_year', 2000)
            try:
                yr = int(yr); by = int(by)
            except Exception:
                yr, by = 2020, 2000
            row['house_age'] = yr - by
        # 装修/朝向：前端传原始字符串，这里转为与训练一致的独热编码
        dec_raw = features.get('decoration')
        for d in SUPPORTED_DECORATIONS:
            if f'dec_{d}' in feature_cols:
                row[f'dec_{d}'] = 1.0 if dec_raw == d else 0.0
        ori_raw = features.get('orientation')
        for o in SUPPORTED_ORIENTATIONS:
            if f'ori_{o}' in feature_cols:
                row[f'ori_{o}'] = 1.0 if ori_raw == o else 0.0
        X = np.array([[row[c] for c in feature_cols]], dtype=float)
        # 用带列名的 DataFrame 传入 scaler，避免 "X does not have valid feature names" 警告
        import pandas as pd
        X_df = pd.DataFrame(X, columns=feature_cols)
        Xs = model['scaler'].transform(X_df)
        xgb_p = model['xgb'].predict(Xs)
        rf_p = model['rf'].predict(Xs)
        blend_X = np.column_stack((xgb_p, rf_p))
        pred_unit = float(model['blend'].predict(blend_X)[0])  # 模型预测单价（元/㎡）
        area = features.get('area') or 0
        total_wan = (pred_unit * float(area) / 10000.0) if area and float(area) > 0 else None
        return {
            "predicted_unit_price": round(pred_unit, 0),
            "predicted_price": round(total_wan, 2) if total_wan is not None else None,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"预测失败: {e}")


# ==================== 趋势预测 API ====================

@app.get("/api/predict/city_trend/{city}")
def predict_city_trend(city: str, future_years: int = Query(5, ge=1, le=20)):
    """预测城市未来N年平均房价趋势"""
    predictor = get_trend_predictor()
    if predictor is None:
        raise HTTPException(status_code=503, detail="趋势预测模型未就绪")
    result = predictor.predict_future(city, future_years)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    return result


@app.post("/api/predict/listing_future")
def predict_listing_future(req: ListingFuturePredictRequest):
    """预测指定房源未来的价格趋势"""
    predictor = get_trend_predictor()
    if predictor is None:
        raise HTTPException(status_code=503, detail="趋势预测模型未就绪")
    result = predictor.predict_listing_future(
        req.city, req.current_price, req.area, req.future_years
    )
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    return result


# ==================== NLP 分析 API ====================

@app.post("/api/analyze/text")
def analyze_text(req: TextAnalysisRequest):
    """综合分析房产描述文本"""
    analyzer = get_nlp_analyzer()
    if analyzer is None:
        raise HTTPException(status_code=503, detail="NLP引擎未就绪")
    return analyzer.comprehensive_analysis(req.text)


@app.post("/api/analyze/listing/{listing_id}")
def analyze_listing(listing_id: int):
    """分析指定房源的描述文本"""
    db = SessionLocal()
    try:
        h = db.query(House).filter(House.id == listing_id).first()
        if not h:
            raise HTTPException(status_code=404, detail="房源不存在")
        desc = getattr(h, 'description', None)
        if not desc:
            return {"error": "该房源无描述文本", "listing_id": listing_id, "title": h.title}
        
        analyzer = get_nlp_analyzer()
        if analyzer is None:
            raise HTTPException(status_code=503, detail="NLP引擎未就绪")
        analysis = analyzer.comprehensive_analysis(desc)
        
        return {
            "listing_id": h.id,
            "title": h.title,
            "city": h.city,
            "price": float(h.price) if h.price else None,
            "analysis": analysis
        }
    finally:
        db.close()


# ==================== 统计/仪表盘 API ====================

@app.get("/api/dashboard/overview")
def dashboard_overview():
    """仪表盘总览数据"""
    db = SessionLocal()
    try:
        total = db.query(func.count(House.id)).scalar()
        city_count = db.query(func.count(distinct(House.city))).scalar()
        avg_price = db.query(func.avg(House.price)).scalar()
        avg_unit = db.query(func.avg(House.unit_price)).scalar()
        avg_area_val = db.query(func.avg(House.area)).scalar()
        
        city_prices = db.query(
            House.city, func.avg(House.price).label('avg_price'),
            func.count(House.id).label('cnt')
        ).group_by(House.city).order_by(func.avg(House.price).desc()).limit(10).all()
        
        decoration_col = getattr(House, 'decoration', None)
        deco_dist = []
        if decoration_col is not None:
            deco_dist = db.query(
                decoration_col, func.count(House.id).label('cnt')
            ).group_by(decoration_col).order_by(func.count(House.id).desc()).all()
        
        region_col = getattr(House, 'region', None)
        price_area_data = db.query(
            House.price, House.area, House.city, region_col
        ).filter(House.price > 0, House.area > 0).limit(5000).all()
        
        return {
            "summary": {
                "total_listings": total,
                "cities_count": city_count,
                "avg_price": round(float(avg_price), 2) if avg_price else None,
                "avg_unit_price": round(float(avg_unit), 2) if avg_unit else None,
                "avg_area": round(float(avg_area_val), 2) if avg_area_val else None,
            },
            "city_price_ranking": [
                {"city": c.city, "avg_price": round(float(c.avg_price), 2), "count": c.cnt}
                for c in city_prices
            ],
            "decoration_distribution": [
                {"type": str(d[0]) or "未知", "count": d[1]} for d in deco_dist
            ],
            "price_area_scatter": [
                {"price": float(r[0]), "area": float(r[1]), "city": r[2], "region": str(r[3]) if r[3] else "未知"}
                for r in price_area_data if r[0] and r[1]
            ]
        }
    finally:
        db.close()


@app.get("/api/dashboard/yearly_trend")
def yearly_trend():
    """年份房价走势。

    房源覆盖多年的城市直接用真实成交均价；只覆盖单一年份的城市
    （如上海仅有 2022 年成交明细），以该年真实均价为锚点，用国家
    统计局 70 城二手住宅同比指数折算历年真实价格水平。
    两类数据来源通过 data_sources 字段标明。
    """
    # 局部导入，避免模块加载时即引入 sklearn 等重依赖
    from models.trend_predictor import TrendPredictor

    db = SessionLocal()
    try:
        # 样本量过少的年份均价不具统计意义，与趋势模型保持一致的过滤口径
        min_samples = TrendPredictor.min_year_samples
        data = db.query(
            House.year, House.city,
            func.avg(House.price).label('avg_price'),
            func.count(House.id).label('cnt')
        ).filter(House.year > 0).group_by(
            House.year, House.city
        ).having(func.count(House.id) >= min_samples).order_by(House.year).all()
        
        result = {}
        for row in data:
            if row.city not in result:
                result[row.city] = []
            result[row.city].append({
                "year": row.year,
                "avg_price": round(float(row.avg_price), 2),
                "count": row.cnt
            })

        # 单年城市用官方指数折算补全历年走势
        sources = {}
        predictor = get_trend_predictor()
        for city, series in list(result.items()):
            if len(series) >= 2:
                sources[city] = "真实成交"
                continue
            # 单年城市：尝试用官方指数折算补全历年走势；
            # 既无多年成交、也无指数数据的，如实标注为单年真实快照
            if predictor is None or len(series) == 0:
                sources[city] = "真实成交（单年）"
                continue
            anchor = series[0]
            adjusted = predictor.index_adjusted_series(
                city, anchor["year"], anchor["avg_price"]
            )
            if len(adjusted) >= 2:
                result[city] = [
                    {
                        "year": item["year"],
                        "avg_price": item["price"],
                        "count": anchor["count"] if item["year"] == anchor["year"] else None
                    }
                    for item in adjusted
                ]
                sources[city] = "官方指数折算"
            else:
                # 本城无官方指数，尝试邻城指数代理补全历年走势
                nb_series, nb = predictor.neighbor_index_adjusted_series(
                    city, anchor["year"], anchor["avg_price"]
                )
                if len(nb_series) >= 2:
                    result[city] = [
                        {
                            "year": item["year"],
                            "avg_price": item["price"],
                            "count": anchor["count"] if item["year"] == anchor["year"] else None
                        }
                        for item in nb_series
                    ]
                    sources[city] = "邻城指数代理"
                else:
                    sources[city] = "真实成交（单年）"

        return {"yearly_trends": result, "data_sources": sources}
    finally:
        db.close()


# ==================== 配置接口 ====================

@app.get("/api/config/predict")
def get_predict_config():
    """返回价格预测所需的特征配置（城市、户型、楼层），前端无需硬编码"""
    return {
        "cities": ALL_CITIES,
        "layouts": SUPPORTED_LAYOUTS,
        "floors": SUPPORTED_FLOORS,
        "decorations": SUPPORTED_DECORATIONS,
        "orientations": SUPPORTED_ORIENTATIONS,
        "source": "utils/constants.py",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
