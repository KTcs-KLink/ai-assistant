"""Pinned, read-only corpus inputs; versioned staging outputs only."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from . import store

WORKSPACE = store.ROOT.parent
EXPANSION = WORKSPACE / "outputs/klink_hr_source_expansion_20261107"
CORPUS = WORKSPACE / "outputs/kepco_hr_full_20261102/data"
NORMALIZED = WORKSPACE / "outputs/kepco_parsed_normalized_20261025"
MANIFEST = EXPANSION / "source-manifest-v2.json"
MANIFEST_SHA = "12855f512460820948318914271662dbb453b24afb6ce57e81bf5427d0d440ab"
SOURCE_HOSTS = {"www.kepco.co.kr", "kepco.co.kr", "home.kepco.co.kr"}


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def allowed_url(url):
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.hostname in SOURCE_HOSTS and not parsed.username and not parsed.password and parsed.port in (None, 443)


def load():
    return _load(MANIFEST.stat().st_mtime_ns, (CORPUS / "reviewed_units.jsonl").stat().st_mtime_ns,
                 (CORPUS / "documents.jsonl").stat().st_mtime_ns,
                 (NORMALIZED / "data/documents.jsonl").stat().st_mtime_ns)


@lru_cache(maxsize=1)
def _load(*stamps):
    if sha_file(MANIFEST) != MANIFEST_SHA:
        raise ValueError("검증된 원문 범위 기록이 변경됐습니다. 자동 반영하지 않았습니다.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (manifest["company"] != "KEPCO" or manifest["human_approved"] is not False
            or manifest["ktcs_applicable"] is not False or manifest["supabase_ingestion"] != "HOLD"):
        raise ValueError("원문 회사·승인·적재 보류 범위를 확인할 수 없습니다.")
    for name, path in [("reviewed_units", CORPUS / "reviewed_units.jsonl"), ("documents", CORPUS / "documents.jsonl"),
                       ("normalized_documents", NORMALIZED / "data/documents.jsonl")]:
        if sha_file(path) != manifest["inputs"][name]:
            raise ValueError("원문 목록의 해시가 검증 기록과 다릅니다.")
    documents = {r["unit_id"]: {k: r[k] for k in ["unit_id", "document_title", "format", "source_url", "source_file_sha256", "file_version_key", "effective_status"]}
                 for r in read_jsonl(CORPUS / "documents.jsonl")}
    allowed_ids = {r["id"] for r in manifest["units"]}
    units = {r["id"]: {k: r[k] for k in ["id", "text", "text_sha256", "document_title", "heading_path"]}
             for r in read_jsonl(CORPUS / "reviewed_units.jsonl") if r["id"] in allowed_ids}
    mapping = {r["unit_id"]: dict(original_local_path=r["original_local_path"])
               for r in read_jsonl(NORMALIZED / "data/documents.jsonl")}
    counts = {key: Counter() for key in documents}
    for item in manifest["units"]:
        row = units[item["id"]]
        if row["text_sha256"] != item["text_sha256"] or hashlib.sha256(row["text"].encode()).hexdigest() != item["text_sha256"]:
            raise ValueError("조문 본문의 해시를 확인할 수 없습니다.")
        key = "answer" if item["answer_eligible"] and item["structural_verified"] else "review" if item["structural_verified"] else "excluded"
        counts[item["unit_id"]][key] += 1
    public = []
    for key, doc in documents.items():
        count = counts[key]
        public.append(dict(id=key, title=doc["document_title"], format=doc["format"],
                           answer_count=count["answer"], review_count=count["review"], excluded_count=count["excluded"],
                           source_url=doc["source_url"] if allowed_url(doc["source_url"]) else None,
                           sha256=doc["source_file_sha256"], version=doc["file_version_key"],
                           effective_status=doc["effective_status"], human_approved=False, ktcs_applicable=False))
    public.sort(key=lambda r: (-bool(r["answer_count"]), r["title"]))
    return dict(manifest=manifest, units=units, mapping=mapping, documents=public)


def selected(ids):
    data = load()
    by_id = {r["id"]: r for r in data["documents"]}
    if not ids or len(ids) > 5 or len(set(ids)) != len(ids) or any(uid not in by_id for uid in ids):
        raise ValueError("실제 원문 목록에서 서로 다른 문서를 1~5개 선택해 주세요.")
    return data, [by_id[uid] for uid in ids]


def safe_report(job_id):
    path = store.DATA / "artifacts" / job_id / "report.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _update(job_id, **fields):
    with store.connect() as c:
        current = c.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not current or current[0] == "cancelled":
            return False
        fields["updated_at"] = store.now()
        c.execute("UPDATE jobs SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?", (*fields.values(), job_id))
    return True


def collect(url, destination):
    """Fixed, manifest-derived public hosts only; redirects are rechecked."""
    for _ in range(4):
        if not allowed_url(url):
            raise ValueError("허용된 한전 공식 출처 주소가 아닙니다.")
        with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
            with client.stream("GET", url, headers={"User-Agent": "KLINK-Source-Review/1.0"}) as response:
                if response.is_redirect:
                    from urllib.parse import urljoin
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                size = 0
                with destination.open("wb") as f:
                    for block in response.iter_bytes(65536):
                        size += len(block)
                        if size > 32 * 1024 * 1024:
                            raise ValueError("재수집 파일이 32MB 한도를 넘었습니다.")
                        f.write(block)
                if not size or "text/html" in response.headers.get("content-type", ""):
                    raise ValueError("원문 파일 대신 빈 응답 또는 HTML 안내가 반환됐습니다.")
                return size, sha_file(destination)
    raise ValueError("출처의 주소 이동 한도를 넘었습니다.")


def run_job(job_id, kind, ids):
    folder = store.DATA / "artifacts" / job_id
    folder.mkdir(parents=True, exist_ok=False)
    report = dict(id=job_id, kind=kind, started_at=store.now(), scope="STAGING_ONLY", active_service_changed=False,
                  supabase_ingestion="HOLD", new_embeddings=0, human_approved=False, ktcs_applicable=False,
                  manifest_sha256=MANIFEST_SHA, documents=[], answer_units=0, review_units=0)
    try:
        if not _update(job_id, state="running", message="선택 원문과 검증 범위를 확인하고 있습니다."):
            return
        data, docs = selected(ids)
        if kind == "reindex":
            db = sqlite3.connect(folder / "staging.sqlite3")
            db.executescript("CREATE VIRTUAL TABLE answer_fts USING fts5(id UNINDEXED,title,text); CREATE VIRTUAL TABLE review_fts USING fts5(id UNINDEXED,title,text);")
        else:
            db = None
        try:
            for i, doc in enumerate(docs):
                if not _update(job_id, progress=round(i / len(docs) * 100), message=doc["title"] + " 처리 중"):
                    return
                origin = data["mapping"][doc["id"]]
                expected = data["manifest"]["documents"][doc["id"]]
                original = Path(origin["original_local_path"]).resolve()
                normal = (NORMALIZED / "normalized_text" / (doc["id"] + ".txt")).resolve()
                # Original attachments were preserved in an earlier checkout.
                # Read only the exact paths in hash-pinned metadata, and verify
                # their expected bytes. A request cannot supply a source path.
                if not normal.is_relative_to(NORMALIZED.resolve()):
                    raise ValueError("원문 경로가 지정된 작업 공간을 벗어났습니다.")
                if sha_file(original) != expected["source_sha256"] or sha_file(normal) != expected["normalized_sha256"]:
                    raise ValueError("현재 원본 또는 정규화 파일이 검증 기록과 다릅니다.")
                item = dict(id=doc["id"], title=doc["title"], source_verified=True,
                            original_sha256=expected["source_sha256"], answer_count=doc["answer_count"], review_count=doc["review_count"])
                if kind == "recollect":
                    size, new_sha = collect(doc["source_url"], folder / (doc["id"] + ".source"))
                    item.update(downloaded_bytes=size, downloaded_sha256=new_sha, same_as_preserved=new_sha == expected["source_sha256"],
                                next_step="새 파일은 격리 보관 · 파싱·검토·승인 후 반영 가능")
                if db is not None:
                    for meta in data["manifest"]["units"]:
                        if meta["unit_id"] != doc["id"] or not meta["structural_verified"]:
                            continue
                        row = data["units"][meta["id"]]
                        table = "answer_fts" if meta["answer_eligible"] else "review_fts"
                        db.execute(f"INSERT INTO {table} VALUES(?,?,?)", (row["id"], row["document_title"], row["text"]))
                report["documents"].append(item)
                report["answer_units"] += doc["answer_count"]
                report["review_units"] += doc["review_count"]
            if db is not None:
                db.commit()
                report["index_type"] = "SEPARATE_ANSWER_AND_REVIEW_FTS5_NOT_ACTIVE_VECTOR_INDEX"
        finally:
            if db is not None:
                db.close()
        report.update(completed_at=store.now(), status="succeeded")
        if kind == "reindex":
            report["index_sha256"] = sha_file(folder / "staging.sqlite3")
        (folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if _update(job_id, state="succeeded", progress=100, message="완료 · 기존 서비스와 벡터는 유지했습니다.", report=json.dumps(report, ensure_ascii=False)):
            with store.connect() as c:
                store.audit(c, "local_worker", "job_completed", job_id, dict(kind=kind, active_service_changed=False))
    except Exception as error:
        message = str(error) if isinstance(error, ValueError) else "원문 연결 또는 처리에 실패했습니다. 기존 자료는 유지했습니다."
        report.update(status="failed", error=message, completed_at=store.now())
        (folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _update(job_id, state="failed", message=message, report=json.dumps(report, ensure_ascii=False))
