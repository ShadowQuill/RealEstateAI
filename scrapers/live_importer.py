# scrapers/live_importer.py
"""
联网直爬贝壳(ke.com)「真实二手房房源」导入器 —— 纯真实、零合成。

设计原则（与项目「全真实数据」方针一致）:
  - 只保存从贝壳列表页真实解析到的房源；绝不生成 / 回退任何模拟数据。
  - 绕过本地 HTTP 代理直连（贝壳对部分子域经代理会 502，直连稳定）。
  - 某页拿不到真实房源(反爬验证码 / 已到末页)就停止该城，绝不造假填充。
  - 年份统一标为「当前年」(这些是当下在售房源)；单年城市的历年走势由
    trend_predictor 用官方 70 城指数折算，与上海口径一致，不生成合成时序。
  - url 使用贝壳真实房源链接(唯一)，INSERT OR IGNORE 幂等，可重复运行。

与 lianjia_spider.py 的区别:
  lianjia_spider 是「真实请求失败→回退 DEMO_CITY_DATA 模拟 + generate_historical_data
  造 historical:// 假数据」的混合脚本，会污染真实库；本脚本严格真实-only。

用法:
    python scrapers/live_importer.py                 # 全部已验证城市，每城最多 15 页
    python scrapers/live_importer.py --pages 8       # 每城最多 8 页
    python scrapers/live_importer.py --cities 成都,武汉,中山
"""
import sys
import os
import re
import time
import random
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import SessionLocal, House, init_db, migrate_db
# 复用 dataset_importer 的归一化工具，保证与既有数据口径一致
from scrapers.dataset_importer import parse_floor, normalize_layout, to_float

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
# 直连，不经过本地代理（代理对某些子域返回 502）
NO_PROXY = {"http": None, "https": None}

# 已实测可返回真实房源的城市（链家/贝壳码）。涵盖一线 / 新一线 / 二线 / 中小城市。
CITY_LIST = [
    ("北京", "bj"), ("上海", "sh"), ("广州", "gz"), ("深圳", "sz"), ("成都", "cd"),
    ("重庆", "cq"), ("杭州", "hz"), ("武汉", "wh"), ("天津", "tj"), ("苏州", "su"),
    ("南京", "nj"), ("西安", "xa"), ("郑州", "zz"), ("长沙", "cs"), ("合肥", "hf"),
    ("青岛", "qd"), ("东莞", "dg"), ("佛山", "fs"), ("宁波", "nb"), ("大连", "dl"),
    ("沈阳", "sy"), ("济南", "jn"), ("昆明", "km"), ("厦门", "xm"), ("福州", "fz"),
    ("无锡", "wx"), ("珠海", "zh"), ("哈尔滨", "hrb"), ("南宁", "nn"), ("中山", "zs"),
    ("温州", "wz"), ("石家庄", "sjz"), ("南昌", "nc"), ("贵阳", "gy"), ("兰州", "lz"),
    ("海口", "hk"), ("太原", "ty"), ("南通", "nt"), ("嘉兴", "jx"), ("保定", "bd"),
    ("烟台", "yt"), ("潍坊", "wf"), ("扬州", "yz"), ("镇江", "zj"), ("唐山", "ts"),
    ("廊坊", "lf"), ("襄阳", "xy"), ("泉州", "quanzhou"), ("泰州", "taizhou"),
    ("芜湖", "wuhu"), ("赣州", "ganzhou"), ("湛江", "zhanjiang"), ("绍兴", "sx"),
    ("昆山", "ks"),
]


def parse_ke_item(li, city):
    """解析贝壳单条房源 li -> House 字段 dict 或 None(解析不出关键信息则丢弃)。"""
    title_el = li.select_one('.title a')
    if not title_el:
        return None
    title = title_el.get_text(strip=True)
    href = title_el.get('href', '')
    if href and not href.startswith('http'):
        href = 'https://ke.com' + href

    community_el = li.select_one('.positionInfo a')
    community = community_el.get_text(strip=True) if community_el else None

    price_el = li.select_one('.totalPrice span')
    price = to_float(price_el.get_text()) if price_el else None
    unit_el = li.select_one('.unitPrice span')
    unit = to_float(unit_el.get_text()) if unit_el else None

    house_info_el = li.select_one('.houseInfo')
    info_text = house_info_el.get_text(" ", strip=True) if house_info_el else ''
    if not info_text:
        return None

    m = re.search(r'(\d+室\d+厅)', info_text)
    rooms = normalize_layout(m.group(1)) if m else None
    am = re.search(r'([\d.]+)\s*平米', info_text)
    area = float(am.group(1)) if am else None
    parts = [p.strip() for p in info_text.split('|')]
    orientation = parts[-1] if parts else None
    floor_info = parse_floor(info_text)

    if price is None or area is None or area <= 0:
        return None

    desc = (
        f"{title}，位于{community or '未知小区'}，{rooms or ''}，{orientation or ''}朝向，"
        f"{floor_info or ''}，建筑面积{area:.1f}平米，总价{price}万，"
        f"单价约{int(unit) if unit else 0}元/平。"
    )
    return dict(
        city=city, region=None, community=community, title=title,
        price=price, unit_price=unit, area=area, rooms=rooms,
        floor_info=floor_info, orientation=orientation,
        decoration=None, building_year=None, description=desc, url=href,
    )


