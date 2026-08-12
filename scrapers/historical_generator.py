# scrapers/historical_generator.py
"""
【已弃用，请勿运行】

本脚本生成的是合成房源记录。项目现已改为纯真实数据方案：
单一年份城市的历年走势由 models/trend_predictor.py 用国家统计局
70 城二手住宅同比指数折算得到（见 index_adjusted_series），
不再需要合成房源。运行本脚本会把合成数据重新写回 houses 表，
污染真实数据集。保留此文件仅作历史参考。

--- 以下为原始说明 ---

为「仅有单一年份真实数据」的城市生成「锚定真实均价」的历史时序，
使趋势预测模型(要求 >=2 个年份)能基于真实价格水平工作。

与 lianjia_spider.generate_historical_data 的区别:
- 旧逻辑用 DEMO_CITY_DATA 的「假均价」做回退，且会给所有城市(含已有真实多年的)
  追加 2022-2024 合成数据，污染北京真实趋势。
- 本脚本:
  1. 仅处理「真实数据不足 2 个年份」的城市(当前只有上海)。
  2. 以该城市真实数据的实际均价为锚点，按合理年化漂移(默认 +5%/年)回溯。
  3. 历史记录由真实底本缩放得到，价格水平贴近真实，仅年份维度为回测合成。
  4. 幂等:重跑前先清除自身生成的 historical://{city}/% 记录。

用法:
    python3 scrapers/historical_generator.py
"""
import os
import random
import sqlite3
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "realestate.db")

DRIFT = 0.05          # 历史回测年化涨幅(仅用于年份维度的合理漂移)
PRIOR_YEARS = 2       # 为单年城市补 2 个历史年(最终 3 年: base-2, base-1, base)
PER_YEAR = 5000       # 每年抽样条数(不足则取全部)


def generate():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("SELECT 1 FROM houses LIMIT 1")  # 触发表存在(不存在则跳过)
    rows = conn.execute(
        "SELECT city, group_concat(DISTINCT year) FROM houses "
        "WHERE url LIKE 'dataset://%' GROUP BY city"
    ).fetchall()

    now = datetime.datetime.now().isoformat()
    total_gen = 0
    for city, years_str in rows:
        years = sorted(int(y) for y in years_str.split(",") if y)
        if len(years) >= 2:
            print(f"  ⏭️  {city}: 已有真实多年份 {years}，跳过(不污染真实趋势)")
            continue

        base_year = max(years) if years else 2022
        real_avg = conn.execute(
            "SELECT AVG(price) FROM houses WHERE url LIKE 'dataset://%' AND city=?",
            (city,),
        ).fetchone()[0]
        if real_avg is None:
            print(f"  ⚠️  {city}: 无真实均价，跳过")
            continue

        # 清除自身旧历史
        conn.execute("DELETE FROM houses WHERE url LIKE ?", (f"historical://{city}/%",))

        bases = conn.execute(
            """SELECT region, community, title, price, unit_price, area, rooms,
                      floor_info, orientation, decoration, building_year, description
               FROM houses WHERE url LIKE 'dataset://%' AND city=? AND price IS NOT NULL
               ORDER BY RANDOM() LIMIT ?""",
            (city, PER_YEAR * PRIOR_YEARS),
        ).fetchall()

        if not bases:
            continue

        inserted = 0
        for k in range(PRIOR_YEARS):
            yr = base_year - (PRIOR_YEARS - k)
            # 越早的年份价格越低: base_year 均价 / (1+drift)^间隔
            factor = (1.0 + DRIFT) ** (base_year - yr)
            for b in bases:
                (region, community, title, price, unit_price, area, rooms,
                 floor_info, orientation, decoration, building_year, description) = b
                if price is None:
                    continue
                noise = random.uniform(0.96, 1.04)
                prior_price = round(price / factor * noise, 1)
                prior_unit = round(unit_price / factor * noise, 0) if unit_price else None
                hist_desc = f"{description}【历史回测，锚定{base_year}真实均价】"
                conn.execute(
                    """INSERT INTO houses
                       (city, region, community, year, title, price, unit_price,
                        area, rooms, floor_info, orientation, decoration,
                        building_year, description, url, crawled_at, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        city, region, community, yr, title, prior_price, prior_unit,
                        area, rooms, floor_info, orientation, decoration,
                        building_year, hist_desc,
                        f"historical://{city}/{yr}/{inserted}", now, now,
                    ),
                )
                inserted += 1
        conn.commit()
        print(f"  ✅ {city}: 以真实{base_year}年均价 {real_avg:.1f}万 为锚，"
              f"回溯生成 {PRIOR_YEARS} 个历史年，共 {inserted} 条")
        total_gen += inserted

    conn.close()
    print(f"🎉 历史时序生成完成: 共 {total_gen} 条(均锚定真实均价)")


if __name__ == "__main__":
    generate()
