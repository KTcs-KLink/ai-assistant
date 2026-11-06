"""Import *explicitly approved* parsed knowledge-mcp documents into the demo dense index.

Example:
  cd ai-assistant/server
  python import_parsed.py --repo ../../knowledge-mcp --source SRC-0004 \
      --collection hr --confirm-authorized

The manifest currently marks redistribution permission as unknown. This script
never imports those documents without a human opt-in.
"""
import argparse
import asyncio
import csv
import re
import sys
from pathlib import Path

from app import COLLECTIONS, database, index_document, now


def manifest_entries(repo: Path) -> dict[str, dict]:
    source_file = repo / "data" / "manifests" / "sources.csv"
    if not source_file.is_file():
        raise FileNotFoundError(f"manifest not found: {source_file}")
    with source_file.open(encoding="utf-8-sig", newline="") as file:
        return {row["source_id"]: row for row in csv.DictReader(file)}


async def import_one(repo: Path, row: dict, collection: str):
    match = re.search(r"(?:^|;\s*)parsed_file=([^;]+)", row.get("notes", ""))
    if not match:
        print(f"SKIP {row['source_id']}: no parsed_file metadata")
        return False
    relative = Path(match.group(1).strip())
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("manifest parsed_file must be a relative path within the repository")
    path = (repo / relative).resolve()
    if not path.is_relative_to(repo.resolve()) or not path.is_file():
        print(f"SKIP {row['source_id']}: no local parsed file")
        return False

    docid = f"source-{row['source_id'].lower()}"
    title = f"{row.get('title', path.parent.name)} · 공개 대체자료"
    with database() as db:
        # Re-importing a modified document regenerates only that document's chunks.
        db.execute(
            """INSERT INTO documents(
                 id,name,collection_id,kind,path,size,uploaded_at,status,error)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name,collection_id=excluded.collection_id,
                 path=excluded.path,size=excluded.size,uploaded_at=excluded.uploaded_at,
                 status='processing',error=NULL""",
            (docid, title, collection, "kb", str(path),
             path.stat().st_size, now(), "processing", None),
        )
    await index_document(docid)
    with database() as db:
        status = db.execute("SELECT status,error FROM documents WHERE id=?", (docid,)).fetchone()
    print(f"{row['source_id']}: {status['status']}  {title}")
    if status["error"]:
        print(f"  error: {status['error']}")
    return status["status"] == "ready"


async def main():
    parser = argparse.ArgumentParser(description="Import approved parsed markdown for K:LINK demo")
    parser.add_argument("--repo", type=Path, required=True, help="local knowledge-mcp directory")
    parser.add_argument("--source", action="append", help="source_id such as SRC-0004 (repeatable)")
    parser.add_argument("--all", action="store_true", help="select all manifest sources")
    parser.add_argument("--collection", choices=COLLECTIONS.keys(), required=True)
    parser.add_argument(
        "--confirm-authorized", action="store_true",
        help="I confirmed that these materials may be indexed and sent to the configured model",
    )
    args = parser.parse_args()
    if not args.confirm_authorized:
        parser.error(
            "자료 이용 조건과 외부 모델 전송 가능 여부를 먼저 확인한 후 "
            "--confirm-authorized 를 명시적으로 사용해야 합니다."
        )
    if not args.all and not args.source:
        parser.error("--source 또는 --all 중 하나를 지정하세요.")
    records = manifest_entries(args.repo)
    chosen = list(records) if args.all else list(dict.fromkeys(args.source))
    failures = 0
    for key in chosen:
        if key not in records:
            print(f"{key}: manifest에서 찾을 수 없습니다.", file=sys.stderr)
            failures += 1
            continue
        if not await import_one(args.repo.resolve(), records[key], args.collection):
            failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
