# data_pipeline/feature_engineering.py
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.database import SessionLocal, House
from utils.constants import (
    ALL_CITIES,
    SUPPORTED_LAYOUTS,
    SUPPORTED_FLOORS,
    SUPPORTED_DECORATIONS,
    SUPPORTED_ORIENTATIONS,
    normalize_layout,
    clean_floor,
    build_feature_cols,
)
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

    # ---- 清洗并归一户型/楼层（逻辑统一由 utils.constants 提供） ----
    # 户型唯一来源为 rooms 列，layout 仅作为训练期的派生列
    df['layout'] = df['rooms'].apply(normalize_layout)
    df['floor_info'] = df['floor_info'].apply(clean_floor)

    # ---- 显式构造独热编码列（与API的HouseInput字段完全一致） ----
    # 城市独热编码
    for c in ALL_CITIES:
        df[f'city_{c}'] = (df['city'] == c).astype(int)
    # 户型独热编码
    for l in SUPPORTED_LAYOUTS:
        df[f'layout_{l}'] = (df['layout'] == l).astype(int)
    # 楼层独热编码
    for f in SUPPORTED_FLOORS:
        df[f'floor_info_{f}'] = (df['floor_info'] == f).astype(int)
    # 装修独热编码（缺失/未知 -> 全 0，由模型学到“无信息”基准）
    for d in SUPPORTED_DECORATIONS:
        df[f'dec_{d}'] = (df['decoration'] == d).astype(int)
    # 朝向独热编码（缺失/未知/不在列表 -> 全 0）
    for o in SUPPORTED_ORIENTATIONS:
        df[f'ori_{o}'] = (df['orientation'] == o).astype(int)

    # ---- 过滤无效样本（训练目标改为 单价 元/㎡）----
    # 剔除单价缺失/非正/极端异常（>30万/㎡ 视为数据错误），以及面积无效行
    before = len(df)
    df = df[df['unit_price'].notna() & (df['unit_price'] > 0) & (df['unit_price'] < 300000)]
    df = df[df['area'].notna() & (df['area'] > 0)]
    print(f"🧹 过滤无效单价/面积: {before} -> {len(df)} 条")

    # 特征列（与API端HouseInput字段顺序一致）
    feature_cols = build_feature_cols()

    X = df[feature_cols].fillna(0)
    y = df['unit_price']  # 目标变量改为 单价（元/㎡），消除总价对面积的量纲依赖

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