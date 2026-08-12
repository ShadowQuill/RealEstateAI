# run_update_real.py
"""
基于「真实数据集」更新并训练模型 —— 安全版，不会清空 / 不会回退模拟数据。

与 run_update.py 的关键区别:
  - run_update.py 会 db.query(House).delete() 清空全部数据(包括已导入的真实数据)，
    然后爬虫在反爬下回退到 DEMO_CITY_DATA 模拟数据 —— 这会抹掉你辛苦导入的真实数据！
  - 本脚本只做「追加真实数据 + 补历史时序 + 重训模型」，绝不删除 dataset:// 记录。

前置: 已 pip install -r requirements.txt（需要 sklearn / xgboost / joblib / pandas 等）
用法:
    python run_update_real.py
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from utils.database import init_db, migrate_db
from scrapers.dataset_importer import import_all
from models.train import train
from models.trend_predictor import TrendPredictor


def main():
    print("🔄 基于真实数据更新模型...\n")

    # 0. 初始化数据库
    init_db()
    migrate_db()

    # 1. 追加真实数据集(已存在则 INSERT OR IGNORE 跳过，不重复)
    print("=" * 50)
    print("📥 第一步：导入 / 追加真实数据集")
    print("=" * 50)
    import_all()

    # 2. 训练价格预测模型（读取 houses 表全部真实数据）
    print("\n" + "=" * 50)
    print("🧠 第二步：训练价格预测模型")
    print("=" * 50)
    train()

    # 3. 训练趋势预测模型
    #    单一年份城市(如上海仅 2022 年)的历年走势，由 trend_predictor
    #    用国家统计局 70 城同比指数折算，不再生成合成数据。
    print("\n" + "=" * 50)
    print("📈 第三步：训练趋势预测模型")
    print("=" * 50)
    predictor = TrendPredictor()
    results = predictor.fit_all_cities()
    for city, res in results.items():
        r2 = res.get('r2_score')
        r2_str = f"{r2:.4f}" if r2 is not None else "—(单年快照)"
        print(f"  ✅ {city}: {res['historical_years']} 年数据, R²={r2_str}")
    predictor.save_model()
    print(f"✅ 趋势模型训练完成，共 {len(results)} 个城市")

    print("\n" + "=" * 50)
    print("🎉 全部完成！模型已基于真实数据重新训练。")
    print("=" * 50)
    print("\n📱 启动系统:")
    print("   后端: python run_system.py")
    print("   前端: cd frontend && npm run dev")


if __name__ == "__main__":
    main()
