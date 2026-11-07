"""Revalidate recorded REAL responses with the final deterministic display guards.

This is explicitly a replay, not 40 new model calls. Fresh correction calls are
separately preserved and selected by a fixed case list, never by best-score search.
"""
import json
from pathlib import Path
import sys
from copy import deepcopy

from evaluate_hr_quality import ROOT, REPO, CORPUS, readl, write, digest
from server import hr_answer, hr_evidence

CORRECTED={"KEPCO-HR-03-003","KEPCO-HR-04-009","KEPCO-HR-07-006","KEPCO-HR-08-002"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cohort=readl(ROOT / "cohort.jsonl")
    proof=[]
    for case in cohort:
        cid=case["case_id"]
        origin="final-live-corrections" if cid in CORRECTED else "candidate-3"
        path=ROOT / origin / "answers" / (cid+".json")
        if not path.is_file():raise SystemExit("Original/correction checkpoints incomplete; no partial final report.")
        record=json.loads(path.read_text(encoding="utf-8"))
        response=deepcopy(record.get("response"))
        replayed=False
        if response:
            candidate={k:response[k] for k in ("status","paragraphs","missing_information")}
            if not candidate["paragraphs"]:
                withheld=ROOT / origin / "withheld-candidates-local-only" / (cid+".json")
                if withheld.is_file():candidate=json.loads(withheld.read_text(encoding="utf-8"))["unvalidated_draft"]
            if candidate["paragraphs"]:
                try:
                    final,extra=hr_answer.finalize(hr_answer.Draft(**candidate),response["sources"],case["question"])
                    response.update(**final.model_dump(),**extra,generated_text_withheld=False,
                        validation="FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION")
                    replayed=True
                except hr_answer.AnswerUnavailable:
                    response.update(status="needs_review",paragraphs=[],missing_information=["최종 원문 검사에서 답변을 보류했어요."],
                        generated_text_withheld=True)
            response["provider_calls"]=[]
            response["usage"]=None
        final_record=dict(**{k:v for k,v in record.items() if k!="response"},response=response,
            evaluation_mode="DETERMINISTIC_REPLAY_OF_RECORDED_REAL_RESPONSE",
            original_stage=origin,original_response_file_sha256=digest(path),new_model_calls_in_replay=0,
            replayed=replayed)
        write(ROOT / "final-display-replay/answers" / (cid+".json"),final_record)
        cards=(response or {}).get("source_conditions",[])
        sources={s["id"]:s for s in (response or {}).get("sources",[])}
        for card in cards:
            source=sources[card["source_id"]]
            assert card["quote"]==source["text"][card["start"]:card["end"]]
            assert card["source_sha256"]==source["sha256"]
        proof.append(dict(case_id=cid,origin=origin,model_called_in_replay=False,
            original_sha256=digest(path),displayed_paragraphs=len((response or {}).get("paragraphs",[])),
            source_condition_cards=len(cards),partial_verified_text=(response or {}).get("partial_verified_text",False)))
    write(ROOT / "final-display-replay/replay-proof.json",dict(cases=proof,new_model_calls=0,
        source_sha256=digest(CORPUS),code={n:digest(REPO / "server" / (n+".py")) for n in ("hr_answer","hr_evidence","hr_conditions")},
        source_condition_cards=sum(p["source_condition_cards"] for p in proof),all_source_card_spans_and_hashes_match=True,
        human_approved=False,semantic_completeness_not_established_by_replay=True))
    print(json.dumps(dict(cases=len(proof),displayed=sum(p["displayed_paragraphs"]>0 for p in proof),
        condition_cards=sum(p["source_condition_cards"] for p in proof),new_model_calls=0),ensure_ascii=False))


if __name__=="__main__":main()
