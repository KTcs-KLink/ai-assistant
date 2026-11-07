"""Read-only, local-only source lookup; no corpus copies or automatic LLM transmission."""
from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path


def corpus_path() -> Path | None:
    configured = os.getenv("KLINK_LOCAL_REVIEWED_UNITS")
    return Path(configured).expanduser().resolve() if configured else None


@lru_cache(maxsize=2)
def _load(path: str, mtime: int) -> tuple[dict, ...]:
    approved_for_reference = []
    with Path(path).open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            # Preserve the pre-existing automated gate and reject a changed excerpt.
            if not row.get("searchable") or not row.get("answer_eligible"):
                continue
            if hashlib.sha256(row["text"].encode()).hexdigest() != row.get("text_sha256"):
                continue
            approved_for_reference.append({
                "id": row["id"], "title": row["document_title"], "section": row["heading_path"],
                "text": row["text"], "sha256": row["text_sha256"],
                "version": row.get("file_version_key"), "company": "KEPCO",
                "review_status": row.get("review_status"), "human_approved": bool(row.get("human_approved")),
                "effective_status": row.get("effective_status"),
            })
    return tuple(approved_for_reference)


def records() -> tuple[dict, ...]:
    path = corpus_path()
    if not path or not path.is_file():
        return ()
    return _load(str(path), path.stat().st_mtime_ns)


def search(query: str) -> dict:
    terms = list(dict.fromkeys(re.findall(r"[가-힣A-Za-z0-9]{2,}", query.lower())))[:12]
    # A narrow lexical reference finder, explicitly separate from the existing BM25/Dense benchmarks.
    hits = []
    for record in records():
        title = (record["title"] + " " + record["section"]).lower()
        body = record["text"].lower()
        score = sum(3 * title.count(t) + min(body.count(t), 5) for t in terms)
        if score:
            hits.append((score, record))
    hits.sort(key=lambda item: (-item[0], item[1]["id"]))
    return dict(method="local_lexical_reference", company="KEPCO", ktcs_applicable=False,
                source_count=len(records()), results=[{k: v for k, v in r.items() if k != "text"} | {"excerpt": r["text"][:300]} for _, r in hits[:5]])


def source(source_id: str) -> dict | None:
    return next((r for r in records() if r["id"] == source_id), None)
