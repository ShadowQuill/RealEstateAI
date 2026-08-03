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
    rooms = Column(String, nullable=True)           # 户型（如 3室2厅）
    floor_info = Column(String, nullable=True)       # 楼层信息
    orientation = Column(String, nullable=True)      # 朝向
    decoration = Column(String, nullable=True)       # 装修情况
    building_year = Column(Integer, nullable=True)   # 建成年份
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
        print("✅ 数据库迁移完成")


if __name__ == "__main__":
    init_db()
    migrate_db()
