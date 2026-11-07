"""Recheck preserved original files and every runtime excerpt's normalized-source offsets.

Does not reparse originals, change approval, or modify any corpus/index/gold file.
"""
import hashlib
import argparse
import json
from pathlib import Path
import re
import sys

from evaluate_hr_quality import ROOT, WORKSPACE, CORPUS, readl, write, digest
from server import hr_evidence


def main(output_root=ROOT):
    sys.stdout.reconfigure(encoding="utf-8")
    full=WORKSPACE / "outputs/kepco_hr_full_20261102"
    allowed={r["id"] for r in hr_evidence.corpus()[0]}
    with CORPUS.open(encoding='utf-8') as file:
        rows=[row for line in file if (row:=json.loads(line))["id"] in allowed]
    docs={r["unit_id"]:r for r in readl(full / "data/documents.jsonl")}
    provenance=json.loads((full / "provenance/original_attachment_validation.json").read_text(encoding="utf-8"))
    originals={r["unit_id"]:r for r in provenance["document_units"]}
    normalized={}
    files=[]
    errors=[]
    for uid in sorted({r["unit_id"] for r in rows}):
        d,o=docs[uid],originals[uid]
        p,n=Path(o["original_local_path"]),Path(d["normalized_file"])
        result=dict(unit_id=uid,title=d["title"],original_path=str(p),normalized_path=str(n),
            original_exists=p.is_file(),normalized_exists=n.is_file(),
            expected_original_sha256=d["source_file_sha256"],expected_normalized_sha256=d["normalized_source_sha256"])
        if p.is_file():result["original_sha256"]=digest(p)
        if n.is_file():
            normalized[uid]=n.read_text(encoding="utf-8")
            result["normalized_sha256"]=digest(n)
        result["original_matches"]=result.get("original_sha256")==result["expected_original_sha256"]
        result["normalized_matches"]=result.get("normalized_sha256")==result["expected_normalized_sha256"]
        if not result["original_matches"] or not result["normalized_matches"]:errors.append(dict(unit_id=uid,kind="FILE_HASH_OR_MISSING"))
        files.append(result)
    proof=[]
    part_count=0
    gap_count=0
    for r in rows:
        parts=r.get("source_parts",[])
        unit_errors=[]
        if hashlib.sha256(r["text"].encode()).hexdigest()!=r["text_sha256"]:unit_errors.append("EXCERPT_HASH")
        for p in parts:
            a,b=p["excerpt_text_range"]
            x,y=p["source_normalized_range"]
            if r["text"][a:b]!=normalized.get(r["unit_id"],"")[x:y]:unit_errors.append("ORIGINAL_OFFSET_MISMATCH")
            part_count+=1
        for a,b in r.get("source_mapping_uncovered_ranges",[]):
            if r["text"][a:b].strip():unit_errors.append("NON_WHITESPACE_UNMAPPED")
            gap_count+=1
        if not parts:unit_errors.append("NO_SOURCE_PARTS")
        if r["source_file_sha256"]!=docs[r["unit_id"]]["source_file_sha256"]:unit_errors.append("VERSION_MISMATCH")
        proof.append(dict(source_id=r["id"],unit_id=r["unit_id"],section=r["heading_path"],sha256=r["text_sha256"],
            source_parts=parts,errors=unit_errors))
        if unit_errors:errors.append(dict(source_id=r["id"],kinds=unit_errors))
    cohorts=readl(output_root / "cohort.jsonl")
    evidence_count=0
    for c in cohorts:
        for ev in c["original_evidence"]:
            evidence_count+=1
            compact=re.sub(r"\s","",ev["quote"])
            matching=[s for s in c["designated_full_sources"] if s["source_file_sha256"]==ev["source_file_sha256"] and compact in re.sub(r"\s","",s["text"])]
            if not matching:errors.append(dict(case_id=c["case_id"],evidence_id=ev["evidence_id"],kind="GOLD_QUOTE_NOT_IN_MAPPED_VERSION"))
    write(output_root / "source-verification.json",dict(status="passed" if not errors else "failed",source_sha256=digest(CORPUS),
        runtime_units=len(rows),documents=len(files),source_parts_checked=part_count,whitespace_gaps_checked=gap_count,
        cohort_cases=len(cohorts),designated_evidence_checked=evidence_count,errors=errors,files=files,
        excerpts=proof,original_files_reparsed_this_run=False,source_currentness_verified=False,
        human_semantic_approval=False,no_corpus_changes=True))
    print(json.dumps(dict(status="passed" if not errors else "failed",runtime_units=len(rows),documents=len(files),
        source_parts=part_count,evidence_count=evidence_count,errors=errors[:8]),ensure_ascii=False))
    if errors:raise SystemExit(1)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT)
    args=parser.parse_args()
    main(args.output.resolve())
