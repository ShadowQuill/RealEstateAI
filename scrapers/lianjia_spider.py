# scrapers/lianjia_spider.py
import sys
import os
import random
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import SessionLocal, House, init_db

def fetch_mock_houses(city="北京", year=2020, count=15):
    houses = []
    # 基础单价随年份增长（从2015年到2026年约增长60%，年均约4.5%）
    base_unit_price = 30000 + (year - 2015) * 2000  # 年增2000元/平米
    for i in range(count):
        area = round(random.uniform(50, 150), 1)
        # 加一些随机波动
        unit_price = round(base_unit_price * random.uniform(0.9, 1.1), -3)
        total_price = round(area * unit_price / 10000, 1)
        # 建成年份：在交易年份前5~20年
        building_year = year - random.randint(5, 20)
        houses.append({
            "city": city,
            "year": year,
            "title": f"{city} {year}年优质房源{i+1}号",
            "price": total_price,
            "unit_price": unit_price,
            "area": area,
            "layout": random.choice(["2室1厅", "3室1厅", "3室2厅"]),
            "floor_info": random.choice(["低楼层", "中楼层", "高楼层"]),
            "building_year": building_year,
            "url": f"https://example.com/{city}_{year}_{i}"
        })
    return houses

# 定义数据保存函数
def save_to_db(houses):
    db = SessionLocal()
    try:
        for h in houses:
            exist = db.query(House).filter(House.url == h["url"]).first()
            if not exist:
                new_house = House(**h)
                db.add(new_house)
        db.commit()
        print(f"✅ 成功写入 {len(houses)} 条房源数据")
    except Exception as e:
        db.rollback()
        print(f"❌ 写入失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    cities = ["北京", "上海", "广州", "深圳"]
    # 生成2015到2026年的数据
    for year in range(2015, 2027):
        for city in cities:
            data = fetch_mock_houses(city, year, 15)
            save_to_db(data)
    print("🎉 所有年度数据写入完成！")