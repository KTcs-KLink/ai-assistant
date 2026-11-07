-- K:LINK publicly sourced KEPCO PoC corpus. No employee data is stored here.
-- Use only from the server over a private Postgres DSN; never expose the DSN in Vite.
create extension if not exists vector with schema extensions;

create table if not exists public.klink_rag_documents (
  source_id text primary key,
  title text not null,
  domain text not null default 'unclassified',
  corpus_label text not null default 'KEPCO public substitute (PoC only)',
  source_url text,
  source_path text not null,
  snapshot_commit text not null,
  original_document_sha256 text,
  parsed_sha256 text,
  published_at_manifest date,
  updated_at timestamptz not null default now()
);

create table if not exists public.klink_rag_chunks (
  chunk_id text primary key,
  source_id text not null references public.klink_rag_documents(source_id) on delete cascade,
  unit_id text,
  unit_kind text,
  article text,
  chapter text,
  section text,
  kind text not null check(kind in ('prose','table_rows')),
  content text not null,
  spans jsonb not null default '[]'::jsonb,
  page integer,
  embedding_body extensions.vector(1024) not null,
  embedding_path extensions.vector(1024) not null,
  snapshot_commit text not null,
  embedding_model text not null,
  embedding_revision text not null,
  updated_at timestamptz not null default now()
);

create index if not exists idx_klink_rag_chunks_source on public.klink_rag_chunks(source_id);
create index if not exists idx_klink_rag_documents_domain on public.klink_rag_documents(domain);
-- For 1,933 chunks use exact cosine scans first; benchmark HNSW/ANN separately.
-- Defense in depth: these tables are NOT browser-facing APIs.
alter table public.klink_rag_documents enable row level security;
alter table public.klink_rag_chunks enable row level security;
revoke all on table public.klink_rag_documents from anon, authenticated, public;
revoke all on table public.klink_rag_chunks from anon, authenticated, public;
-- Backend Postgres credentials must remain server-side; frontend uses FastAPI.
