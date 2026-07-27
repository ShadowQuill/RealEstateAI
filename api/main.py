# api/main.py
from nlp_module.ai_analyzer import AIRealEstateAnalyzer
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator
import joblib
import numpy as np
import pandas as pd
import sys
import os
from datetime import datetime  # 新增，用于获取当前年份

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


class HouseInput(BaseModel):
    # 基础字段（带默认值，但校验会强制必须填写有效数据）
    area: float = Field(0.0, description="房屋建筑面积（单位：平方米）")
    building_year: int = Field(2000, description="房屋建成年份（如 2015）")

    # 户型独热编码字段
    layout_2室1厅: int = Field(0, description="是否2室1厅（是为1，否为0）")
    layout_3室1厅: int = Field(0, description="是否3室1厅（是为1，否为0）")
    layout_3室2厅: int = Field(0, description="是否3室2厅（是为1，否为0）")

    # 楼层独热编码字段
    floor_info_低楼层: int = Field(0, description="是否低楼层（是为1，否为0）")
    floor_info_中楼层: int = Field(0, description="是否中楼层（是为1，否为0）")
    floor_info_高楼层: int = Field(0, description="是否高楼层（是为1，否为0）")

    # 禁止额外字段
    model_config = {"extra": "forbid"}

    # ------------------- 自定义校验器（在全部字段赋值后执行） -------------------
    @model_validator(mode='after')
    def check_all_rules(self):
        # 1. 面积必须大于0
        if self.area <= 0:
            raise ValueError(f"房屋面积必须大于0，当前为 {self.area}")

        # 2. 建成年份必须在 1900 到 去年 之间
        current_year = datetime.now().year
        if not (1900 <= self.building_year < current_year):
            raise ValueError(f"建成年份必须在1900至{current_year - 1}之间，当前为 {self.building_year}")

        # 3. 户型互斥：三个中必须恰好一个为1
        layout_fields = ['layout_2室1厅', 'layout_3室1厅', 'layout_3室2厅']
        layout_sum = sum(getattr(self, f) for f in layout_fields)
        if layout_sum != 1:
            raise ValueError(f"户型字段必须且只能选择一个（三个中恰好一个为1），当前和为 {layout_sum}")

        # 4. 楼层互斥：三个中必须恰好一个为1
        floor_fields = ['floor_info_低楼层', 'floor_info_中楼层', 'floor_info_高楼层']
        floor_sum = sum(getattr(self, f) for f in floor_fields)
        if floor_sum != 1:
            raise ValueError(f"楼层字段必须且只能选择一个（三个中恰好一个为1），当前和为 {floor_sum}")

        # 所有校验通过，返回自身
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
        input_dict = house.dict()
        df = pd.DataFrame([input_dict])
        # 确保特征列顺序一致
        for col in feature_cols:
            if col not in df.columns:
                df[col] = 0
        X = df[feature_cols].values
        X_scaled = scaler.transform(X)

        # 融合预测
        xgb_pred = xgb.predict(X_scaled)[0]
        rf_pred = rf.predict(X_scaled)[0]
        final_pred = blend.predict([[xgb_pred, rf_pred]])[0]

        return {"predicted_price": round(final_pred, 2), "unit": "万元"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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


# 在加载完所有模型后（在 root 端点之前或之后均可）
@app.get("/health", summary="健康检查（含模型状态）")
def health_check():
    """返回模型加载状态，用于启动脚本检测"""
    return {
        "status": "ok",
        "models_loaded": {
            "xgb": xgb is not None,
            "rf": rf is not None,
            "blend": blend is not None,
            "scaler": scaler is not None,
            "feature_cols": feature_cols is not None,
        },
        "nlp_engine": nlp_engine is not None
    }


@app.get("/", summary="检查服务是否活着")
def root():
    return {"message": "🏠 房地产AI平台已启动，请访问 /docs 查看接口文档"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000,  workers=1)