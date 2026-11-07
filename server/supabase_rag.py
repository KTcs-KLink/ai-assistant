"""Supabase pgvector Dense retrieval for the pinned KTCS KEPCO PoC snapshot.

Server-only: KLINK_PG_DSN is a privileged credential; NEVER include it in VITE_.
The saved path embeddings use BGE-m3-ko CLS/bfloat16/1024D, NOT OpenAI or BAAI/bge-m3.
No model calls are made until the remote backend is explicitly selected.
"""
from __future__ import annotations

import asyncio
import os
import threading
from collections import defaultdict
from functools import lru_cache

try:
    from .query_strategy import plan_query, evidence_priority, supports_regular_payday
except ImportError:
    from query_strategy import plan_query, evidence_priority, supports_regular_payday

MODEL = "dragonkue/BGE-m3-ko"
REVISION = "7074d66aa46562342193ca4feb3d89bf9dad71b4"
MODEL_LOCK = threading.RLock()


def enabled() -> bool:
    return os.getenv("KLINK_RAG_BACKEND", "").lower() == "supabase"


def _dsn() -> str:
    dsn = os.getenv("KLINK_PG_DSN", "")
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Supabase 서버 DB 연결 설정(KLINK_PG_DSN)이 없습니다.")
    return dsn


@lru_cache(maxsize=1)
def _load_encoder():
    import torch
    from transformers import AutoModel, AutoTokenizer

    model_dir = os.getenv("KLINK_BGE_MODEL_DIR", "").strip() or MODEL
    opts = {"trust_remote_code": False}
    if model_dir == MODEL:
        opts["revision"] = REVISION
    elif not os.path.isdir(model_dir):
        raise RuntimeError("KLINK_BGE_MODEL_DIR가 유효한 로컬 디렉터리가 아닙니다.")
    # Exact parity with the archived experiment: CPU BF16, CLS pooling, L2 normalization.
    torch.set_num_threads(int(os.getenv("KLINK_BGE_THREADS", "4")))
    tokenizer = AutoTokenizer.from_pretrained(model_dir, **opts)
    model = AutoModel.from_pretrained(model_dir, torch_dtype=torch.bfloat16, **opts).to("cpu").eval()
    return torch, tokenizer, model


def encode_queries(texts: tuple[str, ...]) -> list[list[float]]:
    import numpy as np

    with MODEL_LOCK:
        torch, tokenizer, model = _load_encoder()
        tokens = tokenizer(list(texts), padding=True, truncation=False, return_tensors="pt")
        if tokens["input_ids"].shape[1] > 768:
            raise ValueError("질문이 BGE-m3-ko의 768-token 제한을 초과했습니다.")
        with torch.inference_mode():
            vectors = model(**tokens).last_hidden_state[:, 0, :].float()
            vectors = torch.nn.functional.normalize(vectors, p=2, dim=1).cpu().numpy()
    if vectors.shape != (len(texts), 1024) or not np.isfinite(vectors).all():
        raise ValueError("질의 임베딩 모델이 적재된 1024D 벡터와 일치하지 않습니다.")
    return vectors.tolist()


def _literal(values: list[float]) -> str:
    return "[" + ",".join(format(x, ".9g") for x in values) + "]"


_SELECT = """
SELECT c.chunk_id AS id, c.source_id AS document_id, c.content,
       concat_ws(' > ',nullif(c.chapter,''),nullif(c.section,''),nullif(c.article,'')) AS section,
       c.page, d.title AS name, 'kb' AS kind, d.domain,
       1 - (c.embedding_path <=> %s::extensions.vector) AS score
FROM public.klink_rag_chunks c
JOIN public.klink_rag_documents d ON d.source_id=c.source_id
WHERE d.domain='hr'
ORDER BY c.embedding_path <=> %s::extensions.vector
LIMIT 20
"""

_PAYDAY = """
SELECT c.chunk_id AS id, c.source_id AS document_id, c.content,
       concat_ws(' > ',nullif(c.chapter,''),nullif(c.section,''),nullif(c.article,'')) AS section,
       c.page, d.title AS name, 'kb' AS kind, d.domain, 0.0 AS score
FROM public.klink_rag_chunks c
JOIN public.klink_rag_documents d ON d.source_id=c.source_id
WHERE d.domain='hr' AND c.content ~ '매[[:space:]]*월[[:space:]]*[0-9]{1,2}[[:space:]]*일'
LIMIT 80
"""


def _run_db_query(vectors: list[list[float]], payday: bool) -> list[list[dict]]:
    import psycopg
    from psycopg.rows import dict_row

    result: list[list[dict]] = []
    with psycopg.connect(_dsn(), connect_timeout=15, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            for v in vectors:
                lit = _literal(v)
                cur.execute(_SELECT, (lit, lit))
                result.append(cur.fetchall())
            if payday:
                cur.execute(_PAYDAY)
                result.append(cur.fetchall())
    return result


async def search_supabase(question: str) -> list[dict]:
    plan = plan_query(question)
    vectors = await asyncio.to_thread(encode_queries, plan.variants)
    rankings = await asyncio.to_thread(_run_db_query, vectors, plan.intent == "regular_payday")
    ranked: dict[str, dict] = {}
    for query_idx, candidates in enumerate(rankings):
        for rank, row in enumerate(candidates, 1):
            if query_idx == len(vectors) and plan.intent == "regular_payday":
                if not supports_regular_payday(row["section"], row["content"]):
                    continue
                item = ranked.setdefault(row["id"], {"row": row, "score": 0., "rrf": 0.})
                continue
            score = float(row["score"])
            item = ranked.setdefault(row["id"], {"row": row, "score": score, "rrf": 0.})
            item["score"] = max(item["score"], score)
            item["rrf"] += (1.0 if query_idx == 0 else 0.8) / (60 + rank)
    threshold = float(os.getenv("KLINK_MIN_SCORE", "0.25"))
    chosen = []
    for item in ranked.values():
        row = item["row"]
        anchor = evidence_priority(plan, row["section"], row["content"])
        if plan.intent == "regular_payday" and not anchor:
            continue
        if plan.intent != "regular_payday" and item["score"] < threshold:
            continue
        chosen.append((10 * anchor + item["rrf"] * 30 + item["score"], item))
    chosen.sort(key=lambda obj: obj[0], reverse=True)
    result, seen = [], set()
    for _, item in chosen:
        row = item["row"]
        key = (row["document_id"], row["content"].strip())
        if key in seen:
            continue
        seen.add(key)
        result.append({"score": round(item["score"], 5), "row": row})
        if len(result) == 5:
            break
    return result


def admin_status() -> dict:
    import psycopg

    with psycopg.connect(_dsn(), connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM public.klink_rag_documents")
            documents = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM public.klink_rag_chunks")
            chunks = cur.fetchone()[0]
    return {"readyDocuments": documents, "indexedChunks": chunks, "dimensions": 1024}


def admin_documents() -> list[dict]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(_dsn(), connect_timeout=10, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_id,title,domain,updated_at FROM public.klink_rag_documents "
                "ORDER BY source_id"
            )
            rows = cur.fetchall()
    return [
        {"id": r["source_id"], "name": r["title"] + " · KEPCO 공개 대체자료",
         "collectionId": r["domain"], "access": "단일 관리자 PoC 전용",
         "uploadedAt": r["updated_at"].isoformat(), "status": "ready"}
        for r in rows
    ]


def admin_collection_counts() -> dict[str, int]:
    import psycopg

    with psycopg.connect(_dsn(), connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT domain,count(*) FROM public.klink_rag_documents GROUP BY domain")
            return dict(cur.fetchall())
