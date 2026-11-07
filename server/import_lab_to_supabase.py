"""Import the existing 18-document / 1,933-chunk KEPCO PoC ZIP into Supabase pgvector.

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

PREFIX = "KTCS_RAG_Lab_2026-11-02/run/"
MODEL = "dragonkue/BGE-m3-ko"
REVISION = "7074d66aa46562342193ca4feb3d89bf9dad71b4"
EXPECTED_CHUNKS = 1933
EXPECTED_DIMENSIONS = 1024


# Verified against knowledge-mcp/data/parsed/인사관리규정_20cbc4e2/parsing.md
# The archived chunk lost its parent appendix header; preserve the actual scope
# as corrected metadata without altering its text or the precomputed embedding.
ARCHIVE_SCOPE_OVERRIDES = {
    "SRC-0007-c0315": "【별표 3-2】 근로계약서 표준 양식 (제10조 관련)",
}


def domain_for(title: str) -> str:
    """Conservative PoC labels. Unknown documents stay unclassified."""
    if "회계" in title:
        return "finance"
    if any(word in title for word in (
        "인사", "취업", "연봉", "복리후생", "복지", "노사협의",
        "직급", "비정규직", "성희롱",
    )):
        return "hr"
    return "unclassified"


def load_verified(archive: Path):
    if not archive.is_file() or not zipfile.is_zipfile(archive):
        raise ValueError("KTCS RAG Lab ZIP 파일을 찾을 수 없거나 형식이 잘못되었습니다.")
    with zipfile.ZipFile(archive) as z:
        def raw(name: str) -> bytes:
            return z.read(PREFIX + name)

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
    if len(chunks) != EXPECTED_CHUNKS or len(sources) != 18:
        raise ValueError("Unexpected corpus length")
    ids = [chunk["chunk_id"] for chunk in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate chunk ID")
    source_ids = {source["source_id"] for source in sources}
    if {chunk["source_id"] for chunk in chunks} != source_ids:
        raise ValueError("Source/chunk manifest mismatch")
    for matrix in (body, path):
        if matrix.shape != (EXPECTED_CHUNKS, EXPECTED_DIMENSIONS) or matrix.dtype != np.float32:
            raise ValueError("Embedding dimensions or dtype mismatch")
        if not np.isfinite(matrix).all() or not np.allclose(
            np.linalg.norm(matrix, axis=1), 1.0, atol=1e-4
        ):
            raise ValueError("Embedding vectors must be finite and unit-normalized")
    if any(not chunk["text"].strip() for chunk in chunks):
        raise ValueError("Empty chunk text")
    return sources, chunks, body, path


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
    with psycopg.connect(dsn, connect_timeout=20) as conn:
        with conn.cursor() as cur:
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
                        c.get("article"), ARCHIVE_SCOPE_OVERRIDES.get(c["chunk_id"], c.get("chapter")),
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
            if total != EXPECTED_CHUNKS or docs != 18:
                raise ValueError(f"Post-import verification failed: {total} chunks / {docs} sources")
    print(f"Verified Supabase pgvector import: {docs} sources, {total} chunks, 1024D x 2")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True, help="Existing KTCS RAG Lab ZIP")
    parser.add_argument("--apply", action="store_true", help="Commit verified data to Supabase")
    args = parser.parse_args()
    sources, chunks, body, path = load_verified(args.zip)
    print(f"Verified local ZIP: {len(sources)} sources, {len(chunks)} chunks")
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