def fetch_page(code, page):
    url = f"https://{code}.ke.com/ershoufang/pg{page}/"
    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers=HEADERS, timeout=20, proxies=NO_PROXY)
        resp.encoding = 'utf-8'
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'lxml')
        items = soup.select('.sellListContent li, .listContent li')
        return items
    except Exception as e:
        print(f"    ⚠️ 请求失败: {e}")
        return None


def import_city(city, code, max_pages, db):
    """真实-only 抓取单城。关键健壮性：
      - 提交前按 url 批量预查去重，绝不因重复 URL 触发 IntegrityError；
      - 单批提交失败(任意异常)即 db.rollback() 并跳过该批，绝不污染 session；
      - 某页空/被反爬拦截就停该城，绝不造假填充。
    返回本城新增真实房源数。
    """
    saved = 0
    year = datetime.datetime.now().year
    empty_streak = 0
    for page in range(1, max_pages + 1):
        items = fetch_page(code, page)
        if not items:
            empty_streak += 1
            if empty_streak >= 2:
                break
            time.sleep(random.uniform(1.5, 3.0))
            continue
        empty_streak = 0
        batch = []
        for li in items:
            fields = parse_ke_item(li, city)
            if fields is None:
                continue
            batch.append(fields)
        if not batch:
            time.sleep(random.uniform(1.5, 3.5))
            continue
        # 去重：剔除库中已存在的 url（幂等，可重复运行）
        urls = [b['url'] for b in batch]
        try:
            existing = {r[0] for r in db.query(House.url).filter(House.url.in_(urls)).all()}
        except Exception:
            existing = set()
        batch = [b for b in batch if b['url'] not in existing]
        if not batch:
            time.sleep(random.uniform(1.5, 3.5))
            continue
        objs = [House(
            city=b['city'], region=b['region'],
            community=b['community'], year=year, title=b['title'],
            price=b['price'], unit_price=b['unit_price'],
            area=b['area'], rooms=b['rooms'],
            floor_info=b['floor_info'], orientation=b['orientation'],
            decoration=b['decoration'], building_year=b['building_year'],
            property_type='二手房', description=b['description'],
            url=b['url'],
        ) for b in batch]
        try:
            db.add_all(objs)
            db.commit()
            saved += len(objs)
            print(f"    pg{page}: +{len(objs)} 条 (累计 {saved})")
        except Exception as e:
            # 单批失败只回滚本批，session 恢复后继续下一页/下一城
            db.rollback()
            print(f"    ⚠️ pg{page} 提交失败(已回滚跳过): {e}")
        time.sleep(random.uniform(1.5, 3.5))
    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=10, help='每城最多抓取的页数')
    parser.add_argument('--cities', type=str, default='', help='限定城市(中文逗号分隔)，默认全部')
    args = parser.parse_args()

    # 北京/上海已有数十万条真实成交(来自 CSV 数据集)，无需再用贝壳补，
    # 跳过以省时、避免稀释；其余城市一律实时直爬真实房源。
    SKIP = {'北京', '上海'}
    cities = [(c, code) for (c, code) in CITY_LIST if c not in SKIP]
    if args.cities:
        want = set(c.strip() for c in args.cities.split(',') if c.strip())
        cities = [c for c in cities if c[0] in want]
        if not cities:
            print(f"⚠️ 限定城市 {args.cities} 不在已验证列表中，退出")
            return

    init_db()
    migrate_db()
    db = SessionLocal()

    total = 0
    for i, (city, code) in enumerate(cities, 1):
        print(f"\n🏙️ [{i}/{len(cities)}] {city}({code})")
        try:
            n = import_city(city, code, args.pages, db)
            total += n
            print(f"  ✅ {city}: 新增 {n} 条真实房源")
        except Exception as e:
            # 整城异常：回滚 + 继续下一城，绝不因一城失败中断全量
            try:
                db.rollback()
            except Exception:
                pass
            print(f"  ⚠️ {city} 中断(已跳过): {e}")
        time.sleep(random.uniform(2.0, 4.0))

    db.close()
    print(f"\n🎉 抓取完成: 共新增 {total} 条真实二手房房源（零合成）")


if __name__ == "__main__":
    main()
