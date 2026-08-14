"""浏览器自动化抓取各城二手房「成交」(chengjiao) 真实历史数据。

为什么需要本脚本：
  贝壳/链家「成交」频道需要登录态（裸请求被登录网关拦截），且对自动化浏览器
  做风控（403 Forbidden）。本脚本用 Playwright 驱动系统 Chrome + 反指纹 stealth +
  用户提供的登录 cookie，尽量绕过风控，抓取各城多年真实成交价。

重要约束（与本项目一致）：
  - 仅存真实成交，零合成、零模拟、零回退。
  - 解析成交日期得到真实年份写入 houses(year=成交年)，用于趋势模型多年序列。
  - 某页被拦/空则停该城，绝不造假。

前置条件（用户手动准备）：
  1) 在本机已登录 lianjia.com 的 Chrome 浏览器里，用 DevTools → Application → Cookies
     导出 lianjia.com / ke.com 的 cookie 为 JSON（playwright 格式：
     [{"name":..., "value":..., "domain":..., "path":"/", ...}]），
     保存为 data/raw/lianjiao_cookies.json。
  2) 系统已安装 Google Chrome（playwright 用 channel="chrome" 驱动，无需下载 chromium）。

用法：
  python scrapers/chengjiao_browser.py                 # 抓全部 15 个单年城市(默认有头)
  python scrapers/chengjiao_browser.py --cities 中山,东莞
  python scrapers/chengjiao_browser.py --test                     # 只测默认首城(中山)一页，dump选择器
  python scrapers/chengjiao_browser.py --cities 中山 --test       # 同上，指定城市
  python scrapers/chengjiao_browser.py --cities 中山 --human      # 遇验证码暂停，手动完成后继续
  python scrapers/chengjiao_browser.py --cities 东莞 --start-page 4 --pages 30 --human  # 扩量：跳过已抓页，抓新页
  python scrapers/chengjiao_browser.py --cities 东莞 --start-page 24 --pages 30 --human --fast  # 快速模式续抓
  python scrapers/chengjiao_browser.py --cities 佛山 --year 2025 --pages 5 --human  # 补足历史年成交(解锁趋势真实成交)：仅返回2025成交，每城1-3页即可
  python scrapers/chengjiao_browser.py --cities 佛山,苏州 --sdate 2025-01-01 --bdate 2025-06-30 --pages 5 --human  # 指定日期区间
  python scrapers/chengjiao_browser.py --headless                # 无头模式(服务器用，更易被风控)

前置(必须有)：先运行 python scrapers/save_cookies.py 导出已登录 lianjia.com 的 cookie，
否则未登录请求会被 hip.lianjia.com/captcha 拦截，无法抓取。
"""
import os
import sys
import re
import json
import time
import random
import argparse
import datetime

sys.path.insert(0, os.getcwd())

# ---- 强制直连：关掉本地代理（贝壳直连可达，代理会 502/拦截）----
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_k, None)

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
COOKIE_PATH = os.path.join(RAW_DIR, "lianjia_cookies.json")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "realestate.db")

