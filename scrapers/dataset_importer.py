# scrapers/dataset_importer.py
"""
从「公开真实数据集」(非爬虫)导入二手房数据到 SQLite。

数据来源(均为链家二手房/成交真实数据):
  1. 上海 xiashen532/DataMining/ershoufang.csv   (UTF-8,  ~1.97万行, 挂牌)
     字段: name, model, area, direction, fitment, floor, address, total_list, price_list
  2. 上海 shuifanwangqi/.../sh.csv                (GBK,   ~7.33万行, 挂牌, 含建成年份 + 真实房源url)
     字段: house_title, house_img, s_cate_href, house_desc, zone_href,
           district, house_detail, house_price, house_href, s_cate,
           singel_price, house_time
  3. 北京 Kaggle 镜像 balamurugan-kalaiarasu/...  (GBK, ~31.9万行, 成交)
     字段: url, id, Lng, Lat, Cid, tradeTime, DOM, followers, totalPrice, price,
           square, livingRoom, drawingRoom, kitchen, bathRoom, floor, buildingType,
           constructionTime, renovationCondition, buildingStructure, ladderRatio,
           elevator, fiveYearsProperty, subway, district, communityAverage
     —— 关键: tradeTime 为真实成交日期(2011-2017)，可直接用于趋势模型。

设计原则:
- 仅本地使用,不修改任何爬虫 / 模型逻辑。
- 全部以 dataset:// 开头的 url 标记,清理时 DELETE ... WHERE url NOT LIKE 'dataset://%' 可整体移除。
- 零额外依赖: 仅用标准库 sqlite3 + csv,避免在本机缺失依赖环境下失败。
- 字段归一化与 utils/constants.py 的 SUPPORTED_LAYOUTS / SUPPORTED_FLOORS 对齐,
  使导入的真实数据能直接进入现有特征工程与预测模型。

用法:
    python3 scrapers/dataset_importer.py            # 追加导入所有源
    python3 scrapers/dataset_importer.py --clear    # 先清旧导入再导入
"""
import csv
import os
import re
import sqlite3
import datetime
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "realestate.db")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")

# 北京 district 数字码 -> 行政区名 (链家北京城区编码)
DISTRICT_MAP = {
    '1': '东城', '2': '丰台', '3': '石景山', '4': '通州', '5': '昌平',
    '6': '大兴', '7': '朝阳', '8': '海淀', '9': '西城', '10': '崇文',
    '11': '宣武', '12': '门头沟', '13': '房山', '14': '顺义', '15': '密云',
    '16': '怀柔', '17': '平谷', '18': '延庆',
}
# 北京 renovationCondition 码 -> 装修描述
RENOVATION_MAP = {'1': '其他', '2': '毛坯', '3': '简装', '4': '精装'}

# 各数据源: (文件名, 编码, 城市, 解析器key, 年份模式)
# 年份模式: 'fixed' 用固定 DATASET_YEAR; 'trade' 从成交日期取真实年份
SOURCES = [
    ("shanghai_ershoufang.csv", "utf-8", "上海", "ershoufang", "fixed", 2022),
    ("shanghai_sh.csv", "gbk", "上海", "sh", "fixed", 2022),
    ("beijing_chengjiao.csv", "gbk", "北京", "beijing", "trade", None),
]

# 尝试复用 constants 的户型归一化(单一数据源);失败则用内置兜底。
try:
    sys.path.insert(0, BASE_DIR)
    from utils.constants import normalize_layout as _normalize_layout  # type: ignore
    def normalize_layout(s):
        return _normalize_layout(s)
except Exception:
    LAYOUT_MAP = {
        '1室0厅': '2室1厅', '1室1厅': '2室1厅', '1室2厅': '2室1厅',
        '2室1厅': '2室1厅', '2室2厅': '3室1厅', '3室1厅': '3室1厅',
        '3室2厅': '3室2厅', '4室1厅': '3室2厅', '4室2厅': '3室2厅',
        '5室2厅': '3室2厅', '其他': '其他',
    }
    def normalize_layout(s):
        s = (s or '').strip()
        return LAYOUT_MAP.get(s, '其他')


def parse_floor(raw):
    """将楼层描述归一到 低/中/高楼层(与 utils/constants.SUPPORTED_FLOORS 一致)。"""
    s = "" if raw is None else str(raw)
    # 北京字段形如 '高 26' / '中 4' / '低 3'；优先取 低/中/高
    m = re.search(r'[低中高]', s)
    if m:
        t = m.group(0)
        return {"低": "低楼层", "中": "中楼层", "高": "高楼层"}[t]
    m_total = re.search(r"共(\d+)层", s)
    m_cur = re.search(r"(\d+)层", s)
    if m_cur and m_total:
        try:
            ratio = int(m_cur.group(1)) / int(m_total.group(1))
            if ratio < 0.34:
                return "低楼层"
            if ratio > 0.67:
                return "高楼层"
            return "中楼层"
        except ZeroDivisionError:
            pass
    if m_cur:
        cur = int(m_cur.group(1))
        return "低楼层" if cur <= 6 else ("高楼层" if cur > 15 else "中楼层")
    return "中楼层"


