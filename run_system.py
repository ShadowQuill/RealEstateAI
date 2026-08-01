# run_system.py
import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 配置文件
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import subprocess
import time
import multiprocessing
import requests
import sys

API_URL = os.environ.get('API_BASE_URL', 'http://127.0.0.1:8000')
DASHBOARD_PORT = os.environ.get('DASHBOARD_PORT', '8050')
HEALTH_CHECK_ENDPOINT = "/health"
MAX_RETRIES = 40
RETRY_INTERVAL = 1
TIMEOUT = 2


def start_api():
    proc = subprocess.Popen(
        ["python", "api/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return proc


def wait_for_api():
    print("⏳ 等待后端启动并加载模型...")
    for i in range(MAX_RETRIES):
        try:
            resp = requests.get(API_URL + HEALTH_CHECK_ENDPOINT, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok":
                    print("✅ 后端已就绪，模型加载完成")
                    return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(RETRY_INTERVAL)
        print(f"  尝试 {i + 1}/{MAX_RETRIES}...")
    print("❌ 后端启动或模型加载超时")
    return False


def start_dashboard():
    proc = subprocess.Popen(
        ["python", "dashboard/app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return proc


if __name__ == "__main__":
    print("🚀 正在启动房地产AI平台...")
    api_proc = start_api()
    if not wait_for_api():
        api_proc.terminate()
        sys.exit(1)

    # 🔽 新增：后端成功启动后打印访问地址
    print(f"✅ 后端已启动，访问 {API_URL}/docs 查看接口文档")

    dash_proc = start_dashboard()
    print(f"✅ 看板已启动，访问 http://127.0.0.1:{DASHBOARD_PORT}")

    try:
        api_proc.wait()
        dash_proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 收到中断信号，正在关闭...")
        api_proc.terminate()
        dash_proc.terminate()
        api_proc.wait()
        dash_proc.wait()
        print("已退出")