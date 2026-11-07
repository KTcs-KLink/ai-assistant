"""Start an isolated, local-only HR integration workbench; keys are read by the server only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
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


def marker(origin: str) -> bool:
    try:
        with urlopen(origin+"/api/benefits/hr/capabilities", timeout=2) as response:
            return json.load(response).get("app") == "KLINK_HR_DOMAIN"
    except (OSError, ValueError):
        return False


def launch():
    parser = argparse.ArgumentParser(description="K:LINK 인사 도메인 연결 확인")
    parser.add_argument("--port", type=int, default=8826)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("1024~65535 사이 포트를 지정해 주세요.")
    origin = f"http://127.0.0.1:{args.port}"
    if listening(args.port):
        if not marker(origin):
            raise SystemExit("다른 프로그램이 포트를 사용 중이에요. --port로 다른 번호를 지정해 주세요.")
    else:
        interpreter = ROOT/"server/.venv/Scripts/python.exe"
        if not interpreter.is_file():
            interpreter = Path(sys.executable)
        logs = ROOT/".demo-logs/hr-domain"
        logs.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        allowed = os.getenv("KLINK_HR_ALLOWED_ORIGINS") or ",".join([origin, "http://127.0.0.1:8824", "http://localhost:8824"])
        env.update(KLINK_ENV_FILE=str(ROOT.parent/".env"), KLINK_DATA_DIR=str(logs/"isolated-data"),
            KLINK_BENEFITS_DEMO="true", KLINK_ALLOWED_ORIGINS=allowed, PYTHONIOENCODING="utf-8")
        corpus = ROOT.parent/"outputs/kepco_hr_full_20261102/data/reviewed_units.jsonl"
        if corpus.is_file():
            env["KLINK_LOCAL_REVIEWED_UNITS"] = str(corpus)
        with (logs/"server.log").open("a", encoding="utf-8") as log:
            proc = subprocess.Popen([str(interpreter), "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1",
                "--port", str(args.port), "--no-access-log"], cwd=ROOT, env=env, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        (logs/f"process-{args.port}.json").write_text(json.dumps({"pid":proc.pid,"port":args.port}), encoding="utf-8")
        deadline = time.monotonic()+35
        while time.monotonic() < deadline:
            if marker(origin):
                break
            if proc.poll() is not None:
                raise SystemExit("실행을 확인하지 못했어요. .demo-logs/hr-domain/server.log를 확인해 주세요.")
            time.sleep(.25)
        else:
            raise SystemExit("인사 도메인 연결을 확인하지 못했어요. 로컬 실행 기록을 확인해 주세요.")
    print(origin+"/hr-check")
    if not args.no_open:
        webbrowser.open(origin+"/hr-check")


if __name__ == "__main__":
    launch()