def to_float(s, default=None):
    """提取字符串中的数字(去掉 平米 / 元/平 / 逗号 等非数字字符)。"""
    if s is None:
        return default
    s = re.sub(r"[^\d.]", "", str(s))
    try:
        return float(s) if s else default
    except ValueError:
        return default


def parse_year_built(raw):
    """'1985' / '1985年建' -> 1985; 缺失或越界返回 None。"""
    if not raw:
        return None
    m = re.search(r"(\d{4})", str(raw))
    if not m:
        return None
    y = int(m.group(1))
    return y if 1900 <= y <= 2026 else None


def clean_region(raw):
    """'虹口二手房' -> '虹口'。"""
    if not raw:
        return None
    return str(raw).replace("二手房", "").strip()


def ensure_table(conn):
    """确保 houses 表存在,字段与 utils/database.py 的 House 模型一致。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS houses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT, region TEXT, community TEXT, year INTEGER,
            title TEXT, price REAL, unit_price REAL, area REAL,
            rooms TEXT, floor_info TEXT, orientation TEXT,
            decoration TEXT, building_year INTEGER,
            property_type TEXT DEFAULT '二手房',
            description TEXT,
            url TEXT UNIQUE, deal_id TEXT, crawled_at TEXT, created_at TEXT
        )"""
    )


def _parse_ershoufang(row):
    """解析 xiashen532/ershoufang.csv 的一行 -> House 字段 dict 或 None。"""
    name = (row.get("name") or "").strip()
    model = (row.get("model") or "").strip()
    area_v = to_float(row.get("area"))
    price = to_float(row.get("total_list"))
    unit = to_float(row.get("price_list"))
    if price is None or area_v is None:
        return None
    address = (row.get("address") or "").strip()
    direction = (row.get("direction") or "").strip()
    fitment = (row.get("fitment") or "").strip()
    floor = (row.get("floor") or "").strip()
    community = name or "未知小区"
    floor_info = parse_floor(floor)
    rooms = normalize_layout(model)
    title = f"{community} {model}".strip()
    desc = (
        f"{title}，位于{address}，{model}，{direction}朝向，"
        f"{fitment}，{floor}，建筑面积{area_v:.1f}平米，"
        f"总价{price}万，单价约{int(unit) if unit else 0}元/平。"
    )
    return dict(
        region=address, community=community, title=title,
        price=price, unit_price=unit, area=area_v, rooms=rooms,
        floor_info=floor_info, orientation=direction or None,
        decoration=fitment or None, building_year=None, description=desc,
    )


def _parse_sh(row):
    """解析 shuifanwangqi/sh.csv 的一行 -> House 字段 dict 或 None。
    house_desc = '1室0厅|37.6平|低区/6层|朝南'
    """
    hd = (row.get("house_desc") or "").strip()
    parts = hd.split("|")
    if len(parts) < 2:
        return None
    model = parts[0].strip()
    area_v = to_float(parts[1])
    floor_raw = parts[2] if len(parts) > 2 else ""
    orient_raw = parts[3].replace("朝", "").strip() if len(parts) > 3 else ""
    price = to_float(row.get("house_price"))
    unit = to_float(row.get("singel_price"))
    if price is None or area_v is None:
        return None
    community = (row.get("house_detail") or "").strip() or "未知小区"
    region = clean_region(row.get("district"))
    floor_info = parse_floor(floor_raw)
    building_year = parse_year_built(row.get("house_time"))
    rooms = normalize_layout(model)
    title = f"{community} {model}".strip()
    desc = (
        f"{title}，位于{region}，{model}，{orient_raw}朝向，{floor_raw}，"
        f"建筑面积{area_v:.1f}平米，总价{price}万，单价约{int(unit) if unit else 0}元/平，"
        f"建成于{building_year}年。"
    )
    return dict(
        region=region, community=community, title=title,
        price=price, unit_price=unit, area=area_v, rooms=rooms,
        floor_info=floor_info, orientation=orient_raw or None,
        decoration=None, building_year=building_year, description=desc,
    )


