# run_update.py
"""
一键更新脚本：清空旧数据 → 重新爬取 → 重新训练价格预测模型 → 训练趋势预测模型
用法：python run_update.py
"""
import sys
import os
import time
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from utils.database import SessionLocal, House, init_db, migrate_db
from scrapers.lianjia_spider import parse_listing_page, save_to_db, generate_historical_data, CITY_URL_MAP, DATA_SOURCES
from models.train import train


def clear_old_data():
    db = SessionLocal()
    try:
        count = db.query(House).count()
        if count > 0:
            db.query(House).delete()
            db.commit()
            print(f"🗑️ 已清空旧数据 {count} 条")
        else:
            print("📭 数据库原本就是空的，无需清空")
    except Exception as e:
        db.rollback()
        print(f"❌ 清空数据失败: {e}")
    finally:
        db.close()


def run_spider():
    cities = list(CITY_URL_MAP.keys())
    print("\n" + "=" * 50)
    print("📡 第一步：从链家 + 贝壳爬取真实房源数据")
    print(f"🏙️  共 {len(cities)} 个城市，2 个平台")
    print("=" * 50)

    total = 0
    for source_name, domain in DATA_SOURCES.items():
        print(f"\n🔗 数据源：{source_name}（{domain}）")
        print("-" * 40)
        for city in cities:
            city_url_name = CITY_URL_MAP[city]
            print(f"  🏙️ {city} 第1页", end='')
            houses = parse_listing_page(city, city_url_name, 1, domain=domain)
            if not houses:
                print(" (无数据)")
            else:
                saved = save_to_db(houses)
                total += saved
                print(f" [{len(houses)}条]")
            time.sleep(random.uniform(2.0, 5.0))

    print(f"\n🎉 爬取完成，共写入 {total} 条真实房源数据")


def retrain_price_model():
    print("\n" + "=" * 50)
    print("🧠 第二步：重新训练价格预测模型")
    print("=" * 50)
    train()


def retrain_trend_model():
    print("\n" + "=" * 50)
    print("📈 第三步：训练趋势预测模型")
    print("=" * 50)
    try:
        from models.trend_predictor import TrendPredictor
        predictor = TrendPredictor()
        results = predictor.fit_all_cities()
        for city, res in results.items():
            print(f"  ✅ {city}: {res['historical_years']}年数据, R²={res['r2_score']:.4f}")
        predictor.save_model()
        print(f"✅ 趋势预测模型训练完成，共 {len(results)} 个城市")
    except Exception as e:
        print(f"❌ 趋势预测模型训练失败: {e}")


if __name__ == "__main__":
    print("🔄 开始执行数据更新流程...\n")

    # 0. 初始化/迁移数据库
    init_db()
    migrate_db()

    # 1. 清空旧数据
    clear_old_data()

    # 2. 重新爬取数据
    run_spider()

    # 2.5. 生成历史数据
    print("\n" + "=" * 50)
    print("📊 第1.5步：生成历史数据（2022-2025）")
    print("=" * 50)
    generate_historical_data()

    # 3. 价格预测模型
    retrain_price_model()

    # 4. 趋势预测模型
    retrain_trend_model()

    print("\n" + "=" * 50)
    print("✅ 全部流程执行完毕！数据库和模型均已更新。")
    print("=" * 50)
    print("\n📱 启动系统:")
    print("   后端: python run_system.py")
    print("   前端: cd frontend && npm run dev")
