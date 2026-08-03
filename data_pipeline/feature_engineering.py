# data_pipeline/feature_engineering.py
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from utils.database import SessionLocal, House
import pandas as pd
import re
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

    # ---- 清洗 layout 字段：提取纯户型，去除混入的楼层信息 ----
    def clean_layout(raw):
        if pd.isna(raw) or not raw:
            return '3室2厅'
        # 从混合文本中提取 X室X厅
        m = re.search(r'(\d+[室房]\d*厅?)', str(raw))
        if m:
            return m.group(1)
        return '3室2厅'

    def clean_floor(raw):
        if pd.isna(raw) or not raw:
            return '中楼层'
        s = str(raw)
        if '低' in s:
            return '低楼层'
        elif '高' in s:
            return '高楼层'
        return '中楼层'

    # 标准化户型映射（只保留API支持的3种户型，其余统一归入2室1厅）
    LAYOUT_MAP = {
        '2室0厅': '2室1厅', '2室1厅': '2室1厅', '2室2厅': '2室1厅',
        '3室1厅': '3室1厅', '3室2厅': '3室2厅', '3室3厅': '3室2厅',
        '1室0厅': '2室1厅', '1室1厅': '2室1厅', '1室2厅': '2室1厅',
        '4室1厅': '3室2厅', '4室2厅': '3室2厅', '5室2厅': '3室2厅',
        '6室2厅': '3室2厅', '0室0厅': '3室2厅',
    }

    df['layout'] = df['layout'].apply(clean_layout)
    df['layout'] = df['layout'].map(lambda x: LAYOUT_MAP.get(x, '3室2厅'))
    df['floor_info'] = df['floor_info'].apply(clean_floor)

    # ---- 显式构造独热编码列（与API的HouseInput字段完全一致） ----
    ALL_CITIES = [
        '北京', '上海', '广州', '深圳',
        '成都', '重庆', '杭州', '武汉', '天津',
        '苏州', '南京', '西安', '郑州', '长沙',
        '合肥', '青岛', '东莞', '佛山', '宁波',
        '大连', '沈阳', '济南', '昆明', '厦门',
        '福州', '无锡', '珠海', '哈尔滨', '南宁',
    ]
    SUPPORTED_LAYOUTS = ['2室1厅', '3室1厅', '3室2厅']
    SUPPORTED_FLOORS = ['低楼层', '中楼层', '高楼层']

    # 城市独热编码
    for c in ALL_CITIES:
        df[f'city_{c}'] = (df['city'] == c).astype(int)
    # 户型独热编码
    for l in SUPPORTED_LAYOUTS:
        df[f'layout_{l}'] = (df['layout'] == l).astype(int)
    # 楼层独热编码
    for f in SUPPORTED_FLOORS:
        df[f'floor_info_{f}'] = (df['floor_info'] == f).astype(int)

    # 特征列（与API端HouseInput字段顺序一致）
    feature_cols = ['year', 'area', 'house_age']
    feature_cols += [f'city_{c}' for c in ALL_CITIES]
    feature_cols += [f'layout_{l}' for l in SUPPORTED_LAYOUTS]
    feature_cols += [f'floor_info_{f}' for f in SUPPORTED_FLOORS]

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