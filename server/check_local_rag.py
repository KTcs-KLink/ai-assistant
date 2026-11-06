"""Read-only K:LINK local HR-RAG index/service diagnostics.

Does not read .env, print secrets, transmit files, or modify the original app.
It cannot prove that a live request uses a particular vector index. Instead
it displays which local code/data artifacts are present and whether 8811 responds.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def describe_store(root: Path):
    extensions = {".npy", ".npz", ".faiss", ".index", ".sqlite", ".sqlite3", ".db", ".pkl"}
    root = root.resolve()
    folders = [
        root / "work" / "kepco_hr_contextual_20261102",
        root / "chat" / "kepco_hr_demo_20261102",
        root / "outputs" / "kepco_hr_retrieval_960_20261102",
    ]
    stores = []
    for folder in folders:
        if not folder.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(folder):
            path = Path(dirpath)
            if len(path.relative_to(folder).parts) >= 5:
                dirnames[:] = []
            else:
                dirnames[:] = [n for n in dirnames if n not in {
                    ".venv", "venv", "__pycache__", ".git", "node_modules", "cache", "models"
                }]
            for filename in filenames:
                entry = path / filename
                if entry.suffix.lower() in extensions:
                    stores.append({
                        "relative_path": str(entry.relative_to(root)),
                        "size_mb": round(entry.stat().st_size / (1024 ** 2), 2),
                    })
                    if len(stores) >= 150:
                        return stores
    return stores


def service_status(port: int):
    url = f"http://127.0.0.1:{port}/"
    try:
        with urlopen(url, timeout=2) as response:
            return {"reachable": True, "http_status": response.status,
                    "note": "페이지 연결 성공, 인덱스 로드와 검색 성공까지 검증한 것은 아님"}
    except HTTPError as exc:
        return {"reachable": True, "http_status": exc.code,
                "note": "HTTP 서버가 응답했습니다. 앱 인증·라우팅을 확인하세요."}
    except (URLError, TimeoutError, OSError):
        return {"reachable": False, "http_status": None,
                "note": "로컬 8811 웹앱이 실행 중이지 않거나 접근되지 않습니다."}


def main():
    default = Path.home() / "OneDrive" / "문서" / "ChatGPT" / "KTCS"
    parser = argparse.ArgumentParser(description="K:LINK 로컬 인덱스 읽기 전용 진단")
    parser.add_argument("--root", type=Path, default=default)
    parser.add_argument("--port", type=int, default=8811)
    args = parser.parse_args()

    root = args.root.expanduser()
    if not root.is_dir():
        print(json.dumps({"project_root_exists": False, "expected_path": str(root)},
                         ensure_ascii=False, indent=2))
        return 2

    expected = {
        "existing_demo": (root / "chat" / "kepco_hr_demo_20261102").is_dir(),
        "original_core": (root / "work" / "kepco_hr_contextual_20261102" / "app_core.py").is_file(),
        "retrieval_960_output": (
            root / "outputs" / "kepco_hr_retrieval_960_20261102" / "summary.json"
        ).is_file(),
        "llm_960_output": (
            root / "outputs" / "kepco_hr_llm_eval_960_20261102" / "summary.json"
        ).is_file(),
    }
    report = {
        "project_root_exists": True,
        "original_project_components": expected,
        "candidate_vector_stores": describe_store(root),
        "local_server": service_status(args.port),
        "limits": [
            "인덱스 파일이 존재해도 현재 실행 중인 검색기가 읽는다는 보장은 없음",
            "GPU/모델 객체와 쿼리 임베딩·Top5 검색 로그는 원본 app_core 인터페이스를 확인한 후 검증 필요",
            "검토 승인 밖 문서는 검색 대상으로 추가하면 안 됨",
            "Supabase 적재 여부를 이 진단으로 확인할 수 없음",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
