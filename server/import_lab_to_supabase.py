"""Import ONLY the 10 HR documents / 1,722 chunks from local KTCS PoC archive.

This reuses both precomputed BGE-m3-ko 1024D embedding matrices (body/path).
No re-embedding or LLM calls. Default --check-only never touches a database.
Usage:
  python import_lab_to_supabase.py --zip /path/KTCS_RAG_Lab_2026-11-02.zip
  KLINK_PG_DSN='postgresql://...' python import_lab_to_supabase.py --zip ... --apply
Apply server/sql/pgvector_schema.sql through Supabase first.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np

OLD_PREFIX = "KTCS_RAG_Lab_2026-11-02/run/"
HR_PREFIX = "KLINK_local_HR_2026-11-07/run/"
# Explicit source IDs prevent accidental mixing of 8 unrelated domains.
HR_SOURCE_IDS = frozenset({
    "SRC-0001", "SRC-0004", "SRC-0005", "SRC-0006", "SRC-0007",
    "SRC-0008", "SRC-0009", "SRC-0011", "SRC-0013", "SRC-0014",
})
MODEL = "dragonkue/BGE-m3-ko"
REVISION = "7074d66aa46562342193ca4feb3d89bf9dad71b4"
EXPECTED_CHUNKS = 1722
EXPECTED_DIMENSIONS = 1024


def domain_for(title: str) -> str:
    # All imported source IDs are on the explicit HR allowlist.
    return "hr"


def load_verified(archive: Path):
    if not archive.is_file() or not zipfile.is_zipfile(archive):
        raise ValueError("KTCS RAG Lab ZIP 파일을 찾을 수 없거나 형식이 잘못되었습니다.")
    with zipfile.ZipFile(archive) as z:
        prefix = (
            HR_PREFIX if HR_PREFIX + "chunks.jsonl" in z.namelist()
            else OLD_PREFIX if OLD_PREFIX + "chunks.jsonl" in z.namelist()
            else None
        )
        if prefix is None:
            raise ValueError("Unsupported archive layout; use the local HR ZIP or archived experiment ZIP")

        def raw(name: str) -> bytes:
            return z.read(prefix + name)

        chunk_blob = raw("chunks.jsonl")
        chunks = [json.loads(line) for line in chunk_blob.splitlines() if line.strip()]
        sources = json.loads(raw("source_manifest.json"))
        body_bytes, path_bytes = raw("embeddings_body.npy"), raw("embeddings_path.npy")
        body_manifest = json.loads(raw("embeddings_body.done.json"))
        path_manifest = json.loads(raw("embeddings_path.done.json"))
        for label, manifest, vector_bytes in (
            ("body", body_manifest, body_bytes), ("path", path_manifest, path_bytes)
        ):
            if manifest["model"] != MODEL or manifest["revision"] != REVISION:
                raise ValueError(f"{label} model snapshot mismatch")
            if manifest["pooling"] != "CLS" or manifest["max_tokens"] != 768:
                raise ValueError(f"{label} pooling/tokenization mismatch")
            if hashlib.sha256(vector_bytes).hexdigest() != manifest["vectors_sha256"]:
                raise ValueError(f"{label} embedding checksum mismatch")
            if hashlib.sha256(chunk_blob).hexdigest() != manifest["chunks_sha256"]:
                raise ValueError(f"{label} chunk checksum mismatch")
        body = np.load(io.BytesIO(body_bytes), allow_pickle=False)
        path = np.load(io.BytesIO(path_bytes), allow_pickle=False)
    if (len(sources), len(chunks)) not in {(18, 1933), (10, EXPECTED_CHUNKS)}:
        raise ValueError("Unexpected local experiment corpus length")
    original_len = len(chunks)
    ids = [chunk["chunk_id"] for chunk in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate chunk ID")
    source_ids = {source["source_id"] for source in sources}
    if {chunk["source_id"] for chunk in chunks} != source_ids:
        raise ValueError("Source/chunk manifest mismatch")
    for matrix in (body, path):
        if matrix.shape != (original_len, EXPECTED_DIMENSIONS) or matrix.dtype != np.float32:
            raise ValueError("Embedding dimensions or dtype mismatch")
        if not np.isfinite(matrix).all() or not np.allclose(
            np.linalg.norm(matrix, axis=1), 1.0, atol=1e-4
        ):
            raise ValueError("Embedding vectors must be finite and unit-normalized")
    if any(not chunk["text"].strip() for chunk in chunks):
        raise ValueError("Empty chunk text")

    # Ensure text/vector correspondence by slicing both arrays with identical
    # original line indices. No external GitHub document contents are fetched.
    chosen = [i for i, c in enumerate(chunks) if c["source_id"] in HR_SOURCE_IDS]
    filtered_chunks = [chunks[i] for i in chosen]
    filtered_sources = [src for src in sources if src["source_id"] in HR_SOURCE_IDS]
    if len(filtered_sources) != 10 or len(filtered_chunks) != EXPECTED_CHUNKS:
        raise ValueError("HR source allowlist / expected chunk count mismatch")
    if {s["source_id"] for s in filtered_sources} != HR_SOURCE_IDS:
        raise ValueError("Missing HR source IDs")
    return filtered_sources, filtered_chunks, body[chosen].copy(), path[chosen].copy()


def vector_literal(vector: np.ndarray) -> str:
    # Always serialize finite validated float32 data into pgvector's literal syntax.
    return "[" + ",".join(format(float(x), ".9g") for x in vector) + "]"


def write_to_pg(dsn: str, sources: list, chunks: list, body: np.ndarray, path: np.ndarray):
    import psycopg

    if not dsn.startswith(("postgresql://", "postgres://")):
        raise ValueError("KLINK_PG_DSN must be a PostgreSQL connection URL")
    docs_sql = """
        INSERT INTO public.klink_rag_documents (
          source_id,title,domain,source_url,source_path,snapshot_commit,
          original_document_sha256,parsed_sha256,published_at_manifest
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(source_id) DO UPDATE SET
          title=excluded.title,domain=excluded.domain,source_url=excluded.source_url,
          source_path=excluded.source_path,snapshot_commit=excluded.snapshot_commit,
          original_document_sha256=excluded.original_document_sha256,
          parsed_sha256=excluded.parsed_sha256,
          published_at_manifest=excluded.published_at_manifest,updated_at=now()
    """
    chunks_sql = """
        INSERT INTO public.klink_rag_chunks (
          chunk_id,source_id,unit_id,unit_kind,article,chapter,section,kind,
          content,spans,page,embedding_body,embedding_path,snapshot_commit,
          embedding_model,embedding_revision
        ) VALUES (
          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::extensions.vector,
          %s::extensions.vector,%s,%s,%s
        )
        ON CONFLICT(chunk_id) DO UPDATE SET
          source_id=excluded.source_id,unit_id=excluded.unit_id,
          unit_kind=excluded.unit_kind,article=excluded.article,
          chapter=excluded.chapter,section=excluded.section,
          kind=excluded.kind,content=excluded.content,spans=excluded.spans,
          page=excluded.page,embedding_body=excluded.embedding_body,
          embedding_path=excluded.embedding_path,
          snapshot_commit=excluded.snapshot_commit,
          embedding_model=excluded.embedding_model,
          embedding_revision=excluded.embedding_revision,updated_at=now()
    """
    if len(sources) != 10 or len(chunks) != EXPECTED_CHUNKS:
        raise ValueError("Only verified HR-only corpus may be imported")
    if {s["source_id"] for s in sources} != HR_SOURCE_IDS:
        raise ValueError("Refusing to import non-HR sources")
    with psycopg.connect(dsn, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT source_id FROM public.klink_rag_documents")
            existing = {row[0] for row in cur.fetchall()}
            if existing - HR_SOURCE_IDS:
                raise ValueError("Target database contains non-HR sources; use a clean HR project")
            cur.executemany(docs_sql, [
                (s["source_id"], s["title"], domain_for(s["title"]), s.get("source_url"),
                 s["source_path"], s["snapshot_commit"], s.get("original_document_sha256"),
                 s.get("parsed_sha256"), s.get("published_at_manifest"))
                for s in sources
            ])
            batch_size = 32
            for start in range(0, len(chunks), batch_size):
                rows = []
                for i in range(start, min(start + batch_size, len(chunks))):
                    c = chunks[i]
                    rows.append((
                        c["chunk_id"], c["source_id"], c.get("unit_id"), c.get("unit_kind"),
                        c.get("article"), c.get("chapter"),
                        c.get("section"), c["kind"],
                        c["text"], json.dumps(c["spans"], ensure_ascii=False),
                        c.get("page"), vector_literal(body[i]), vector_literal(path[i]),
                        c["snapshot_commit"], MODEL, REVISION,
                    ))
                cur.executemany(chunks_sql, rows)
            cur.execute(
                "SELECT count(*),count(distinct source_id) FROM public.klink_rag_chunks "
                "WHERE embedding_model=%s AND embedding_revision=%s", (MODEL, REVISION)
            )
            total, docs = cur.fetchone()
            cur.execute("SELECT count(*) FROM public.klink_rag_documents")
            document_total = cur.fetchone()[0]
            if total != EXPECTED_CHUNKS or docs != 10 or document_total != 10:
                raise ValueError(f"Post-import verification failed: {total} chunks / {docs} sources / {document_total} docs")
    print(f"Verified HR-only Supabase pgvector import: {docs} documents, {total} chunks, 1024D x 2")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True,
                        help="Local experiment ZIP or filtered KLINK_local_HR ZIP")
    parser.add_argument("--apply", action="store_true", help="Commit verified data to Supabase")
    args = parser.parse_args()
    sources, chunks, body, path = load_verified(args.zip)
    print(f"Verified LOCAL HR ZIP: {len(sources)} documents, {len(chunks)} chunks (no GitHub fetch)")
    print("Domains:", dict(sorted(Counter(domain_for(s["title"]) for s in sources).items())))
    if not args.apply:
        print("CHECK-ONLY: no remote writes. Provide --apply and KLINK_PG_DSN to import.")
        return
    dsn = os.getenv("KLINK_PG_DSN", "")
    if not dsn:
        parser.error("KLINK_PG_DSN is required with --apply; never add it to Git")
    write_to_pg(dsn, sources, chunks, body, path)


if __name__ == "__main__":
    main()
