"""Launch this checkout's local query encoder and HR BFF without touching older services."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from http.cookiejar import CookieJar
import socket
import subprocess
import sys
import time
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT.parent
LOGS = ROOT / ".demo-logs/hr-vector-chat"


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=.3):
            return True
    except OSError:
        return False


def get_json(url):
    try:
        with urlopen(url, timeout=3) as response:
            return json.load(response)
    except (OSError, ValueError):
        return {}


def encoder_ready(port):
    data = get_json(f"http://127.0.0.1:{port}/health")
    return (data.get("app") == "KLINK_HR_QUERY_ENCODER" and data.get("ready") is True
            and data.get("model") == "BAAI/bge-m3" and data.get("dimension") == 1024
            and data.get("revision") == "5617a9f61b028005a4858fdac845db406aefb181"
            and data.get("weights_sha256") == "993b2248881724788dcab8c644a91dfd63584b6e5604ff2037cb5541e1e38e7e"
            and data.get("pooling") == "CLS_then_FP32_L2" and data.get("truncation") is False
            and data.get("query_cache_preloaded") is False)


def bff_ready(port):
    data = get_json(f"http://127.0.0.1:{port}/api/benefits/hr/capabilities")
    return data.get("app") == "KLINK_HR_DOMAIN" and data.get("answer_retrieval") == "local_bge_m3_dense"


def start(command, env, filename, port):
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / filename).open("a", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    (LOGS / f"process-{port}.json").write_text(json.dumps(dict(pid=process.pid, port=port,
        cwd=str(ROOT))), encoding="utf-8")
    return process


def await_ready(process, probe, port, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if probe(port):
            return
        if process.poll() is not None:
            raise SystemExit("로컬 챗봇 실행을 확인하지 못했어요. 이 체크아웃의 .demo-logs/hr-vector-chat 기록을 확인해 주세요.")
        time.sleep(.5)
    raise SystemExit("로컬 모델 준비 시간이 길어졌어요. 실행 기록을 확인한 뒤 다시 시작해 주세요.")


def warm_sources(port):
    """Warm read-only source/numeric checks with a disposable empty demo session.

    No example profile, employee login, cloud-store check or LLM request.
    Cookie values remain in this in-memory jar and are never printed or saved.
    """
    origin = f"http://127.0.0.1:{port}"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    headers = {"Origin": origin, "Content-Type": "application/json"}
    try:
        with opener.open(Request(origin + "/api/benefits/session/demo", data=b"{}", headers=headers), timeout=10):
            pass
        with opener.open(origin + "/api/benefits/hr/retrieval/status", timeout=180) as response:
            status = json.load(response)
        if status.get("ready") is not True:
            raise ValueError("source checks not ready")
    except (OSError, ValueError):
        raise SystemExit("로컬 원문과 질문 모델의 호환 확인을 완료하지 못했어요. 실행 기록을 확인해 주세요.") from None
    finally:
        try:
            with opener.open(Request(origin + "/api/benefits/session", headers=headers, method="DELETE"), timeout=10):
                pass
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8833)
    parser.add_argument("--encoder-port", type=int, default=8832)
    args = parser.parse_args()
    if args.port == args.encoder_port or not all(1024 <= p <= 65535 for p in [args.port, args.encoder_port]):
        raise SystemExit("서로 다른 유효한 서비스 번호가 필요합니다.")
    index = DATA_ROOT / "outputs/kepco_hr_full_eval_960_20261102/indexes"
    windows = DATA_ROOT / "outputs/kepco_hr_full_20261102/indexes/windows.jsonl"
    corpus = DATA_ROOT / "outputs/kepco_hr_full_20261102/data/reviewed_units.jsonl"
    if not all(p.is_file() for p in [corpus, index / "windows.npy", index / "windows_vectors.json", windows]):
        raise SystemExit("기존 로컬 원문과 BGE-M3 임베딩 색인이 필요해요. 자료를 새로 만들거나 다른 데이터로 대체하지 않았습니다.")
    env = os.environ.copy()
    env.update(PYTHONIOENCODING="utf-8", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    if listening(args.encoder_port):
        if not encoder_ready(args.encoder_port):
            raise SystemExit("다른 서비스가 질문 임베딩 주소를 사용 중입니다. 기존 서비스를 변경하지 않았습니다.")
    else:
        interpreter = Path(os.getenv("KLINK_BGE_PYTHON") or
                           str(Path.home() / ".cache/tooling/kepco-bge-m3-directml-20261029/Scripts/python.exe"))
        if not interpreter.is_file():
            raise SystemExit("기존 BGE-M3 DirectML 실행 환경을 찾지 못했어요. KLINK_BGE_PYTHON을 확인해 주세요.")
        print("기존 로컬 BGE-M3 질문 임베딩 모델을 준비하고 있어요.", flush=True)
        encoder = start([str(interpreter), "-X", "utf8", "-m", "server.hr_embedding_service",
                         "--port", str(args.encoder_port)], env, "encoder.log", args.encoder_port)
        await_ready(encoder, encoder_ready, args.encoder_port, 180)
    if listening(args.port):
        if not bff_ready(args.port):
            raise SystemExit("다른 서비스가 챗봇 주소를 사용 중입니다. 기존 서비스를 변경하지 않았습니다.")
    else:
        origin = f"http://127.0.0.1:{args.port}"
        env.update(KLINK_ENV_FILE=str(DATA_ROOT / ".env"), KLINK_DATA_DIR=str(LOGS / "isolated-data"),
                   KLINK_BENEFITS_DEMO="true", KLINK_LOCAL_REVIEWED_UNITS=str(corpus),
                   KLINK_HR_RETRIEVAL="dense", KLINK_HR_VECTOR_INDEX=str(index),
                   KLINK_HR_VECTOR_WINDOWS=str(windows),
                   KLINK_HR_ENCODER_URL=f"http://127.0.0.1:{args.encoder_port}",
                   KLINK_ALLOWED_ORIGINS=",".join([origin, "http://127.0.0.1:8825", "http://127.0.0.1:8824"]))
        backend = start([sys.executable, "-X", "utf8", "-m", "uvicorn", "server.app:app", "--host",
                         "127.0.0.1", "--port", str(args.port), "--no-access-log"], env, "server.log", args.port)
        await_ready(backend, bff_ready, args.port, 40)
    print("로컬 색인과 질문 모델의 호환성을 확인하고 있어요.", flush=True)
    warm_sources(args.port)
    print("로컬 질문 임베딩 → 실제 청크 검색 → 지정 LLM 경로 준비 완료.", flush=True)
    print(f"인사 API: http://127.0.0.1:{args.port}", flush=True)


if __name__ == "__main__":
    main()
