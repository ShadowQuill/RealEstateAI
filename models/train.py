# models/train.py
import sys
import os

# 获取项目根目录（RealEstateAI/）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from data_pipeline.feature_engineering import load_and_prepare_data
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import numpy as np
import joblib

MODEL_DIR = os.path.join(BASE_DIR, 'models')  # 统一模型保存目录

def train():
    X, y = load_and_prepare_data()
    if X is None:
        return

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    xgb = XGBRegressor(
        n_estimators=150,
        learning_rate=0.1,
        max_depth=8,
        random_state=42,
        tree_method='hist',  # 解决 ARM 崩溃
        n_jobs=-1,  # 充分利用 CPU 所有核心
        enable_categorical=False  # 因为我们的特征已经做过独热编码了，保持 False 更稳
    )
    xgb.fit(X_train, y_train)
    xgb_pred = xgb.predict(X_test)

    rf = RandomForestRegressor(n_estimators=150, max_depth=14, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)

    blend_X = np.column_stack((xgb_pred, rf_pred))
    blend_model = LinearRegression()
    blend_model.fit(blend_X, y_test)
    blend_pred = blend_model.predict(blend_X)

    # 定义评估函数（当前目标变量为单价 元/㎡）
    def evaluate(name, preds):
        print(f"📊 {name} (单价 元/㎡):")
        print(f"  RMSE: {np.sqrt(mean_squared_error(y_test, preds)):.2f}")
        print(f"  MAE:  {mean_absolute_error(y_test, preds):.2f}")
        print(f"  R²:   {r2_score(y_test, preds):.4f}")

    evaluate("XGBoost", xgb_pred)
    evaluate("RandomForest", rf_pred)
    evaluate("Blended(融合)", blend_pred)

    # 确保目录存在
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(xgb, os.path.join(MODEL_DIR, 'xgb_model.pkl'))
    joblib.dump(rf, os.path.join(MODEL_DIR, 'rf_model.pkl'))
    joblib.dump(blend_model, os.path.join(MODEL_DIR, 'blend_model.pkl'))
    print(f"✅ 所有模型已保存至 {MODEL_DIR}")

if __name__ == "__main__":
    train()