def _parse_beijing(row):
    """解析 Kaggle 北京成交数据 new.csv 的一行 -> House 字段 dict 或 None。
    真实成交: tradeTime 取年份, totalPrice=总价(万), price=单价(元/平),
    square=面积, livingRoom/drawingRoom=户型, floor=楼层,
    constructionTime=建成年份, district=城区码, renovationCondition=装修。
    """
    trade = (row.get("tradeTime") or "").strip()
    m = re.match(r"(\d{4})", trade)
    if not m:
        return None
    year = int(m.group(1))
    if not (2000 <= year <= 2026):
        return None

    price = to_float(row.get("totalPrice"))      # 总价, 万
    unit = to_float(row.get("price"))            # 单价, 元/平
    area_v = to_float(row.get("square"))         # 面积, 平米
    if price is None or area_v is None or area_v <= 0:
        return None

    living = (row.get("livingRoom") or "").strip()
    drawing = (row.get("drawingRoom") or "").strip()
    if living.isdigit() and drawing.isdigit():
        model = f"{living}室{drawing}厅"
    else:
        model = "2室1厅"
    rooms = normalize_layout(model)

    district = DISTRICT_MAP.get((row.get("district") or "").strip(), "未知区域")
    floor_info = parse_floor(row.get("floor"))
    building_year = parse_year_built(row.get("constructionTime"))
    renovation = RENOVATION_MAP.get((row.get("renovationCondition") or "").strip())
    community = "未知小区"
    real_url = (row.get("url") or "").strip()
    title = f"北京 {district} {model} {floor_info}"
    desc_parts = [f"北京{district}，{model}，{floor_info}"]
    if building_year:
        desc_parts.append(f"建成于{building_year}年")
    if renovation:
        desc_parts.append(renovation)
    desc_parts.append(f"建筑面积{area_v:.1f}平米，总价{price}万，单价约{int(unit) if unit else 0}元/平，成交于{trade}。")
    if real_url:
        desc_parts.append(f"来源: {real_url}")
    desc = "，".join(desc_parts)
    return dict(
        region=district, community=community, title=title,
        price=price, unit_price=unit, area=area_v, rooms=rooms,
        floor_info=floor_info, orientation=None,
        decoration=renovation, building_year=building_year, description=desc,
    )


_PARSERS = {
    "ershoufang": _parse_ershoufang,
    "sh": _parse_sh,
    "beijing": _parse_beijing,
}


def import_all(clear_first=False):
    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)
    if clear_first:
        conn.execute("DELETE FROM houses WHERE url LIKE 'dataset://%'")
        print("🧹 已清除上一次的数据集导入记录")

    total_ins = 0
    total_skip = 0
    for fname, enc, city, key, year_mode, fixed_year in SOURCES:
        path = os.path.join(RAW_DIR, fname)
        if not os.path.exists(path):
            print(f"⚠️  跳过缺失数据源: {path}")
            continue
        parser = _PARSERS[key]
        inserted = 0
        skipped = 0
        batch = []
        now = datetime.datetime.now().isoformat()

        def flush():
            nonlocal inserted
            if not batch:
                return
            conn.executemany(
                """INSERT OR IGNORE INTO houses
                   (city, region, community, year, title, price, unit_price,
                    area, rooms, floor_info, orientation, decoration,
                    building_year, property_type, description,
                    url, crawled_at, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                batch,
            )
            inserted += len(batch)
            batch.clear()

        with open(path, encoding=enc, errors="ignore") as fh:
            reader = csv.DictReader(fh)
            for idx, row in enumerate(reader):
                fields = parser(row)
                if fields is None:
                    skipped += 1
                    continue
                if year_mode == "trade":
                    trade = (row.get("tradeTime") or "").strip()
                    ym = re.match(r"(\d{4})", trade)
                    year = int(ym.group(1)) if ym else fixed_year
                else:
                    year = fixed_year
                url = f"dataset://{city}-{key}/{idx}"
                batch.append((
                    city, fields.get("region"), fields.get("community"),
                    year, fields.get("title"), fields.get("price"),
                    fields.get("unit_price"), fields.get("area"), fields.get("rooms"),
                    fields.get("floor_info"), fields.get("orientation"),
                    fields.get("decoration"), fields.get("building_year"),
                    "二手房", fields.get("description"), url, now, now,
                ))
                if len(batch) >= 5000:
                    flush()
        flush()
        conn.commit()
        print(f"  ✅ {fname} ({city}): 新增 {inserted} 条, 跳过 {skipped} 条")
        total_ins += inserted
        total_skip += skipped

    conn.close()
    print(f"🎉 全部导入完成: 共新增 {total_ins} 条真实数据, 跳过 {total_skip} 条")


if __name__ == "__main__":
    clear = "--clear" in sys.argv
    import_all(clear_first=clear)
