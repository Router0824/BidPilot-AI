#!/usr/bin/env python3
import getpass
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BACKEND_PORT = os.environ.get("BIDPILOT_BACKEND_PORT", "8000")
FRONTEND_PORT = os.environ.get("BIDPILOT_FRONTEND_PORT", "5173")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes", "是", "啟用", "启用")


def build_backend_env() -> dict:
    env = os.environ.copy()
    use_real_api = ask_yes_no("是否啟用真實 DeepSeek API？選否將使用 mock，不消耗 API", default=False)
    if use_real_api:
        env["BIDPILOT_LLM_PROVIDER"] = "deepseek"
        env.setdefault("BIDPILOT_LLM_BASE_URL", "https://api.deepseek.com")
        env.setdefault("BIDPILOT_LLM_FAST_MODEL", "deepseek-v4-flash")
        env.setdefault("BIDPILOT_LLM_QUALITY_MODEL", "deepseek-v4-pro")
        if not env.get("BIDPILOT_LLM_API_KEY"):
            key = getpass.getpass("請輸入 DeepSeek API Key（不會保存）: ").strip()
            if key:
                env["BIDPILOT_LLM_API_KEY"] = key
            else:
                print("未輸入 API Key，已切回 mock 模式。")
                env["BIDPILOT_LLM_PROVIDER"] = "mock"
    else:
        env["BIDPILOT_LLM_PROVIDER"] = "mock"
        env.pop("BIDPILOT_LLM_API_KEY", None)
    return env


def ensure_frontend_deps() -> None:
    if not (FRONTEND / "node_modules").exists():
        print("首次啟動：正在安裝前端依賴...")
        subprocess.run(["npm", "install"], cwd=FRONTEND, check=True)


def port_in_use(port: str) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def start_processes(env: dict) -> list[subprocess.Popen]:
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        BACKEND_PORT,
        "--reload",
    ]
    frontend_cmd = ["npm", "run", "dev", "--", "--port", FRONTEND_PORT]

    processes = []
    if port_in_use(BACKEND_PORT):
        print(f"\n後端端口 {BACKEND_PORT} 已在使用，將復用現有後端。")
    else:
        print("\n啟動後端 FastAPI...")
        processes.append(subprocess.Popen(backend_cmd, cwd=ROOT, env=env))
        time.sleep(1.2)

    if port_in_use(FRONTEND_PORT):
        print(f"前端端口 {FRONTEND_PORT} 已在使用，將復用現有前端。")
    else:
        print("啟動前端 Vite...")
        processes.append(subprocess.Popen(frontend_cmd, cwd=FRONTEND, env=os.environ.copy()))
    return processes


def stop_processes(processes: list[subprocess.Popen]) -> None:
    for proc in processes:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
    deadline = time.time() + 8
    for proc in processes:
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.2)
        if proc.poll() is None:
            proc.terminate()


def main() -> int:
    print("BidPilot 一鍵開發啟動器")
    print(f"專案目錄：{ROOT}")
    env = build_backend_env()
    ensure_frontend_deps()
    processes = start_processes(env)

    provider = env.get("BIDPILOT_LLM_PROVIDER", "mock")
    print("\n已啟動：")
    print(f"- 後端：http://127.0.0.1:{BACKEND_PORT}")
    print(f"- 前端：http://localhost:{FRONTEND_PORT}")
    print(f"- LLM：{provider}")
    print("\n按 Ctrl+C 可同時停止前後端。\n")
    if not processes:
        print("前後端都已經在運行，本次啟動器不接管現有進程。")
        return 0

    try:
        while True:
            for proc in processes:
                code = proc.poll()
                if code is not None:
                    stop_processes(processes)
                    return code
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n正在停止前後端...")
        stop_processes(processes)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
