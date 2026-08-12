# utils/database.py
import os
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "realestate.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class House(Base):
    __tablename__ = "houses"
    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, index=True)
    region = Column(String, index=True, nullable=True)
    community = Column(String, nullable=True)
    year = Column(Integer, index=True)
    title = Column(String)
    price = Column(Float)
    unit_price = Column(Float)
    area = Column(Float)
    rooms = Column(String, nullable=True)           # 户型（如 3室2厅），唯一户型字段
    floor_info = Column(String, nullable=True)       # 楼层信息
    orientation = Column(String, nullable=True)      # 朝向
    decoration = Column(String, nullable=True)       # 装修情况
    building_year = Column(Integer, nullable=True)   # 建成年份
    property_type = Column(String, index=True, default='二手房')  # 房源类型：二手房 / 新房
    description = Column(Text, nullable=True)        # 房源描述
    url = Column(String, unique=True)
    crawled_at = Column(DateTime, default=datetime.datetime.now)
    created_at = Column(DateTime, default=datetime.datetime.now)


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print(f"✅ 数据库初始化成功！文件位置: {DB_PATH}")


def migrate_db():
    """迁移数据库：为旧表添加新列"""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    existing_cols = {c['name'] for c in inspector.get_columns('houses')} if inspector.has_table('houses') else set()
    
    new_columns = {
        'region': 'String',
        'community': 'String',
        'rooms': 'String',
        'orientation': 'String',
        'decoration': 'String',
        'property_type': 'String',
        'description': 'Text',
        'crawled_at': 'DateTime',
    }

    with engine.connect() as conn:
        for col_name, col_type in new_columns.items():
            if col_name not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE houses ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                    print(f"  ✅ 添加列: {col_name} ({col_type})")
                except Exception as e:
                    print(f"  ⚠️ 跳过 {col_name}: {e}")

        # 清理冗余的 layout 列：户型统一由 rooms 承载
        if 'layout' in existing_cols:
            try:
                # 先把 rooms 缺失但 layout 有值的记录补回，避免丢数据
                conn.execute(text(
                    "UPDATE houses SET rooms = layout "
                    "WHERE (rooms IS NULL OR rooms = '') AND layout IS NOT NULL AND layout != ''"
                ))
                conn.execute(text("ALTER TABLE houses DROP COLUMN layout"))
                conn.commit()
                print("  ✅ 移除冗余列: layout（已并入 rooms）")
            except Exception as e:
                # SQLite < 3.35 不支持 DROP COLUMN，保留旧列不影响运行
                print(f"  ⚠️ 未能移除 layout 列（可忽略）: {e}")

        print("✅ 数据库迁移完成")


class CityIndex(Base):
    """国家统计局 70 城房价指数（新房/二手房，月度，同比/环比）。

    数据源：hugohe3/70cityprice（国家统计局官方发布）。
    与 House 房源级数据不同，这是城市级价格指数，用于新房/二手房
    走势对比与政策影响分析（新房挂牌价 ≠ 成交价，受政策影响大）。
    """
    __tablename__ = "city_index"
    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, index=True)
    adcode = Column(String, nullable=True)
    year = Column(Integer, index=True)
    month = Column(Integer, index=True)
    date_str = Column(String)                 # 原始日期，如 2006/1/1
    base_type = Column(String, index=True)    # 同比 / 环比
    house_idx = Column(Float, nullable=True)          # 新建住宅价格指数
    resident_idx = Column(Float, nullable=True)       # 二手住宅价格指数（总）
    commodity_idx = Column(Float, nullable=True)      # 新房（商品住宅）指数
    secondhand_idx = Column(Float, nullable=True)    # 二手房指数
    commodity_below90 = Column(Float, nullable=True)
    commodity_144 = Column(Float, nullable=True)
    commodity_above144 = Column(Float, nullable=True)
    secondhand_below90 = Column(Float, nullable=True)
    secondhand_144 = Column(Float, nullable=True)
    secondhand_above144 = Column(Float, nullable=True)


if __name__ == "__main__":
    init_db()
    migrate_db()
