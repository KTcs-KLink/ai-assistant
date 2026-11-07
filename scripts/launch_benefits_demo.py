"""Launch the isolated benefit demo. Reuse .env privately without changing the original RAG."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=.3):
            return True
    except OSError:
        return False


def wait(port: int):
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        if listening(port):
            return
        time.sleep(.3)
    raise SystemExit("서버가 시작되지 않았습니다. .demo-logs/benefits의 로컬 기록을 확인하세요.")


def launch():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--api-port", type=int, default=8820)
    parser.add_argument("--web-port", type=int, default=8821)
    parser.add_argument("--env-file", type=Path, default=ROOT.parent / ".env")
    args = parser.parse_args()
    api_url = f"http://127.0.0.1:{args.api_port}"
    web_url = f"http://127.0.0.1:{args.web_port}/benefits"
    log_dir = ROOT / ".demo-logs/benefits"
    log_dir.mkdir(parents=True, exist_ok=True)
    processes = {}
    python = ROOT / "server/.venv/Scripts/python.exe"
    if not python.is_file():
        python = Path(sys.executable)
    env = os.environ.copy()
    env.update(KLINK_ENV_FILE=str(args.env_file.resolve()), KLINK_ALLOWED_ORIGINS=f"http://127.0.0.1:{args.web_port},http://localhost:{args.web_port}",
               KLINK_DATA_DIR=str(log_dir / "isolated-data"), KLINK_BENEFITS_DEMO="true")
    corpus = ROOT.parent / "outputs/kepco_hr_full_20261102/data/reviewed_units.jsonl"
    if corpus.is_file():
        env["KLINK_LOCAL_REVIEWED_UNITS"] = str(corpus)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    if not listening(args.api_port):
        with (log_dir / "api.log").open("a", encoding="utf-8") as log:
            proc = subprocess.Popen([str(python), "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", str(args.api_port), "--no-access-log"],
                                    cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=flags)
            processes["api"] = proc.pid
        wait(args.api_port)
    # Refuse a colliding, unrelated API rather than silently connect to it.
    try:
        with urlopen(api_url + "/api/benefits/config", timeout=15) as response:
            config = json.load(response)
        if config.get("catalog") != "synthetic":
            raise ValueError()
    except Exception:
        raise SystemExit("API 포트에서 K:LINK 혜택 서비스를 확인하지 못했습니다. 다른 포트를 지정하세요.") from None
    if not listening(args.web_port):
        node = shutil.which("node")
        vite = ROOT / "web/node_modules/vite/bin/vite.js"
        if not node or not vite.is_file():
            raise SystemExit("web 폴더의 프론트엔드 의존성 설치가 필요합니다.")
        web_env = os.environ.copy()
        web_env.update(VITE_API_BASE_URL=api_url, VITE_USE_MOCK="false")
        with (log_dir / "web.log").open("a", encoding="utf-8") as log:
            proc = subprocess.Popen([node, str(vite), "--host", "127.0.0.1", "--port", str(args.web_port), "--strictPort"],
                                    cwd=ROOT / "web", env=web_env, stdout=log, stderr=log, creationflags=flags)
            processes["web"] = proc.pid
        wait(args.web_port)
    if processes:
        (log_dir / "pids.json").write_text(json.dumps(processes), encoding="utf-8")
    print(web_url)
    print("가상 규정 시연입니다. 실제 KTcs 자격 검증과 신청은 연결되지 않았습니다.")
    if not args.no_open:
        webbrowser.open(web_url)


if __name__ == "__main__":
    launch()
