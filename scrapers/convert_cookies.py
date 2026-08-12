"""把浏览器扩展(Cookie-Editor / EditThisCookie)导出的 JSON 转成 Playwright 可注入格式。

用法：
  1) 先在 Chrome 登录 lianjia.com，用 Cookie-Editor 扩展导出 JSON，存为 data/raw/lianjia_cookies_raw.json
  2) 运行本脚本 -> 生成 data/raw/lianjia_cookies.json（chengjiao_browser.py 直接读取）

也支持直接把导出内容命名为 lianjia_cookies.json 后用 --inplace 原地修复（不推荐，建议保留原始备份）。
"""
import os
import json
import argparse

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
SRC = os.path.join(RAW_DIR, "lianjia_cookies_raw.json")
DST = os.path.join(RAW_DIR, "lianjia_cookies.json")

SAME_SITE_MAP = {
    "no_restriction": "None",
    "unspecified": "Lax",
    "lax": "Lax",
    "strict": "Strict",
    None: "Lax",
}


def convert(cookies):
    out = []
    for c in cookies:
        exp = c.get("expirationDate")
        ss = SAME_SITE_MAP.get(c.get("sameSite"), "Lax")
        item = {
            "name": c.get("name"),
            "value": c.get("value"),
            "domain": c.get("domain", ".lianjia.com"),
            "path": c.get("path", "/"),
            "expires": int(exp) if exp else -1,
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure": bool(c.get("secure", False)),
            "sameSite": ss,
        }
        if not item["name"]:
            continue
        out.append(item)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--dst", default=DST)
    args = ap.parse_args()
    with open(args.src, encoding="utf-8") as f:
        raw = json.load(f)
    # 兼容两种导出：列表 或 {"cookies": [...]}
    if isinstance(raw, dict) and "cookies" in raw:
        raw = raw["cookies"]
    out = convert(raw)
    with open(args.dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 转换 {len(out)} 条 cookie -> {args.dst}")


if __name__ == "__main__":
    main()
