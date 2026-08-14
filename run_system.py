# run_system.py
"""房地产 AI 平台一键启动 / 停止脚本。

启动（含前端）:  python run_system.py --with-frontend
启动（仅后端+看板）: python run_system.py
停止所有相关进程: python run_system.py --stop
"""
import os
import sys
import time
import signal
import socket
import shutil
import atexit
import argparse
import subprocess

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_HOST = os.environ.get('API_HOST', '0.0.0.0')
API_PORT = int(os.environ.get('API_PORT', '8000'))
API_URL = f'http://127.0.0.1:{API_PORT}'
DASHBOARD_HOST = os.environ.get('DASHBOARD_HOST', '127.0.0.1')
DASHBOARD_PORT = int(os.environ.get('DASHBOARD_PORT', '8050'))
FRONTEND_PORT = int(os.environ.get('FRONTEND_PORT', '5173'))

HEALTH_CHECK_ENDPOINT = "/health"
MAX_RETRIES = 60
RETRY_INTERVAL = 1
TIMEOUT = 2
MAX_CONSECUTIVE_FAILS = 3


# ANSI 颜色（终端可见；即使写入日志文件，也会用符号/框线保证醒目）
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_CYAN = "\033[36m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_RESET = "\033[0m"


def c(text, *codes):
    return "".join(codes) + text + C_RESET


def log(*args, **kwargs):
    """强制 flush，避免 nohup 重定向时日志看不到。"""
    print(*args, **kwargs, flush=True)


# ---------- 端口占用处理 ----------
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def _owners_of_port(port):
    try:
        out = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        return out.split() if out else []
    except Exception:
        return []


def kill_port_owners(port, silent=False):
    """终止占用 port 的所有进程；返回端口是否已被释放。"""
    pids = _owners_of_port(port)
    if not pids:
        return True
    if not silent:
        log(f"   🔪 将终止占用端口 {port} 的进程: {', '.join(pids)}")
    freed = True
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except Exception as e:
            log(f"   ⚠️ 无法终止进程 {pid}: {e}")
            freed = False
    if freed:
        time.sleep(1)
        return not is_port_in_use(port)
    return False


def free_port_if_needed(port, name, auto_kill=True):
    if not is_port_in_use(port):
        return True
    log(f"⚠️ 端口 {port}（{name}）已被占用。")
    if auto_kill:
        if kill_port_owners(port):
            log(f"✅ 已自动释放端口 {port}")
            return True
        log(f"❌ 无法自动释放端口 {port}，请手动处理后再试。")
        return False
    pids = _owners_of_port(port)
    if pids:
        log(f"   占用进程 PID: {', '.join(pids)}")
    log(f"   请先执行: lsof -ti :{port} | xargs kill -9")
    return False


# ---------- 进程启动 ----------
def _spawn(cmd, cwd=None):
    return subprocess.Popen(
        cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=cwd or BASE_DIR,
        start_new_session=True,
    )


def start_api():
    return _spawn([sys.executable, os.path.join(BASE_DIR, 'api', 'main.py')])


def start_dashboard():
    return _spawn([sys.executable, os.path.join(BASE_DIR, 'dashboard', 'app.py')])


def start_frontend(port):
    npm = shutil.which("npm")
    if not npm:
        log("⚠️ 未找到 npm，跳过前端启动。请先安装 Node.js。")
        return None
    fe_dir = os.path.join(BASE_DIR, 'frontend')
    if not os.path.isdir(fe_dir):
        log("⚠️ 未找到 frontend 目录，跳过前端启动。")
        return None
    return subprocess.Popen(
        [npm, "run", "dev", "--", "--port", str(port)],
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=fe_dir,
        start_new_session=True,
    )


# ---------- 健康检查 ----------
def wait_for_api():
    log("⏳ 等待后端启动并加载模型...")
    for i in range(MAX_RETRIES):
        try:
            resp = requests.get(API_URL + HEALTH_CHECK_ENDPOINT, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                nlp_ok = data.get("nlp_engine", False)
                if data.get("status") == "ok":
                    log(f"  {'✅' if nlp_ok else '⚠️'} NLP引擎: {'已加载' if nlp_ok else '未加载（非阻塞）'}")
                    for name, loaded in data.get("models_loaded", {}).items():
                        log(f"  {'✅' if loaded else '⚠️'} {name}: {'已加载' if loaded else '未加载'}")
                    log("✅ 后端已就绪（全部模型加载完成）")
                    log(f"📡 API文档: {API_URL}/docs")
                    return True
                if (i + 1) % 5 == 0:
                    m = data.get("models_loaded", {})
                    log(f"  ⏳ 模型预热中... NLP={'✅' if nlp_ok else '⏳'} "
                        f"趋势={'✅' if m.get('trend_predictor') else '⏳'} "
                        f"价格={'✅' if m.get('price_model') else '⏳'}")
        except Exception:
            pass
        time.sleep(RETRY_INTERVAL)
        if (i + 1) % 10 == 0:
            log(f"  尝试 {i + 1}/{MAX_RETRIES}...")
    log("⚠️ 后端健康检查超时，但 API 可能仍在加载模型中；继续启动其余服务。")
    return True  # 不阻塞其余服务的启动


# ---------- 进程组清理 ----------
def kill_proc_group(proc, name):
    if proc is None:
        return
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except Exception:
            os.killpg(pgid, signal.SIGKILL)
        log(f"🛑 已停止 {name}")
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ---------- 接管旧的 run_system 主进程，避免双主进程抢端口 ----------
def take_over():
    my_pid = os.getpid()
    try:
        out = subprocess.run(
            ["pgrep", "-f", "run_system.py"],
            capture_output=True, text=True
        ).stdout.strip()
        pids = [int(p) for p in out.split() if int(p) != my_pid]
    except Exception:
        return
    if not pids:
        return
    log(f"🔄 发现其它 run_system 实例 {pids}，先接管停止...")
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    time.sleep(3)


# ---------- 停止模式 ----------
def stop_all():
    log("🧹 正在停止房地产 AI 平台相关进程...")
    for port, name in [(API_PORT, "后端"), (DASHBOARD_PORT, "看板"), (FRONTEND_PORT, "前端")]:
        if is_port_in_use(port):
            kill_port_owners(port)
    # 清理可能残留的 run_system 常驻主进程（排除自己）
    my_pid = os.getpid()
    try:
        out = subprocess.run(
            ["pgrep", "-f", "run_system.py"],
            capture_output=True, text=True
        ).stdout.strip()
        for pid in out.split():
            pid = int(pid)
            if pid != my_pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    log(f"🛑 已停止 run_system 主进程 {pid}")
                except Exception:
                    pass
    except Exception:
        pass
    log("✅ 停止操作完成。")


# ---------- 主启动流程 ----------
def main():
    parser = argparse.ArgumentParser(description="房地产 AI 平台启动/停止脚本")
    parser.add_argument("--with-frontend", action="store_true",
                        help="同时启动前端开发服务器 (Vite)")
    parser.add_argument("--frontend-port", type=int, default=FRONTEND_PORT,
                        help=f"前端端口 (默认 {FRONTEND_PORT})")
    parser.add_argument("--no-autokill", action="store_true",
                        help="端口被占用时不自动终止占用进程（仅提示）")
    parser.add_argument("--stop", action="store_true",
                        help="停止所有平台相关进程并退出")
    args = parser.parse_args()

    if args.stop:
        stop_all()
        return

    fe_port = args.frontend_port
    log("🚀 正在启动房地产 AI 平台...")
    log("=" * 50)

    # 先接管可能残留的旧 run_system 主进程，避免双主进程竞态
    take_over()

    # 预检 + 自动释放端口
    if not free_port_if_needed(API_PORT, "后端", auto_kill=not args.no_autokill):
        sys.exit(1)
    if not free_port_if_needed(DASHBOARD_PORT, "看板", auto_kill=not args.no_autokill):
        sys.exit(1)
    if args.with_frontend:
        if not free_port_if_needed(fe_port, "前端", auto_kill=not args.no_autokill):
            sys.exit(1)

    # 先并行拉起全部服务，再等待 API 健康；
    # 这样即使主进程在等待期间被中断，子服务也已在运行，不会留下半成品/孤儿。
    procs = {"api": start_api()}
    log(f"🟢 后端启动中，访问 {API_URL}/docs")
    procs["dash"] = start_dashboard()
    log(f"🟢 看板启动中，访问 http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")

    fe_enabled = False
    if args.with_frontend:
        fe = start_frontend(fe_port)
        if fe is not None:
            procs["frontend"] = fe
            fe_enabled = True
            log(c(f"🟢 前端启动中 → http://localhost:{fe_port}", C_BOLD, C_CYAN))
    else:
        log(c("⚠️  前端【未启动】！网页界面依赖前端，请加 --with-frontend 启动。", C_BOLD, C_YELLOW))
        log(c("    启动方式（任选其一）：", C_YELLOW))
        log(c("    ① 一键带起前端: python run_system.py --with-frontend", C_YELLOW))
        log(c(f"    ② 手动启动:      cd frontend && npm run dev   (→ http://localhost:{fe_port})", C_YELLOW))

    # 等待 API 就绪（仅用于打印就绪信息，不阻塞其余服务）
    wait_for_api()

    log("=" * 50)
    log("✅ 平台运行中，按 Ctrl+C 停止（关闭前会自动结束所有子服务）")
    log(f"   🔌 后端 API : {API_URL}/docs")
    log(f"   📊 看板 Dash: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    log("-" * 50)
    if fe_enabled:
        log(c(f"   🌐 前端网页 → http://localhost:{fe_port}", C_BOLD, C_GREEN))
        log(c("      ↑ 这就是你要打开的网页界面（前端界面）", C_GREEN))
    else:
        log(c(f"   ⚠️  前端【未启动】！打开网页请用前端地址，而非上面的后端/看板。", C_BOLD, C_YELLOW))
        log(c(f"       重新运行: python run_system.py --with-frontend", C_YELLOW))
        log(c(f"       或手动:   cd frontend && npm run dev  → http://localhost:{fe_port}", C_YELLOW))
    log("=" * 50)

    fails = {k: 0 for k in procs}
    enabled = {k: True for k in procs}

    def cleanup():
        for k, p in procs.items():
            kill_proc_group(p, k)

    atexit.register(cleanup)
    stop = {"flag": False}

    def _handler(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    try:
        while not stop["flag"]:
            for name, proc in list(procs.items()):
                if not enabled[name]:
                    continue
                if proc.poll() is not None:
                    code = proc.returncode
                    fails[name] += 1
                    # 后端是核心：连续失败直接整体退出
                    if name == "api" and fails[name] >= MAX_CONSECUTIVE_FAILS:
                        log("❌ 后端连续启动失败，停止平台。")
                        stop["flag"] = True
                        break
                    if fails[name] >= MAX_CONSECUTIVE_FAILS:
                        log(f"⚠️ {name} 连续启动失败 {fails[name]} 次，停止自动重启该服务（其余服务继续运行）。")
                        enabled[name] = False
                        continue
                    log(f"⚠️ {name} 进程退出（码 {code}），3 秒后重启...")
                    time.sleep(3)
                    if name == "api":
                        procs[name] = start_api()
                    elif name == "dash":
                        procs[name] = start_dashboard()
                    elif name == "frontend":
                        fe = start_frontend(fe_port)
                        if fe:
                            procs[name] = fe
                        else:
                            enabled[name] = False
                else:
                    fails[name] = 0
            if stop["flag"]:
                break
            time.sleep(2)
    finally:
        cleanup()
        log("👋 已完全退出")


if __name__ == "__main__":
    main()
