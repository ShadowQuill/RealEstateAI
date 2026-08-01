# data_pipeline/feature_engineering.py
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.database import SessionLocal, House
import pandas as pd
from sklearn.preprocessing import StandardScaler
import joblib

MODEL_DIR = os.path.join(BASE_DIR, 'models')


# 从数据库取数据，进行加工，最后输出可以直接用于模型训练的数据
def load_and_prepare_data():
    db = SessionLocal()
    try:
        df = pd.read_sql(db.query(House).statement, db.bind)
    finally:
        db.close()

    if df.empty:
        print("⚠️ 数据库为空，请先运行爬虫！")
        return None, None

    # 计算房龄（交易年份 - 建成年份）
    df['house_age'] = df['year'] - df['building_year']

    # 对城市、户型、楼层进行独热编码
    df = pd.get_dummies(df, columns=['city', 'layout', 'floor_info'],
                        prefix=['city', 'layout', 'floor'])

    # 特征列：year, area, house_age, 以及所有独热列（排除 id, title, url, created_at, building_year, unit_price）
    exclude_cols = ['id', 'title', 'url', 'created_at', 'building_year', 'unit_price']
    feature_cols = [c for c in df.columns if c not in exclude_cols and c != 'price']

    X = df[feature_cols].fillna(0)
    y = df['price']

    # 标准化数值特征（year 和 area, house_age）
    # 注意：year 我们也标准化，但预测时我们会传入未来年份，需要先标准化，所以scaler必须保存
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(scaler, os.path.join(MODEL_DIR, 'scaler.pkl'))
    joblib.dump(feature_cols, os.path.join(MODEL_DIR, 'feature_cols.pkl'))

    print(f"✅ 特征工程完成，共 {X_scaled.shape[1]} 个特征")
    print("特征列表:", feature_cols)
    return X_scaled, y