# 14 个单年城市 -> 贝壳/链家城市码
# 注：泰州(tz) 链家无独立站(tz.lianjia.com 解析失败)，已剔除；该城保持原单年快照/邻城指数。
SINGLE_YEAR_CITIES = {
    "中山": "zs", "东莞": "dg", "苏州": "su", "保定": "bd", "南通": "nt",
    "嘉兴": "jx", "廊坊": "lf", "昆山": "ks", "潍坊": "wf",
    "珠海": "zh", "绍兴": "sx", "芜湖": "wuhu", "镇江": "zj", "佛山": "fs",
}

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
const origQ = navigator.permissions && navigator.permissions.query;
if (origQ) { navigator.permissions.query = (p) => (p.name === 'notifications' ? Promise.resolve({state:'denied',onchange:null}) : origQ(p)); }
const origAD = Object.getOwnPropertyDescriptor(Navigator.prototype, 'languages');
if (origAD) Object.defineProperty(Navigator.prototype, 'languages', { get: () => ['zh-CN','zh'] });
"""

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def to_float(v):
    try:
        return float(str(v).replace("万", "").replace("元", "").replace("平米", "")
                      .replace("平", "").replace(",", "").strip())
    except Exception:
        return None


def parse_deal_year(s):
    m = re.search(r"(\d{4})", str(s or ""))
    return int(m.group(1)) if m else None


def normalize_layout(s):
    s = str(s or "")
    m = re.search(r"(\d+)\s*室\s*(\d+)\s*厅", s)
    if m:
        return f"{m.group(1)}室{m.group(2)}厅"
    return s.strip() or None


def parse_floor(s):
    s = str(s or "")
    if "高" in s:
        return "高楼层"
    if "中" in s:
        return "中楼层"
    if "低" in s:
        return "低楼层"
    if "地下" in s:
        return "地下"
    return None


def extract_card(card):
    """从一条成交卡片抽取字段；解析失败返回 None。

    贝壳成交卡片结构特点：户型+面积常拼在标题里（如「汇翠山庄桃源居 3室2厅 124.7平米」），
    而 .houseInfo 通常只剩朝向/装修。故面积/户型/小区名优先从标题解析，houseInfo 作补充。
    """
    try:
        title_a = card.query_selector(".title a") or card.query_selector("a.title")
        title = title_a.inner_text().strip() if title_a else ""
        # 小区名：优先 .positionInfo a，否则从标题去尾（去掉"3室2厅 124.7平米"）
        comm_a = card.query_selector(".positionInfo a") or card.query_selector(".houseInfo a")
        community = comm_a.inner_text().strip() if comm_a else ""
        if not community:
            m_comm = re.match(r"^(.*?)\s*\d+\s*室", title)
            community = m_comm.group(1).strip() if m_comm else title
        # 面积/户型：优先从标题提取（贝壳把"124.7平米 / 3室2厅"放进标题）
        area = None
        m_area = re.search(r"([\d.]+)\s*平米", title)
        if m_area:
            area = to_float(m_area.group(1))
        rooms = None
        m_rooms = re.search(r"(\d+)\s*室\s*(\d+)\s*厅", title)
        if m_rooms:
            rooms = f"{m_rooms.group(1)}室{m_rooms.group(2)}厅"
        # 总价（万）—— 兼容「有内层 span」与「直接写在 .totalPrice 内」两种结构
        tp = card.query_selector(".totalPrice span") or card.query_selector(".totalPrice")
        price = to_float(tp.inner_text()) if tp else None
        # 单价（元/平）—— 同上，兼容有无内层 span
        up = card.query_selector(".unitPrice span") or card.query_selector(".unitPrice")
        unit = to_float(up.inner_text()) if up else None
        # 成交日期
        dd = card.query_selector(".dealDate")
        deal = dd.inner_text().strip() if dd else ""
        year = parse_deal_year(deal)
        # houseInfo：朝向 | 装修 | 楼层 | 建成年份（面积/户型已在标题取过，这里补充）
        hi = card.query_selector(".houseInfo")
        hi_text = hi.inner_text() if hi else ""
        parts = [p.strip() for p in re.split(r"[|｜]", hi_text) if p.strip()]
        orientation = decoration = floor_info = building_year = None
        for p in parts:
            if "室" in p and "厅" in p:
                rooms = normalize_layout(p)
            elif "平米" in p or "平" in p:
                area = to_float(p)
            elif "朝向" in p or p in ("东", "南", "西", "北", "东南", "东北", "西南", "西北"):
                orientation = p.replace("朝向", "").strip() or None
            elif p in ("精装", "简装", "毛坯", "其他", "豪装"):
                decoration = p
            elif "楼层" in p:
                floor_info = parse_floor(p)
            elif re.search(r"\d{4}年", p) or re.match(r"^\d{4}$", p):
                by = re.search(r"(\d{4})", p)
                building_year = int(by.group(1)) if by else None
        # 价格允许缺失（异步渲染/部分城市结构差异），但面积与年份为趋势模型必需，缺一不可
        if area is None or area <= 0 or year is None:
            return None
        # 单价兜底：用总价(万)/面积 折算
        if unit is None and price and area:
            unit = price * 10000.0 / area
        # 真实房源ID：从成交详情链接解析（用于精准去重，避免合成 url 无法判重）
        deal_id = None
        if title_a:
            href = title_a.get_attribute("href") or ""
            m = re.search(r"/chengjiao/([^/]+?)\.html", href) or re.search(r"/chengjiao/(\w+)", href)
            if m:
                deal_id = m.group(1)
        return {
            "title": title, "community": community, "price": price, "unit_price": unit,
            "year": year, "area": area, "rooms": rooms, "orientation": orientation,
            "decoration": decoration, "floor_info": floor_info, "building_year": building_year,
            "deal_id": deal_id,
        }
    except Exception:
        return None


def insert_batch(db, city, rows):
    cur = db.cursor()
    now = datetime.datetime.now().isoformat()
    n = 0
    for i, r in enumerate(rows):
        url = f"chengjiao://{city}/{i}-{r['community']}-{r['year']}"
        try:
            cur.execute(
                """INSERT OR IGNORE INTO houses
                   (city, region, community, year, title, price, unit_price, area, rooms,
                    floor_info, orientation, decoration, building_year,
                    property_type, description, url, deal_id, crawled_at, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (city, None, r["community"], r["year"], r["title"], r["price"], r["unit_price"],
                 r["area"], r["rooms"], r["floor_info"], r["orientation"], r["decoration"],
                 r["building_year"], "二手房成交", r["title"], url, r.get("deal_id"), now, now),
            )
            n += 1
        except Exception:
            pass
    db.commit()
    return n


