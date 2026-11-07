"""Check current local sources and fresh query retrieval; no GPT calls or index writes."""
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server import hr_vector


def main():
    parent = REPO.parent / "outputs"
    os.environ.update(KLINK_HR_RETRIEVAL="dense",
        KLINK_LOCAL_REVIEWED_UNITS=str(parent / "kepco_hr_full_20261102/data/reviewed_units.jsonl"),
        KLINK_HR_VECTOR_INDEX=str(parent / "kepco_hr_full_eval_960_20261102/indexes"),
        KLINK_HR_VECTOR_WINDOWS=str(parent / "kepco_hr_full_20261102/indexes/windows.jsonl"))
    status = hr_vector.status()
    assert status["ready"], status
    cases = []
    for question, heading in [("병가 누계가 7일이 되면 어떤 증빙이 필요한가요?", "질병휴가"),
                              ("민원 대응 때문에 점심 휴게시간을 12시가 아닌 시간대로 운영할 수 있나요?", "휴게시간")]:
        sources, trace = hr_vector.retrieve(question)
        assert heading in sources[0]["section"]
        assert trace["embedding"]["computed"] and not trace["embedding"]["cached"]
        cases.append(dict(question=question, first_section=sources[0]["section"], embedding=trace["embedding"],
                          chunk_ids=[m["chunk_id"] for m in trace["matches"]], source_ids=trace["source_unit_ids"]))
    sources, trace = hr_vector.retrieve("오늘 날씨는 어떤가요?")
    assert not sources and trace["embedding"] is None
    report = dict(status="PASSED", connection=status, fresh_query_checks=cases, out_of_scope_no_embedding=True,
                  paid_model_calls=0, old_sources_and_vectors_modified=False,
                  scope="Two bounded retrieval smoke questions and three numeric window controls, not a search-performance evaluation")
    target = REPO / "output/playwright/hr-vector-source-verification.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":report["status"],"source_count":status["index"]["source_count"],
                      "window_count":status["index"]["window_count"],"query_checks":len(cases),"paid_model_calls":0}))


if __name__ == "__main__":
    main()
