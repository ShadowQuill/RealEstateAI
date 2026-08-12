"""导入国家统计局 70 城房价指数到 city_index 表（零依赖：标准库 csv + sqlite3）。

数据源：hugohe3/70cityprice（国家统计局官方发布，月度，2006 至今）。
每行 = 某城市某个日期的某个口径（同比/环比）的多项价格指数。

为什么用指数而非房源级数据？
- 新房（一手房）公开可直连的房源级真实数据极少；其挂牌价 ≠ 实际成交价，
  且受限价、摇号、备案等政策影响大，房源级“价格”失真。
- 国家统计局 70 城指数（新建商品住宅价格指数 + 二手住宅价格指数）是官方、
  权威、政策敏感的真实数据，天然区分新房与二手房，最适合作为新房页的数据底座。

用法：
    python scrapers/index_importer.py            # 导入全部
    python scrapers/index_importer.py --clear    # 清旧后重导（幂等）
"""
import csv
import os
import re
import sqlite3
import sys

# 复用项目的数据库路径，保证与 ORM 同一文件
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
DB_PATH = os.path.join(_ROOT, "data", "realestate.db")
CSV_PATH = os.path.join(_ROOT, "data", "raw", "70cityprice.csv")

# CSV 原始列 -> (CityIndex 字段, 是否数值)
COL_MAP = [
    ("HouseIDX", "house_idx"),
    ("ResidentIDX", "resident_idx"),
    ("CommodityHouseIDX", "commodity_idx"),
    ("SecondHandIDX", "secondhand_idx"),
    ("CommodityBelow90IDX", "commodity_below90"),
    ("Commodity144IDX", "commodity_144"),
    ("CommodityAbove144IDX", "commodity_above144"),
    ("SecondHandBelow90IDX", "secondhand_below90"),
    ("SecondHand144IDX", "secondhand_144"),
    ("SecondHandAbove144IDX", "secondhand_above144"),
]

INSERT_SQL = """
INSERT INTO city_index (
    city, adcode, year, month, date_str, base_type,
    house_idx, resident_idx, commodity_idx, secondhand_idx,
    commodity_below90, commodity_144, commodity_above144,
    secondhand_below90, secondhand_144, secondhand_above144
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""


def _to_float(v):
    v = (v or "").strip()
    if v == "" or v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def import_index(clear=False):
    if not os.path.exists(CSV_PATH):
        print(f"❌ 找不到索引 CSV：{CSV_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 确保表存在（与 ORM 表名一致）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS city_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT, adcode TEXT,
            year INTEGER, month INTEGER, date_str TEXT,
            base_type TEXT,
            house_idx REAL, resident_idx REAL, commodity_idx REAL, secondhand_idx REAL,
            commodity_below90 REAL, commodity_144 REAL, commodity_above144 REAL,
            secondhand_below90 REAL, secondhand_144 REAL, secondhand_above144 REAL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_city_index_city ON city_index(city)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_city_index_ym ON city_index(year, month)")

    if clear:
        cur.execute("DELETE FROM city_index")
        conn.commit()
        print("🧹 已清空旧 city_index 数据")

    total = 0
    skipped = 0
    with open(CSV_PATH, encoding="utf-8-sig", errors="ignore", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for row in reader:
            city = (row.get("CITY") or "").strip()
            adcode = (row.get("ADCODE") or "").strip()
            date_str = (row.get("DATE") or "").strip()
            base_type = (row.get("FixedBase") or "").strip()
            if not city or not date_str:
                skipped += 1
                continue
            m = re.match(r"(\d{4})\s*/\s*(\d{1,2})", date_str)
            if not m:
                skipped += 1
                continue
            year = int(m.group(1))
            month = int(m.group(2))
            vals = (
                city, adcode, year, month, date_str, base_type,
            ) + tuple(_to_float(row.get(c)) for c, _ in COL_MAP)
            rows.append(vals)
            total += 1

    cur.executemany(INSERT_SQL, rows)
    conn.commit()

    # 统计
    n_rows = cur.execute("SELECT COUNT(*) FROM city_index").fetchone()[0]
    n_cities = cur.execute("SELECT COUNT(DISTINCT city) FROM city_index").fetchone()[0]
    yr = cur.execute("SELECT MIN(year), MAX(year) FROM city_index").fetchone()
    conn.close()
    print(f"✅ 导入完成：共 {n_rows} 行（含同比/环比两类），覆盖 {n_cities} 个城市，年份区间 {yr[0]}–{yr[1]}")
    if skipped:
        print(f"   ⚠️ 跳过 {skipped} 行（缺城市/日期/格式异常）")
    return n_rows, n_cities


if __name__ == "__main__":
    do_clear = "--clear" in sys.argv
    import_index(clear=do_clear)
