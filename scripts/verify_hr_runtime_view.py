"""Prove the small runtime view preserves every prior allowed source field."""
import importlib.util
import json
import sys
import time

from evaluate_hr_expansion import ROOT,REPO,CORPUS,hr_evidence
from expand_hr_sources import write
from hr_source_audit import sha


def main():
    start=time.monotonic();current=hr_evidence.corpus()[0];seconds=time.monotonic()-start
    path=ROOT/'evaluation/expanded-v2/code_snapshot/hr_evidence.py'
    name='server.original_full_reader_for_comparison'
    spec=importlib.util.spec_from_file_location(name,path);frozen=importlib.util.module_from_spec(spec)
    sys.modules[name]=frozen;spec.loader.exec_module(frozen)
    start=time.monotonic();previous=frozen.corpus()[0];old_seconds=time.monotonic()-start
    if current!=previous:raise ValueError('RUNTIME_VIEW_CHANGED_A_SOURCE_FIELD')
    overlay=json.loads((ROOT/'review-overlay.json').read_text(encoding='utf-8'))
    result=dict(all_source_fields_equal=True,source_units=len(current),canonical_source_sha256=sha(CORPUS),
        canonical_file_bytes=CORPUS.stat().st_size,runtime_view_bytes=(ROOT/overlay['runtime_view_file']).stat().st_size,
        runtime_view_sha256=overlay['runtime_view_sha256'],view_rows=overlay['runtime_view_count'],
        current_reader_seconds=round(seconds,3),full_reader_seconds=round(old_seconds,3),
        original_text_ids_conditions_exceptions_and_version_metadata_unchanged=True,new_embeddings=0)
    write(ROOT/'reader-equivalence.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
