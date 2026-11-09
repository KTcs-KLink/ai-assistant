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
ENCODER_APP = "klink-kepco-query-encoder-20261107"


def encoder_ready(origin: str) -> bool:
    try:
        with urlopen(origin+"/health", timeout=2) as response:
            state = json.load(response)
        return (state.get("app_id") == ENCODER_APP and state.get("ready") is True
            and state.get("model") == "BAAI/bge-m3"
            and state.get("revision") == "5617a9f61b028005a4858fdac845db406aefb181"
            and state.get("weights_sha256") == "993b2248881724788dcab8c644a91dfd63584b6e5604ff2037cb5541e1e38e7e"
            and state.get("dimension") == 1024 and state.get("numeric_reference_state") == "PASSED"
            and state.get("parameter_readback_passed") is True
            and state.get("resident_encoder_layer_count") == 24)
    except (OSError, ValueError):
        return False


def ensure_encoder(port: int) -> str:
    origin = f"http://127.0.0.1:{port}"
    if listening(port):
        if not encoder_ready(origin):
            raise SystemExit("검색 포트를 다른 서비스가 사용 중이에요. 기존 프로그램은 종료하지 않았어요.")
        return origin
    interpreter = Path.home()/".cache/tooling/kepco-bge-m3-directml-20261029/Scripts/python.exe"
    if not interpreter.is_file():
        raise SystemExit("검증된 한전 검색용 Python 환경이 없어요. 의미 검색을 준비한 뒤 실행해 주세요.")
    logs = ROOT/".demo-logs/hr-quality-closeout"
    logs.mkdir(parents=True, exist_ok=True)
    # The encoder only needs public KEPCO text and model weights, never API or DB credentials.
    env = {k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ("OPENAI", "SUPABASE", "SECRET", "TOKEN", "PASSWORD", "API_KEY", "KLINK_ENV_FILE"))}
    env["PYTHONIOENCODING"] = "utf-8"
    with (logs/"encoder.log").open("a", encoding="utf-8") as out, (logs/"encoder-error.log").open("a", encoding="utf-8") as error:
        proc = subprocess.Popen([str(interpreter), str(ROOT/"scripts/serve_kepco_query_encoder.py"), "--port", str(port)],
            cwd=ROOT, env=env, stdout=out, stderr=error,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    (logs/"encoder-process.json").write_text(json.dumps({"pid":proc.pid,"port":port,"app_id":ENCODER_APP}), encoding="utf-8")
    deadline = time.monotonic()+180
    while time.monotonic() < deadline:
        if encoder_ready(origin):return origin
        if proc.poll() is not None:
            raise SystemExit("한전 검색 모델이 시작되지 않았어요. 로컬 실행 기록을 확인해 주세요.")
        time.sleep(.5)
    raise SystemExit("한전 검색 모델 준비 시간을 초과했어요. 준비 전에는 답변을 생성하지 않아요.")


def listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=.3):
            return True
    except OSError:
        return False


def marker(origin: str, retrieval: str | None = None, understanding: str | None = None, source_scope: str | None = None, review_domains: str | None = None) -> bool:
    try:
        with urlopen(origin+"/api/benefits/hr/capabilities", timeout=2) as response:
            state = json.load(response)
            return (state.get("app") == "KLINK_HR_DOMAIN" and (retrieval is None or state.get("retrieval_mode") == retrieval)
                and (understanding is None or state.get("question_understanding") == understanding)
                and (source_scope is None or state.get('source_scope') == source_scope)
                and (review_domains is None or state.get('review_domains') == review_domains))
    except (OSError, ValueError):
        return False


def launch():
    parser = argparse.ArgumentParser(description="K:LINK 인사 도메인 연결 확인")
    parser.add_argument("--port", type=int, default=8826)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--retrieval", choices=["hybrid", "bm25"], default="hybrid")
    parser.add_argument("--encoder-port", type=int, default=8841)
    parser.add_argument("--understanding", choices=["llm", "off"], default="llm")
    parser.add_argument("--source-scope", choices=["baseline", "expanded"], default="expanded")
    parser.add_argument("--review-domains", choices=["baseline", "reclassified"], default="reclassified")
    args = parser.parse_args()
    if args.source_scope=='baseline':args.review_domains='baseline'
    if not 1024 <= args.port <= 65535 or not 1024 <= args.encoder_port <= 65535 or args.port == args.encoder_port:
        raise SystemExit("1024~65535 사이 포트를 지정해 주세요.")
    origin = f"http://127.0.0.1:{args.port}"
    if args.source_scope == 'expanded' and not (ROOT.parent/'outputs/klink_hr_source_expansion_20261107/source-manifest-v2.json').is_file():
        raise SystemExit('확장 원문 검증 기록이 없어요. scripts/audit_hr_source_expansion.py를 먼저 실행해 주세요.')
    if args.review_domains=='reclassified' and not (ROOT.parent/'outputs/klink_hr_reclassification_20261108/domain-review-search.sqlite3').is_file():
        raise SystemExit('인사 재분류 검색 파일이 아직 준비되지 않았어요. 이전 범위 비교는 --review-domains baseline으로 실행할 수 있어요.')
    encoder_origin = ensure_encoder(args.encoder_port) if args.retrieval == "hybrid" else ""
    if listening(args.port):
        if not marker(origin, args.retrieval, args.understanding, args.source_scope, args.review_domains):
            raise SystemExit("이 포트에는 다른 버전 또는 다른 프로그램이 실행 중이에요. --port로 다른 번호를 지정해 주세요.")
    else:
        interpreter = ROOT/"server/.venv/Scripts/python.exe"
        if not interpreter.is_file():
            interpreter = Path(sys.executable)
        logs = ROOT/".demo-logs/hr-domain"
        logs.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        allowed = os.getenv("KLINK_HR_ALLOWED_ORIGINS") or ",".join([origin, "http://127.0.0.1:8824", "http://localhost:8824"])
        env.update(KLINK_ENV_FILE=str(ROOT.parent/".env"), KLINK_DATA_DIR=str(logs/f"isolated-data-{args.port}"),
            KLINK_BENEFITS_DEMO="true", KLINK_ALLOWED_ORIGINS=allowed, PYTHONIOENCODING="utf-8",
            KLINK_HR_RETRIEVAL=args.retrieval, KLINK_HR_ENCODER_URL=encoder_origin, KLINK_HR_INTENT_MODE=args.understanding,
            KLINK_HR_SOURCE_SCOPE=args.source_scope,
            KLINK_HR_REVIEW_DOMAINS=args.review_domains,
            OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
        corpus = ROOT.parent/"outputs/kepco_hr_full_20261102/data/reviewed_units.jsonl"
        if corpus.is_file():
            env["KLINK_LOCAL_REVIEWED_UNITS"] = str(corpus)
        with (logs/"server.log").open("a", encoding="utf-8") as log:
            proc = subprocess.Popen([str(interpreter), "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1",
                "--port", str(args.port), "--no-access-log"], cwd=ROOT, env=env, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        (logs/f"process-{args.port}.json").write_text(json.dumps({"pid":proc.pid,"port":args.port,"source_scope":args.source_scope,"review_domains":args.review_domains}), encoding="utf-8")
        deadline = time.monotonic()+35
        while time.monotonic() < deadline:
            if marker(origin, args.retrieval, args.understanding, args.source_scope, args.review_domains):
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
