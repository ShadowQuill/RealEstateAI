# scrapers/lianjia_spider.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import SessionLocal, House, init_db
import random
import datetime


# 模拟数据生成器（真实场景可替换为 requests + BeautifulSoup）
def fetch_mock_houses(city="北京", count=20):
    houses = []
    for i in range(count):
        area = round(random.uniform(50, 150), 1)
        unit_price = round(random.uniform(30000, 80000), -3)  # 3万~8万
        total_price = round(area * unit_price / 10000, 1)  # 总价万元
        houses.append({
            "city": city,
            "title": f"{city}朝阳区优质房源{i + 1}号",
            "price": total_price,
            "unit_price": unit_price,
            "area": area,
            "layout": random.choice(["2室1厅", "3室1厅", "3室2厅"]),
            "floor_info": random.choice(["低楼层", "中楼层", "高楼层"]),
            "building_year": random.randint(1990, 2025),
            "url": f"https://example.com/{city}_{i}"
        })
    return houses


def save_to_db(houses):
    db = SessionLocal()
    try:
        for h in houses:
            # 检查是否已存在
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
    # 1. 初始化数据库（只需执行一次）
    init_db()

    # 2. 抓取并保存
    cities = ["北京", "上海", "广州", "深圳"]
    for city in cities:
        data = fetch_mock_houses(city, 15)
        save_to_db(data)