# api/main.py
import sys
import os

# 加载项目根目录的 .env 配置文件
from dotenv import load_dotenv
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

sys.path.append(BASE_DIR)
from nlp_module.ai_analyzer import AIRealEstateAnalyzer
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

app = FastAPI(
    title="🏡 中国城市房地产AI分析平台",
    description="本接口提供基于机器学习的房价预测、文本信息提取等功能。",
    version="1.0.0",
    contact={
        "name": "hefeiyu",
        "email": "1340863075@qq.com",
    },
    # 🔽 直接禁用 ReDoc
    redoc_url=None
)

# 加载模型和特征工具
nlp_engine = AIRealEstateAnalyzer()
xgb = joblib.load(os.path.join(BASE_DIR, 'models/xgb_model.pkl'))
rf = joblib.load(os.path.join(BASE_DIR, 'models/rf_model.pkl'))
blend = joblib.load(os.path.join(BASE_DIR, 'models/blend_model.pkl'))
scaler = joblib.load(os.path.join(BASE_DIR, 'models/scaler.pkl'))
feature_cols = joblib.load(os.path.join(BASE_DIR, 'models/feature_cols.pkl'))


# api/main.py 中修改 HouseInput 和校验器
class HouseInput(BaseModel):
    year: int = Field(2026, description="交易年份（支持未来5年）")
    area: float = Field(80.0, description="面积")
    building_year: int = Field(2010, description="建成年份")
    # 一线城市
    city_北京: int = Field(0)
    city_上海: int = Field(0)
    city_广州: int = Field(0)
    city_深圳: int = Field(0)
    # 新一线城市
    city_成都: int = Field(0)
    city_重庆: int = Field(0)
    city_杭州: int = Field(0)
    city_武汉: int = Field(0)
    city_天津: int = Field(0)
    city_苏州: int = Field(0)
    city_南京: int = Field(0)
    city_西安: int = Field(0)
    city_郑州: int = Field(0)
    city_长沙: int = Field(0)
    city_合肥: int = Field(0)
    city_青岛: int = Field(0)
    city_东莞: int = Field(0)
    city_佛山: int = Field(0)
    city_宁波: int = Field(0)
    # 重要二线城市
    city_大连: int = Field(0)
    city_沈阳: int = Field(0)
    city_济南: int = Field(0)
    city_昆明: int = Field(0)
    city_厦门: int = Field(0)
    city_福州: int = Field(0)
    city_无锡: int = Field(0)
    city_珠海: int = Field(0)
    city_哈尔滨: int = Field(0)
    city_南宁: int = Field(0)
    # 户型 & 楼层
    layout_2室1厅: int = Field(0)
    layout_3室1厅: int = Field(0)
    layout_3室2厅: int = Field(0)
    floor_info_低楼层: int = Field(0)
    floor_info_中楼层: int = Field(0)
    floor_info_高楼层: int = Field(0)

    model_config = {"extra": "forbid"}

    @model_validator(mode='after')
    def check_rules(self):
        """
        对输入数据进行一些规则检查，如年份、面积、城市、户型、楼层等。
        """
        current_year = datetime.now().year
        if not (1900 <= self.year <= current_year + 5):
            raise ValueError(f"年份必须在1900~{current_year+5}之间，当前{self.year}")
        if self.area <= 0:
            raise ValueError("面积必须>0")
        if not (1900 <= self.building_year < self.year):
            raise ValueError(f"建成年份必须<{self.year}且>=1900")

        # 城市互斥检查（动态获取所有city_开头的字段）
        city_fields = [f for f in self.model_fields if f.startswith('city_')]
        city_sum = sum(getattr(self, f) for f in city_fields)
        if city_sum != 1:
            raise ValueError("必须且只能选择一个城市")
        layout_sum = sum(getattr(self, f) for f in ['layout_2室1厅','layout_3室1厅','layout_3室2厅'])
        if layout_sum != 1:
            raise ValueError("必须且只能选择一个户型")
        floor_sum = sum(getattr(self, f) for f in ['floor_info_低楼层','floor_info_中楼层','floor_info_高楼层'])
        if floor_sum != 1:
            raise ValueError("必须且只能选择一个楼层")
        return self

@app.post(
    "/predict",
    summary="二手房总价智能预测",
    description=""" 
    **使用说明**：  
    1. 请输入房屋的面积和建成年份。    
    2. 户型与楼层特征请使用 **独热编码** (One-Hot)，即只能有一个相关字段为 1，其余为 0。（是为1，否为0）    
    3. 该模型融合了 XGBoost 和随机森林算法。  
    """,
    response_description="返回预测的总价（单位：万元）"
)
def predict_price(house: HouseInput):
    try:
        # 将输入转为DataFrame并填充缺失特征
        input_dict = house.model_dump()
        df = pd.DataFrame([input_dict])
        # 计算房龄（与训练时的特征工程保持一致）
        df['house_age'] = df['year'] - df['building_year']
        # 确保特征列顺序一致
        for col in feature_cols:
            if col not in df.columns:
                df[col] = 0
        X = df[feature_cols]
        X_scaled = scaler.transform(X)

        # 融合预测
        xgb_pred = xgb.predict(X_scaled)[0]
        rf_pred = rf.predict(X_scaled)[0]
        final_pred = blend.predict([[xgb_pred, rf_pred]])[0]

        return {"predicted_price": round(final_pred, 2), "unit": "万元"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/analyze/text",
    summary="分析房产文本：提取成交价 + 检测虚假宣传",
    description=""" 
    **使用说明**：  
    1. 请输入相关文本    
    """,
    response_description="返回从文本中提取出的成交价格（单位：万元），无则为null以及虚假宣传风险检测结果"
)
async def analyze_text(text: str):
    """
    分析房产文本：提取成交价 + 检测虚假宣传
    """
    price = nlp_engine.extract_deal_price(text)
    risk = nlp_engine.detect_fake_promotion(text)
    return {
        "extracted_price": price,
        "fraud_risk": risk
    }


# 在加载完所有模型后
@app.get("/health", summary="健康检查（含模型状态）")
def health_check():
    """返回模型加载状态，用于启动脚本检测"""
    models_loaded = {
        "xgb": xgb is not None,
        "rf": rf is not None,
        "blend": blend is not None,
        "scaler": scaler is not None,
        "feature_cols": feature_cols is not None,
    }
    nlp_ok = nlp_engine is not None
    # 所有模型和NLP引擎都加载成功才算ok
    all_ok = all(models_loaded.values()) and nlp_ok
    return {
        "status": "ok" if all_ok else "error",
        "models_loaded": models_loaded,
        "nlp_engine": nlp_ok
    }


@app.get("/", summary="检查服务是否活着")
def root():
    return {"message": "🏠 房地产AI平台已启动，请访问 /docs 查看接口文档"}


if __name__ == "__main__":
    import uvicorn
    _host = os.environ.get('API_HOST', '127.0.0.1')
    _port = int(os.environ.get('API_PORT', '8000'))
    uvicorn.run(app, host=_host, port=_port, workers=1)