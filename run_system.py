# run_system.py
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

import subprocess
import time
import multiprocessing
import requests
import sys
import signal
import atexit
import socket

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_HOST = os.environ.get('API_HOST', '0.0.0.0')
API_PORT = int(os.environ.get('API_PORT', '8000'))
API_URL = f'http://127.0.0.1:{API_PORT}'
DASHBOARD_HOST = os.environ.get('DASHBOARD_HOST', '127.0.0.1')
DASHBOARD_PORT = int(os.environ.get('DASHBOARD_PORT', '8050'))
HEALTH_CHECK_ENDPOINT = "/health"
MAX_RETRIES = 60
RETRY_INTERVAL = 1
TIMEOUT = 2


def is_port_in_use(port):
    """检测本机端口是否已被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def free_port_if_needed(port, name):
    """若端口被占，尝试找出占用进程并提示；返回 True 表示可继续，False 表示应退出"""
    if not is_port_in_use(port):
        return True
    print(f"⚠️ 端口 {port}（{name}）已被占用。尝试查找占用进程...")
    try:
        out = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if out:
            pids = out.split()
            print(f"   占用进程 PID: {', '.join(pids)}")
            print(f"   请先执行: lsof -ti :{port} | xargs kill -9")
            return False
    except Exception:
        pass
    print(f"   无法自动识别占用进程，请手动释放端口 {port} 后重试。")
    return False


def start_api():
    # 继承父进程终端，避免 PIPE 缓冲导致子进程因 BrokenPipe 退出
    # 使用独立进程组，便于整体回收，避免孤儿进程残留
    proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, 'api', 'main.py')],
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=BASE_DIR,
        start_new_session=True,
    )
    return proc


def wait_for_api():
    print("⏳ 等待后端启动并加载模型...")
    for i in range(MAX_RETRIES):
        try:
            resp = requests.get(API_URL + HEALTH_CHECK_ENDPOINT, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models_loaded", {})
                nlp_ok = data.get("nlp_engine", False)
                # 仅在全部模型就绪（status==ok）时才算启动完成
                if data.get("status") == "ok":
                    tag = "✅" if nlp_ok else "⚠️"
                    print(f"  {tag} NLP引擎: {'已加载' if nlp_ok else '未加载（非阻塞）'}")
                    for name, loaded in models.items():
                        tag = "✅" if loaded else "⚠️"
                        print(f"  {tag} {name}: {'已加载' if loaded else '未加载'}")
                    print("✅ 后端已就绪（全部模型加载完成）")
                    print(f"📡 API文档: {API_URL}/docs")
                    return True
                else:
                    # 仍在加载中，打印进度但不算完成
                    if (i + 1) % 5 == 0:
                        print(f"  ⏳ 模型预热中... NLP={'✅' if nlp_ok else '⏳'} "
                              f"趋势={'✅' if models.get('trend_predictor') else '⏳'} "
                              f"价格={'✅' if models.get('price_model') else '⏳'}")
        except requests.exceptions.RequestException:
            pass
        time.sleep(RETRY_INTERVAL)
        if (i + 1) % 10 == 0:
            print(f"  尝试 {i + 1}/{MAX_RETRIES}...")
    print("⚠️ 后端启动超时，但API可能仍在加载模型中")
    return True  # 不阻塞


def start_dashboard():
    # 继承父进程终端，避免 PIPE 缓冲导致子进程因 BrokenPipe 退出
    proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, 'dashboard', 'app.py')],
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=BASE_DIR,
        start_new_session=True,
    )
    return proc


def _kill_proc_group(proc, name):
    if proc is None:
        return
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except Exception:
            os.killpg(pgid, signal.SIGKILL)
        print(f"🛑 已停止 {name}")
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def main():
    print("🚀 正在启动房地产AI平台...")
    print("=" * 50)

    # 启动前预检端口，避免「端口被旧进程占用 → 死循环重启」
    if not free_port_if_needed(API_PORT, "后端"):
        sys.exit(1)
    if not free_port_if_needed(DASHBOARD_PORT, "看板"):
        sys.exit(1)

    api_proc = start_api()
    if not wait_for_api():
        _kill_proc_group(api_proc, "后端")
        sys.exit(1)

    print(f"✅ 后端已启动，访问 {API_URL}/docs 查看接口文档")

    dash_proc = start_dashboard()
    print(f"✅ 看板已启动，访问 http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")

    print("=" * 50)
    print("📱 前端开发服务器请手动启动:")
    print("   cd frontend && npm run dev")
    print("=" * 50)
    print("✅ 平台运行中，按 Ctrl+C 停止（关闭前会自动结束后端与看板）")

    # 注册退出时清理子进程组，避免残留
    atexit.register(_kill_proc_group, api_proc, "后端")
    atexit.register(_kill_proc_group, dash_proc, "看板")

    # 主进程常驻：仅在收到 SIGINT/SIGTERM 时退出
    procs = {"api": api_proc, "dash": dash_proc}
    stop = {"flag": False}

    def _handler(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    # 记录连续重启失败次数，避免端口占用时无限刷屏
    api_fail = 0
    dash_fail = 0

    try:
        while not stop["flag"]:
            if procs["api"].poll() is not None:
                code = procs["api"].returncode
                # 端口占用类错误（退出码 1）连续出现，直接停，避免死循环
                if code != 0:
                    api_fail += 1
                else:
                    api_fail = 0
                if api_fail >= 3:
                    print("❌ 后端连续启动失败，请检查端口占用或日志后重试。")
                    stop["flag"] = True
                    break
                print(f"⚠️ 后端进程已退出（退出码 {code}），3 秒后重启...")
                time.sleep(3)
                procs["api"] = start_api()
                wait_for_api()
            else:
                api_fail = 0

            if procs["dash"].poll() is not None:
                code = procs["dash"].returncode
                if code != 0:
                    dash_fail += 1
                else:
                    dash_fail = 0
                if dash_fail >= 3:
                    print("❌ 看板连续启动失败，请检查端口占用或日志后重试。")
                    stop["flag"] = True
                    break
                print(f"⚠️ 看板进程已退出（退出码 {code}），3 秒后重启...")
                time.sleep(3)
                procs["dash"] = start_dashboard()
            else:
                dash_fail = 0

            time.sleep(2)
    finally:
        _kill_proc_group(procs["api"], "后端")
        _kill_proc_group(procs["dash"], "看板")
        print("👋 已完全退出")


if __name__ == "__main__":
    main()
