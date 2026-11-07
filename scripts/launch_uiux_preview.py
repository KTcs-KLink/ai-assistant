"""Serve the frontend-only K:LINK design preview, without API or .env access."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def is_preview(origin: str) -> bool:
    try:
        with urlopen(origin + "/uiux-preview.json", timeout=2) as response:
            marker = json.load(response)
        return marker.get("app") == "klink-final-uiux" and marker.get("data") == "synthetic-only"
    except (OSError, ValueError):
        return False


def launch() -> None:
    parser = argparse.ArgumentParser(description="K:LINK UI/UX 미리보기")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--port", type=int, default=8822)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("1024~65535 사이의 포트를 선택해 주세요.")
    origin = f"http://127.0.0.1:{args.port}"
    url = origin + "/workspace"
    web = ROOT / "web"
    node = shutil.which("node")
    vite = web / "node_modules/vite/bin/vite.js"
    if not node or not vite.is_file():
        raise SystemExit("화면 실행 준비가 필요합니다. web 폴더에서 npm ci를 실행해 주세요.")
    if args.rebuild or not (web / "dist/uiux-preview.json").is_file():
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise SystemExit("Node.js와 npm을 먼저 설치해 주세요.")
        result = subprocess.run([npm, "run", "build"], cwd=web, check=False)
        if result.returncode:
            raise SystemExit("화면 빌드를 완료하지 못했습니다. 위 오류를 확인해 주세요.")
    if listening(args.port):
        if not is_preview(origin):
            raise SystemExit("다른 프로그램이 이 포트를 사용 중입니다. --port로 다른 번호를 지정해 주세요.")
    else:
        log_dir = ROOT / ".demo-logs/final-uiux"
        log_dir.mkdir(parents=True, exist_ok=True)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (log_dir / "preview.log").open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                [node, str(vite), "preview", "--host", "127.0.0.1", "--port", str(args.port), "--strictPort"],
                cwd=web, stdout=log, stderr=log, creationflags=flags,
            )
        (log_dir / f"preview-{args.port}.json").write_text(
            json.dumps({"pid": process.pid, "port": args.port, "mode": "frontend-only"}), encoding="utf-8",
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if is_preview(origin):
                break
            if process.poll() is not None:
                raise SystemExit("미리보기 실행이 종료됐습니다. .demo-logs/final-uiux/preview.log를 확인해 주세요.")
            time.sleep(0.2)
        else:
            raise SystemExit("미리보기를 확인하지 못했습니다. 잠시 후 다시 실행해 주세요.")
    print(url)
    print("가상 직원과 예시 규정으로 체험하는 UI/UX 시안입니다. 실제 신청은 제출되지 않습니다.")
    if not args.no_open:
        webbrowser.open(url)


if __name__ == "__main__":
    launch()
