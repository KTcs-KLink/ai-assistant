"""Start the EXISTING KTCS 960-question local demo and open the K:LINK UI.

This launcher does not alter source documents, embeddings, local index, or .env.
It cannot replace the original app if its dependencies/index are unavailable.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import webbrowser


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def wait_for_port(port: int, *, seconds: int = 35) -> bool:
    for _ in range(max(1, seconds * 2)):
        if port_open(port):
            return True
        time.sleep(0.5)
    return False


def python_for(demo: Path, root: Path) -> str:
    candidates = [
        demo / ".venv/Scripts/python.exe",
        root / ".venv/Scripts/python.exe",
        root / "venv/Scripts/python.exe",
        root / "runtime_venv/Scripts/python.exe",
        demo / ".venv/bin/python",
        root / ".venv/bin/python",
    ]
    return str(next((p for p in candidates if p.is_file()), Path(sys.executable)))


def find_app_entry(demo: Path) -> Path | None:
    preferred = [
        "run_demo.py", "start_demo.py", "serve.py", "app.py", "main.py",
        "server.py", "demo.py", "run.py", "web_app.py", "streamlit_app.py",
        "src/app.py", "src/main.py",
    ]
    for name in preferred:
        path = demo / name
        if path.is_file():
            return path
    possible = []
    for path in sorted(demo.rglob("*.py")):
        if any(piece in {"venv", ".venv", "site-packages", "__pycache__", "tests"}
               for piece in path.relative_to(demo).parts):
            continue
        if len(path.relative_to(demo).parts) > 3:
            continue
        code = path.read_text("utf-8", errors="replace")[:200_000]
        if re.search(r"FastAPI\s*\(|\bstreamlit\b|uvicorn\.run\s*\(|Flask\s*\(|HTTPServer\s*\(", code):
            possible.append(path)
        if len(possible) >= 5:
            break
    return possible[0] if len(possible) == 1 else None


def original_launch(demo: Path, root: Path, port: int) -> tuple[list[str], Path]:
    for name in ("start.ps1", "run.ps1"):
        if (demo / name).is_file():
            return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(demo / name)], demo
    for name in ("start.cmd", "run.cmd", "start.bat", "run.bat"):
        if (demo / name).is_file():
            return ["cmd.exe", "/c", str(demo / name)], demo
    entry = find_app_entry(demo)
    if entry is None:
        candidates = [p.name for p in demo.iterdir() if p.is_file() and p.suffix.lower() in {".py", ".ps1", ".cmd", ".bat"}]
        raise RuntimeError("원본 앱 시작 파일을 판별할 수 없습니다. 확인된 실행 파일: " + ", ".join(candidates))
    python = python_for(demo, root)
    code = entry.read_text("utf-8", errors="replace")[:200_000]
    if re.search(r"(?:\bstreamlit\b|import\s+streamlit)", code):
        return [python, "-m", "streamlit", "run", str(entry), "--server.address", "127.0.0.1", "--server.port", str(port)], entry.parent
    if re.search(r"uvicorn\.run\s*\(|app\.run\s*\(|HTTPServer\s*\(", code):
        return [python, str(entry)], entry.parent
    if re.search(r"FastAPI\s*\(", code):
        return [python, "-m", "uvicorn", entry.stem + ":app", "--host", "127.0.0.1", "--port", str(port)], entry.parent
    return [python, str(entry)], entry.parent


def start_logged(cmd: list[str], cwd: Path, logdir: Path, name: str, env: dict[str, str] | None = None) -> subprocess.Popen:
    stdout = logdir / f"{name}.stdout.log"
    stderr = logdir / f"{name}.stderr.log"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with stdout.open("ab") as out, stderr.open("ab") as err:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=out, stderr=err, creationflags=creationflags)
    print(f"{name} PID={proc.pid}; 오류 로그: {stderr}")
    return proc


def log_tail(path: Path, max_lines: int = 22) -> None:
    if path.is_file():
        lines = path.read_text("utf-8", errors="replace").splitlines()
        print("\n".join(lines[-max_lines:]))


def main() -> int:
    parser = argparse.ArgumentParser(description="기존 960문항 로컬 RAG와 K:LINK 웹을 실행하고 브라우저를 엽니다.")
    default_root = Path.home() / "OneDrive" / "문서" / "ChatGPT" / "KTCS"
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--original-app", type=Path, default=None)
    parser.add_argument("--original-port", type=int, default=8811)
    parser.add_argument("--web-port", type=int, default=5173)
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    demo = (args.original_app or root / "chat" / "kepco_hr_demo_20261102").resolve()
    repo = Path(__file__).resolve().parent.parent
    web = repo / "web"
    print(f"KTCS 로컬 프로젝트: {root}")
    print(f"기존 RAG 앱: {demo}")
    print(f"새 K:LINK 프런트: {web}")
    if not demo.is_dir():
        raise RuntimeError(f"기존 960문항 시연 앱 폴더가 없습니다: {demo}")
    if not (web / "package.json").is_file():
        raise RuntimeError(f"K:LINK 웹 폴더가 없습니다: {web}")
    print("원본 앱 주요 파일:", ", ".join(p.name for p in sorted(demo.iterdir())
          if p.is_file() and p.suffix.lower() in {".py", ".ps1", ".md", ".toml", ".txt"})[:800])
    if args.inspect_only:
        print("읽기 전용 확인만 수행했습니다. 파일·인덱스·서버는 변경하지 않았습니다.")
        return 0
    logs = repo / ".demo-logs"
    logs.mkdir(exist_ok=True)

    if not port_open(args.original_port):
        cmd, cwd = original_launch(demo, root, args.original_port)
        print("기존 RAG 시연 앱을 실행합니다:", cmd[0], Path(cmd[-1]).name)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(root), str(demo), env.get("PYTHONPATH", "")]))
        start_logged(cmd, cwd, logs, "original-rag", env)
        if not wait_for_port(args.original_port):
            print(f"원본 RAG가 포트 {args.original_port} 에서 실행되지 않았습니다. 로그 마지막 부분:")
            log_tail(logs / "original-rag.stderr.log")
            raise RuntimeError("기존 RAG 서버 실행 실패. 원본 앱의 실행 명령/의존성 확인이 필요합니다.")
    print(f"원본 RAG HTTP 포트 열림: http://127.0.0.1:{args.original_port}/ (인덱스 로딩/답변 성공은 별도 확인 필요)")

    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("npm 명령을 찾지 못했습니다. Node.js 22 이상이 필요합니다.")
    if not (web / "node_modules").exists():
        print("기존 웹 dependencies 설치 중...")
        subprocess.run([npm, "ci"], cwd=web, check=True)
    env = os.environ.copy()
    env["VITE_USE_MOCK"] = "false"
    env["VITE_KTCS_ORIGINAL_DEMO_URL"] = f"http://127.0.0.1:{args.original_port}/"
    if not port_open(args.web_port):
        start_logged([npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(args.web_port), "--strictPort"], web, logs, "klink-web", env)
        if not wait_for_port(args.web_port):
            print("프런트엔드가 실행되지 않았습니다. 로그 마지막 부분:")
            log_tail(logs / "klink-web.stderr.log")
            raise RuntimeError("K:LINK 웹 실행 실패")
    url = f"http://127.0.0.1:{args.web_port}/original-data-demo"
    print(f"K:LINK 화면을 엽니다: {url}")
    webbrowser.open(url, new=2)
    print(f"브라우저의 iframe이 차단되면 원본 앱을 직접 여세요: http://127.0.0.1:{args.original_port}/")
    print("기존 데이터/벡터는 복사하거나 수정하지 않았습니다. Supabase에도 적재하지 않았습니다.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"실행 오류: {exc}", file=sys.stderr)
        raise SystemExit(1)
