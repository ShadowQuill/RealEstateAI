# data_pipeline/feature_engineering.py
import sys
import os

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.database import SessionLocal, House
import pandas as pd
from sklearn.preprocessing import StandardScaler
import joblib

MODEL_DIR = os.path.join(BASE_DIR, 'models')


def load_and_prepare_data():
    db = SessionLocal()
    try:
        df = pd.read_sql(db.query(House).statement, db.bind)
    finally:
        db.close()

    if df.empty:
        print("⚠️ 数据库为空，请先运行爬虫！")
        return None, None

    df['house_age'] = 2026 - df['building_year']
    df = pd.get_dummies(df, columns=['layout', 'floor_info'], prefix=['layout', 'floor'])

    exclude_cols = ['id', 'title', 'url', 'created_at', 'city', 'building_year']
    feature_cols = [c for c in df.columns if c not in exclude_cols and c != 'price']

    X = df[feature_cols].fillna(0)
    y = df['price']

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(scaler, os.path.join(MODEL_DIR, 'scaler.pkl'))
    joblib.dump(feature_cols, os.path.join(MODEL_DIR, 'feature_cols.pkl'))

    print(f"✅ 特征工程完成，共 {X_scaled.shape[1]} 个特征")
    return X_scaled, y