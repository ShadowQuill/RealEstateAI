"""探针：定位某城成交列表「翻到哪一页开始出现目标年份」，并确认目标年份在 100 页上限内可达。

用法：
  python scrapers/probe_year.py --cities 佛山 --human
  python scrapers/probe_year.py --cities 中山,苏州 --pages 30,55,80,100 --human

只读取、不写入数据库。每页打印首卡/末卡成交日期，用于判断：
  - 目标年份(默认2025)在 100 页内是否可达；
  - 边界大概在哪页（决定正式抓取从哪页翻到哪页）。
"""
import os
import sys
import re
import json
import time
import random
import argparse

sys.path.insert(0, os.getcwd())
from scrapers.chengjiao_browser import (SINGLE_YEAR_CITIES, COOKIE_PATH, UA, STEALTH_JS,
                                        extract_card)

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")


def probe_city(context, city, code, pages, human, target_year, area=None):
    page = context.new_page()
    scope = f"/{area}" if area else ""
    where = f"{city}({code}{scope})"
    print(f"\n🔍 探针 {where} 目标年={target_year} 探测页={pages}")
    for pg in pages:
        url = f"https://{code}.lianjia.com/chengjiao{scope}/pg{pg}/"
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"  pg{pg} 加载失败: {e}")
            break
        if any(k in page.url for k in ("forbidden", "clogin", "captcha", "login")):
            print(f"  pg{pg} 被风控/登录拦截: {page.url[:60]}")
            try:
                txt = page.content()
                if any(s in txt for s in ("访问已被拦截", "账号被临时封禁", "异常行为", "保护站点安全")):
                    print("  🚫 账号被临时封禁，停止探针。")
                    page.close()
                    return
            except Exception:
                pass
            if human:
                input("  ⏸ 手动过滑块后按回车重试本页:")
                try:
                    with open(COOKIE_PATH, "w", encoding="utf-8") as f:
                        json.dump(context.cookies(), f, ensure_ascii=False, indent=2)
                    print("  💾 已刷新 cookie")
                except Exception:
                    pass
                continue
            else:
                print("  → 停(用 --human 过验证)")
                break
        try:
            page.wait_for_selector(".listContent li .title a, .house-lst li .title a", timeout=15000)
        except Exception:
            print(f"  pg{pg} 未渲染列表，停")
            break
        page.wait_for_timeout(1200)
        cards = page.query_selector_all(".listContent li, .house-lst li")
        rows = [extract_card(c) for c in cards]
        rows = [r for r in rows if r]
        if not rows:
            print(f"  pg{pg}: 无有效卡片")
            continue
        yrs = [r["year"] for r in rows if r.get("year")]
        first, last = rows[0], rows[-1]
        print(f"  pg{pg}: 卡片={len(rows)} 年份范围 {min(yrs)}~{max(yrs)}  "
              f"首卡={first.get('community')}({first.get('year')}) 末卡={last.get('community')}({last.get('year')})")
        # 若整页都已是目标年之前，无需再深翻
        if min(yrs) < target_year:
            print(f"  ✅ pg{pg} 已出现 <{target_year} 的成交，目标年可达（边界在此页之前）。")
    page.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", default="佛山")
    ap.add_argument("--pages", default="30,55,80,100", help="探测的页码(逗号分隔)")
    ap.add_argument("--year", type=int, default=2025, help="目标年份")
    ap.add_argument("--human", action="store_true")
    ap.add_argument("--area", default=None, help="按区域细分，如 chancheng/nanhai/shunde（突破单城100页上限）")
    args = ap.parse_args()

    want = set(c.strip() for c in args.cities.split(",") if c.strip())
    cities = {c: v for c, v in SINGLE_YEAR_CITIES.items() if c in want}
    pages = [int(x) for x in args.pages.split(",") if x.strip()]

    if not os.path.exists(COOKIE_PATH):
        print(f"⚠️ 未找到 {COOKIE_PATH}，请先 save_cookies.py 导出。")
        return

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False, channel="chrome",
            args=["--no-proxy-server", "--disable-blink-features=AutomationControlled", "--lang=zh-CN"],
        )
        context = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 768})
        context.add_init_script(STEALTH_JS)
        try:
            with open(COOKIE_PATH, encoding="utf-8") as f:
                context.add_cookies(json.load(f))
        except Exception as e:
            print(f"  ⚠️ 读取 cookie 失败: {e}")
        try:
            for city, code in cities.items():
                probe_city(context, city, code, pages, args.human, args.year, area=args.area)
        finally:
            context.close()
            browser.close()
    print("\n🏁 探针结束。")


if __name__ == "__main__":
    main()
