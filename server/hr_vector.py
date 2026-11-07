"""Read-only BGE-M3 retrieval over existing windows, intersected with allowed HR sources.

No document embedding, gold-question cache, cloud database, or lexical fallback.
The complete reviewed source unit accompanies its matched window so exceptions
are not cut away merely to fit a retrieval window.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import time
from threading import Lock
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import numpy as np

try:
    from . import hr_evidence
except ImportError:
    import hr_evidence

MODEL = "BAAI/bge-m3"
REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
WEIGHTS = "993b2248881724788dcab8c644a91dfd63584b6e5604ff2037cb5541e1e38e7e"
DIMENSION = 1024
METHOD = "local_bge_m3_dense"
IDENTITY = dict(model=MODEL, revision=REVISION, weights_sha256=WEIGHTS,
                dimension=DIMENSION, pooling="CLS_then_FP32_L2", truncation=False)
NUMERIC_LOCK = Lock()


class VectorUnavailable(Exception):
    def __init__(self, message: str, code: str = "LOCAL_VECTOR_INDEX_UNAVAILABLE"):
        super().__init__(message)
        self.code = code


def enabled() -> bool:
    return os.getenv("KLINK_HR_RETRIEVAL", "lexical") == "dense"


def sha(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def identity_matches(value: dict) -> bool:
    return all(value.get(key) == expected for key, expected in IDENTITY.items())


def _signature(sources: list[dict]) -> tuple:
    keys = ("id", "sha256", "source_file_sha256", "version", "company", "employee_scope",
            "review_status", "effective_status", "human_approved", "ktcs_applicable")
    return tuple(tuple(s.get(key) for key in keys) for s in sources)


@lru_cache(maxsize=2)
def _load(directory: str, windows_path: str, file_stats: tuple, source_signature: tuple):
    folder = Path(directory)
    meta = json.loads((folder / "windows_vectors.json").read_text(encoding="utf-8"))
    if (not identity_matches(meta) or meta.get("normalized") is not True
            or meta.get("stored_vectors") != "FP32"
            or meta.get("encoder_runtime", {}).get("loader") != "CPU_WORD_GATHER_VERIFIED_OFFICIAL_ENCODER_LAYERS"):
        raise ValueError("index model identity")
    if sha(folder / "windows.npy") != meta["vectors_sha256"] or sha(Path(windows_path)) != meta["windows_sha256"]:
        raise ValueError("index file digest")
    with Path(windows_path).open(encoding="utf-8") as file:
        windows = [json.loads(line) for line in file if line.strip()]
    if (meta["ids"] != [w["id"] for w in windows] or len(set(meta["ids"])) != len(windows)
            or meta["rows"] != len(windows)):
        raise ValueError("index row identity")
    vectors = np.load(folder / "windows.npy", allow_pickle=False)
    if (vectors.shape != (len(windows), DIMENSION) or vectors.dtype != np.float32
            or not np.isfinite(vectors).all()
            or np.max(np.abs(np.linalg.norm(vectors, axis=1) - 1), initial=0) > 2e-4):
        raise ValueError("invalid stored vectors")
    sources = hr_evidence.corpus()[0]
    if _signature(sources) != source_signature:
        raise ValueError("source changed while loading index")
    allowed = {source["id"]: source for source in sources}
    selected, positions, covered = [], [], set()
    for position, window in enumerate(windows):
        source = allowed.get(window["unit_record_id"])
        if source is None:
            continue
        start, end = window["start"], window["end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source["text"]):
            raise ValueError("invalid source offset")
        text = source["text"][start:end]
        if (digest(source["text"]) != source["sha256"]
                or digest(text) != window["text_sha256"]
                or window["retrieval_text"] != source["title"] + " > " + source["section"] + "\n" + text
                or digest(window["retrieval_text"]) != window["retrieval_text_sha256"]
                or window["source_file_sha256"] != source.get("source_file_sha256")
                or window["answer_bundle_id"] != source["id"]):
            raise ValueError("window does not match allowed original")
        selected.append(dict(chunk_id=window["id"], source_id=source["id"], start=start, end=end,
                             text=text, sha256=window["text_sha256"], source_sha256=source["sha256"],
                             embedding_text_sha256=window["retrieval_text_sha256"]))
        positions.append(position)
        covered.add(source["id"])
    if not selected or covered != set(allowed):
        raise ValueError("allowed source coverage incomplete")
    selected_vectors = vectors[positions].copy()
    selected_vectors.setflags(write=False)
    return selected, selected_vectors, allowed, dict(window_count=len(selected), source_count=len(covered),
        stored_window_count=len(windows), vectors_sha256=meta["vectors_sha256"], windows_sha256=meta["windows_sha256"],
        read_only=True, scope="INTERSECTION_WITH_CURRENT_ALLOWED_HR_SOURCES")


def index():
    try:
        configured = os.getenv("KLINK_HR_VECTOR_INDEX")
        if not configured:
            raise ValueError("index not configured")
        directory = Path(configured).expanduser().resolve()
        windows = Path(os.getenv("KLINK_HR_VECTOR_WINDOWS") or directory / "windows.jsonl").expanduser().resolve()
        files = [directory / "windows_vectors.json", directory / "windows.npy", windows]
        stats = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in files)
        return _load(str(directory), str(windows), stats, _signature(hr_evidence.corpus()[0]))
    except (OSError, ValueError, KeyError, TypeError):
        raise VectorUnavailable("로컬 임베딩 색인과 허용 원문 연결을 확인하지 못했어요. 검색 결과를 대신 만들지 않습니다.") from None


def encoder_url() -> str:
    value = os.getenv("KLINK_HR_ENCODER_URL", "http://127.0.0.1:8832")
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise VectorUnavailable("로컬 질문 임베딩 서비스 주소를 확인해 주세요.", "LOCAL_ENCODER_UNAVAILABLE")
    return value


def _json(request, timeout: int) -> dict:
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("oversized encoder response")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("invalid encoder response")
        return data


def health() -> dict:
    try:
        data = _json(encoder_url() + "/health", 3)
        if (data.get("app") != "KLINK_HR_QUERY_ENCODER" or data.get("ready") is not True
                or not identity_matches(data) or data.get("query_cache_preloaded") is not False):
            raise ValueError("encoder identity mismatch")
        return data
    except (OSError, ValueError, KeyError):
        raise VectorUnavailable("로컬 질문 임베딩 모델이 준비되지 않았어요. 모델을 시작한 뒤 다시 질문해 주세요.", "LOCAL_ENCODER_UNAVAILABLE") from None


def embed(question: str) -> tuple[np.ndarray, dict]:
    health()
    try:
        request = Request(encoder_url() + "/embed", data=json.dumps({"text": question}).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
        started = time.perf_counter()
        data = _json(request, 60)
        if (not identity_matches(data) or data.get("computed") is not True or data.get("cached") is not False):
            raise ValueError("query model identity")
        vector = np.asarray(data["vector"], dtype=np.float32)
        if vector.shape != (DIMENSION,) or not np.isfinite(vector).all() or abs(float(np.linalg.norm(vector)) - 1) > 2e-4:
            raise ValueError("invalid query vector")
        return vector, dict(**IDENTITY, computed=True, cached=False, location="LOCAL_SERVER",
                            execution=data.get("execution"),
                            elapsed_ms=round((time.perf_counter() - started) * 1000, 2))
    except (OSError, ValueError, KeyError, TypeError):
        raise VectorUnavailable("질문을 실제로 임베딩하지 못해 답변 생성을 시작하지 않았어요.", "LOCAL_QUERY_EMBEDDING_FAILED") from None


@lru_cache(maxsize=2)
def _numeric_check(index_identity: tuple, encoder_instance: str) -> dict:
    windows, vectors, allowed, _ = index()
    ordered = sorted(range(len(windows)), key=lambda i: (len(windows[i]["text"]), windows[i]["chunk_id"]))
    positions = sorted(set([ordered[0], ordered[len(ordered) // 2], ordered[-1]]))
    cosines = []
    for position in positions:
        window = windows[position]
        source = allowed[window["source_id"]]
        text = source["title"] + " > " + source["section"] + "\n" + window["text"]
        vector, _ = embed(text)
        cosines.append(float(vectors[position] @ vector))
    if min(cosines) < .9999 or health().get("instance_id") != encoder_instance:
        raise VectorUnavailable("문서 벡터와 질문 모델의 수치 호환 검사를 통과하지 못해 생성을 보류했어요.", "LOCAL_VECTOR_SPACE_MISMATCH")
    return dict(sampled_windows=len(positions), minimum_cosine=round(min(cosines), 8),
                minimum_required=.9999, all_windows_reembedded=False)


def verified_index():
    loaded = index()
    service = health()
    instance = service.get("instance_id")
    if not isinstance(instance, str) or not instance:
        raise VectorUnavailable("질문 임베딩 서비스의 실행 상태를 확인하지 못했어요.", "LOCAL_ENCODER_UNAVAILABLE")
    metadata = loaded[3]
    key = (metadata["vectors_sha256"], metadata["windows_sha256"], _signature(list(loaded[2].values())))
    # React's initial status request can be repeated; tokenize startup controls
    # once per encoder instance instead of running the same controls concurrently.
    with NUMERIC_LOCK:
        numeric = _numeric_check(key, instance)
    return loaded, numeric


def retrieve(question: str, limit: int = 5) -> tuple[list[dict], dict]:
    if not 2 <= len(question.strip()) <= 500 or hr_evidence.PRIVATE.search(question):
        raise VectorUnavailable("개인정보나 키 없이 일반적인 인사 업무 질문을 입력해 주세요.", "INVALID_HR_QUERY")
    base = {**hr_evidence.summary(), "method": METHOD}
    if not hr_evidence.HR_TERMS.search(question):
        return [], dict(**base, status="OUT_OF_HR_SCOPE", matches=[], embedding=None)
    (windows, vectors, allowed, metadata), numeric = verified_index()
    query, embedding = embed(question)
    started = time.perf_counter()
    scores = vectors @ query
    # Rank actual windows first; retain the best window per complete source unit.
    order = sorted(range(len(windows)), key=lambda i: (-float(scores[i]), windows[i]["chunk_id"]))
    matches, sources, seen = [], [], set()
    for position in order:
        chunk = windows[position]
        if chunk["source_id"] in seen:
            continue
        seen.add(chunk["source_id"])
        matches.append(dict(**chunk, rank=len(matches) + 1, similarity=round(float(scores[position]), 6)))
        sources.append(dict(allowed[chunk["source_id"]]))
        if len(sources) >= max(1, min(limit, 5)):
            break
    return sources, dict(**base, status="RETRIEVED", embedding=embedding, index={**metadata, "numeric_compatibility": numeric},
        matches=matches, search_elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        source_delivery="MATCHED_WINDOWS_WITH_COMPLETE_REVIEWED_SOURCE_UNITS",
        source_unit_ids=[s["id"] for s in sources], lexical_fallback=False)


def status() -> dict:
    if not enabled():
        return dict(method="hr_lexical_bm25", ready=False, query_embedding=False)
    try:
        loaded, numeric = verified_index()
        metadata = {**loaded[3], "numeric_compatibility": numeric}
        return dict(method=METHOD, ready=True, query_embedding=True, **IDENTITY, index=metadata,
                    company="KEPCO", ktcs_applicable=False, human_approved=False)
    except VectorUnavailable as error:
        return dict(method=METHOD, ready=False, query_embedding=False, code=error.code, message=str(error))
