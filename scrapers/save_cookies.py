"""无需浏览器扩展：用 Playwright 打开真实 Chrome 窗口，你手动登录链家，
脚本自动把当前所有 cookie 导出为 Playwright 可直接注入的 JSON。

为什么这样最省事：
  - 登录态 token 大多是 httpOnly，JS 书签读取不到；本脚本从浏览器上下文
    直接取 context.cookies()，能完整拿到登录态。
  - 导出格式与 chengjiao_browser.py 的 add_cookies() 完全兼容，无需再转换。

用法：
  python scrapers/save_cookies.py
  1) 会自动弹出 Chrome 窗口并打开 lianjia.com
  2) 你在窗口里登录（手机验证码）
  3) 回到终端按回车
  4) 自动生成 data/raw/lianjia_cookies.json
"""
import os
import json
import time

# ---- 强制直连：关掉本地代理 ----
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_k, None)

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)
DST = os.path.join(RAW_DIR, "lianjia_cookies.json")
USER_DATA = os.path.join(RAW_DIR, "chrome_profile")  # 持久化登录态，下次还能复用


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        # 持久化上下文：登录态会保存在 USER_DATA，方便复用
        context = pw.chromium.launch_persistent_context(
            USER_DATA,
            headless=False,
            channel="chrome",
            args=["--no-proxy-server", "--lang=zh-CN"],
            locale="zh-CN",
        )
        page = context.new_page()
        print("🌐 正在打开 lianjia.com ... 请在弹出的 Chrome 窗口中登录。")
        try:
            page.goto("https://www.lianjia.com/", timeout=30000)
        except Exception as e:
            print(f"⚠️ 打开页面出错: {e}")

        input("\n✅ 登录完成后，回到这里按回车导出 Cookie（若已登录可直接回车）...\n")

        # 确保停留在链家域再取 cookie（只取 lianjia.com 相关）
        try:
            if "lianjia" not in page.url:
                page.goto("https://www.lianjia.com/", timeout=30000)
                time.sleep(2)
        except Exception:
            pass

        cookies = context.cookies()
        # 过滤掉明显无关域，仅保留 lianjia / ke 域
        cookies = [c for c in cookies if "lianjia" in c.get("domain", "") or "ke.com" in c.get("domain", "")]
        with open(DST, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"✅ 已导出 {len(cookies)} 条 cookie -> {DST}")
        print("   接下来即可运行：python scrapers/chengjiao_browser.py --test 中山")
        context.close()


if __name__ == "__main__":
    main()
