# utils/database.py
import os
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

# 项目目录下的绝对路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "realestate.db")

# 打印最终使用的路径，方便调试
print(f"🔍 数据库路径: {DB_PATH}")

# 注意：绝对路径使用三个斜杠即可（因为路径以 / 开头）
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------- 定义 House 表 ----------
class House(Base):
    __tablename__ = "houses"
    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, index=True)
    year = Column(Integer, index=True)          # 交易年份
    title = Column(String)
    price = Column(Float)                       # 交易时总价（万元）
    unit_price = Column(Float)                  # 交易时单价（元/平米）
    area = Column(Float)
    layout = Column(String)
    floor_info = Column(String)
    building_year = Column(Integer)             # 房屋建成年份
    url = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.datetime.now)

# ---------- 初始化数据库 ----------
def init_db():
    # 确保数据库所在目录存在（对于 ~/ 路径，无需创建，但代码保留通用）
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print(f"✅ 数据库初始化成功！文件位置: {DB_PATH}")