def fetch_city(context, city, code, max_pages, test=False, human=False, start_page=1, fast=False, sdate=None, bdate=None, area=None):
    page = context.new_page()
    saved = 0
    pg = start_page
    resumed = False  # 手动过验证后跳过重新 goto，直接复用已渲染的当前页
    scope = f"/{area}" if area else ""
    while pg <= max_pages:
        url = f"https://{code}.lianjia.com/chengjiao{scope}/pg{pg}/"
        if sdate and bdate:
            url += f"?sDate={sdate}&bDate={bdate}"  # 年份/日期筛选：直接返回该时段成交，避免深翻
        if not resumed:
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
            except Exception as e:
                print(f"  {city} pg{pg} 加载失败: {e}")
                break
        else:
            resumed = False
        if any(k in page.url for k in ("forbidden", "clogin", "captcha", "login")):
            print(f"  {city} pg{pg} 被风控/登录拦截: {page.url[:60]}")
            # 检测账号级封禁（比普通滑块更严重，重试无意义且会延长封禁）
            banned = False
            try:
                txt = page.content()
                if any(s in txt for s in ("访问已被拦截", "账号被临时封禁", "异常行为", "保护站点安全")):
                    banned = True
            except Exception:
                pass
            if banned:
                print(f"  🚫 检测到账号被临时封禁！请停止抓取、等待自动解封，勿频繁重试（重试会延长封禁）。")
                try:
                    page.screenshot(path=os.path.join(RAW_DIR, f"banned_{city}.png"))
                except Exception:
                    pass
                break
            try:
                page.screenshot(path=os.path.join(RAW_DIR, f"captcha_{city}.png"))
            except Exception:
                pass
            if human:
                input(f"  ⏸ 请在该 Chrome 窗口手动完成验证(滑块)后，回到这里按回车重试本页:")
                # 验证通过后把最新 cookie 写回文件，后续城市/下次运行有望免验证
                try:
                    with open(COOKIE_PATH, "w", encoding="utf-8") as f:
                        json.dump(context.cookies(), f, ensure_ascii=False, indent=2)
                    print(f"  💾 已刷新 cookie -> {COOKIE_PATH}")
                except Exception:
                    pass
                resumed = True  # 复用当前(已验证)页面，不再重新 goto
                continue  # 重试当前页（pg 不变）
            print(f"  → 停该城（可用 --human 手动过验证，或先确认 cookie 已注入）")
            break
        try:
            # 等到具体卡片元素(而非空壳容器)，确保 JS 已渲染出房源
            page.wait_for_selector(
                ".listContent li .title a, .house-lst li .title a",
                timeout=15000,
            )
        except Exception:
            print(f"  {city} pg{pg} 未渲染出列表，停  url={page.url[:70]}")
            try:
                with open(os.path.join(RAW_DIR, f"debug_{city}_pg{pg}.html"), "w", encoding="utf-8") as fh:
                    fh.write(page.content()[:3000])
                print(f"  📝 已dump页面诊断 -> data/raw/debug_{city}_pg{pg}.html")
            except Exception:
                pass
            break
        # 价格/日期可能异步晚于标题渲染，先等它们出现（城市间结构差异大，超时即放手让 extract_card 兜底）
        for sel in (".totalPrice", ".dealDate", ".unitPrice"):
            try:
                page.wait_for_selector(f".listContent li {sel}, .house-lst li {sel}", timeout=6000)
            except Exception:
                pass
        page.wait_for_timeout(500 if fast else 1500)  # 兜底等懒加载图片/卡片补齐（fast 缩短）
        cards = page.query_selector_all(".listContent li, .house-lst li")
        if test:
            print(f"  [TEST] {city} pg{pg}: 卡片数={len(cards)} url={page.url[:60]}")
            if cards:
                print("  首卡HTML:", cards[0].inner_html()[:800])
            # 打印时间/筛选相关的链接，帮助定位正确的年份筛选 URL（链家用 co 条件码而非 query 参数）
            # 用 textContent 抓隐藏(折叠下拉)选项的文本
            try:
                import re as _re
                anchors = page.query_selector_all("a[href*='chengjiao']")
                seen = set()
                for a in anchors:
                    t = (a.get_attribute("textContent") or a.inner_html() or "").strip()
                    h = a.get_attribute("href") or ""
                    if _re.search(r"2025|2024|2023|时间|不限|近\s*\d+\s*月", t) and h not in seen:
                        seen.add(h)
                        print(f"  [FILTER-LINK] text={t!r} href={h}")
            except Exception as e:
                print("  filter-link 提取失败:", e)
            # 打印所有下拉容器 HTML，暴露自定义下拉里的年份选项
            try:
                for sel in (".dropdown", "div[class*='dropdown']", "div[class*='time']",
                            "div[class*='sort']", "ul[class*='dropdown']", "div[class*='select']",
                            ".list-box", ".sort"):
                    for el in page.query_selector_all(sel):
                        html = el.inner_html() or ""
                        if ("2025" in html) or ("2024" in html) or ("时间" in html) or ("近" in html and "月" in html):
                            print(f"  [DROPDOWN {sel}]", html[:1500].replace("\n", " "))
            except Exception as e:
                print("  dropdown 提取失败:", e)
            try:
                for sel in (".filters", ".screen", ".filter", "div[class*='filter']", ".list-box", ".sec-bottom"):
                    el = page.query_selector(sel)
                    if el:
                        print(f"  [FILTER-HTML {sel}]", el.inner_html()[:600].replace("\n", " "))
            except Exception:
                pass
            # 专门打印所有 <select> 下拉及其选项（成交时间筛选通常是 select）
            try:
                selects = page.query_selector_all("select")
                for si, s in enumerate(selects):
                    cls = s.get_attribute("class") or ""
                    name = s.get_attribute("name") or ""
                    print(f"  [SELECT #{si}] class={cls!r} name={name!r}")
                    for o in s.query_selector_all("option"):
                        print(f"      option value={o.get_attribute('value')!r} text={o.inner_text().strip()!r}")
            except Exception as e:
                print("  select 提取失败:", e)
            page.close()
            return 0
        rows = [extract_card(c) for c in cards]
        rows = [r for r in rows if r]
        if not rows:
            print(f"  {city} pg{pg} 无有效卡片，停  url={page.url[:70]}")
            cards0 = page.query_selector_all(".listContent li, .house-lst li")
            if cards0:
                c0 = cards0[0]
                tp = c0.query_selector(".totalPrice span") or c0.query_selector(".totalPrice")
                dd = c0.query_selector(".dealDate")
                print("  诊断 首卡: "
                      f"title={c0.query_selector('.title a').inner_text()[:30] if c0.query_selector('.title a') else None!r} "
                      f"totalPrice={tp.inner_text() if tp else None!r} "
                      f"dealDate={dd.inner_text() if dd else None!r}")
                try:
                    with open(os.path.join(RAW_DIR, f"debug_{city}_pg{pg}_card.html"), "w", encoding="utf-8") as fh:
                        fh.write(c0.inner_html())
                    print(f"  📝 已dump首卡完整HTML -> data/raw/debug_{city}_pg{pg}_card.html")
                except Exception:
                    pass
            break
        saved += insert_batch(db_conn(), city, rows)
        print(f"    {city} pg{pg}: +{len(rows)} (累计 {saved})")
        pg += 1
        time.sleep(random.uniform(2.0, 4.0) if fast else random.uniform(8.0, 15.0))  # 页间间隔（fast 提速）
    page.close()
    return saved


_db = None


def db_conn():
    global _db
    if _db is None:
        import sqlite3
        _db = sqlite3.connect(DB_PATH)
    return _db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", default="", help="限定城市(中文逗号分隔)，默认全部单年城市")
    ap.add_argument("--pages", type=int, default=15, help="每城最多页数(上限)")
    ap.add_argument("--start-page", type=int, default=1, help="起始页(默认1)；扩量重跑时设 4 跳过已抓页、避免重复触发验证码")
    ap.add_argument("--test", action="store_true", help="只加载首城首页并dump选择器，用于调参")
    ap.add_argument("--human", action="store_true", help="遇验证码暂停，等手动完成验证后再继续")
    ap.add_argument("--headless", action="store_true", help="无头模式(默认有头，更易过风控/手动验证)")
    ap.add_argument("--fast", action="store_true", help="快速模式：页间间隔 8-15s→2-4s、城市间 5-10s→2-3s（换新号/赶进度时用，封号风险略增）")
    ap.add_argument("--year", type=int, default=0, help="限定成交年份(如 2025)；自动设 sDate/bDate 为该年1/1-12/31（链家已证实忽略此参数，请用 --area 深翻）")
    ap.add_argument("--sdate", default="", help="成交起始日期 YYYY-MM-DD（与 --bdate 配套；链家成交页忽略 query 参数）")
    ap.add_argument("--bdate", default="", help="成交截止日期 YYYY-MM-DD")
    ap.add_argument("--area", default=None, help="按区域/街道细分，如 chancheng/nanhai/shunde（突破单城100页上限，深翻到历史年）")
    args = ap.parse_args()
    if args.test and not args.cities:
        args.cities = "中山"  # 单测默认首城

    # 年份/日期筛选参数解析（用于补足历史年成交）
    sdate, bdate = args.sdate, args.bdate
    if (not sdate) and args.year:
        sdate, bdate = f"{args.year}-01-01", f"{args.year}-12-31"

    cities = SINGLE_YEAR_CITIES
    if args.cities:
        want = set(c.strip() for c in args.cities.split(",") if c.strip())
        cities = {c: v for c, v in SINGLE_YEAR_CITIES.items() if c in want}

    if not os.path.exists(COOKIE_PATH):
        print(f"⚠️ 未找到 {COOKIE_PATH}（需你导出已登录 lianjia.com 的 cookie）。\n"
              f"   没有登录态，成交页会被登录墙拦截，无法抓取。请先准备 cookie 文件。")
        # 仍进入 test 模式帮助用户调参（会被拦，但能看到现象）
        if not args.test:
            return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=args.headless, channel="chrome",
            args=["--no-proxy-server", "--disable-blink-features=AutomationControlled", "--lang=zh-CN"],
        )
        # 共享一个 context：登录态/验证态跨城市复用，通常只需手动验证一次
        context = browser.new_context(
            user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 768},
        )
        context.add_init_script(STEALTH_JS)
        try:
            with open(COOKIE_PATH, encoding="utf-8") as f:
                context.add_cookies(json.load(f))
        except Exception as e:
            print(f"  ⚠️ 读取 cookie 失败: {e}")
        total = 0
        try:
            for i, (city, code) in enumerate(cities.items(), 1):
                print(f"\n🏙️ [{i}/{len(cities)}] {city}({code})")
                try:
                    n = fetch_city(context, city, code, args.pages, test=args.test, human=args.human, start_page=args.start_page, fast=args.fast, sdate=sdate, bdate=bdate, area=args.area)
                    total += n
                    print(f"  ✅ {city}: 新增 {n} 条真实成交")
                except Exception as e:
                    print(f"  ⚠️ {city} 中断: {e}")
                time.sleep(random.uniform(2.0, 3.0) if args.fast else random.uniform(5.0, 10.0))  # 城市间间隔（fast 提速）
                if args.test:
                    break
        finally:
            context.close()
            browser.close()
            if _db:
                _db.close()
    print(f"\n🎉 抓取完成: 共新增 {total} 条真实二手房成交（零合成）")


if __name__ == "__main__":
    main()
