"""KEPCO 21 retrieval cases + one prose case, preserved baseline and real API rechecks.

This is confined to KTCS/K:LINK. No source, gold, original index, or database writes.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import evaluate_hr_quality as shared

ROOT=shared.WORKSPACE / "outputs/klink_hr_quality_closeout_20261107"
REPO=shared.REPO
CORPUS=shared.CORPUS
readl,write,digest=shared.readl,shared.write,shared.digest

POINTS={
 "01-005":["사업소 채용 절차/전형은 본사 인사담당부서 직접 관리", "사업소 별도 채용이 불가피하면 계획 및 결과 본사 보고"],
 "01-037":["공개채용의 부당한 가족 우대 금지", "채용권자의 임직원 가족·사적 지인 채용 금지와 구분", "공개경쟁이라는 이유만으로 별도 채용 금지의 예외를 만들지 않음"],
 "02-018":["사직원 제출", "소정 수속과 승인 후 퇴직", "의사 통보만으로 자동 완료라고 하지 않음"],
 "02-019":["정년 연령과 적용대상을 해당 조문 그대로", "정년퇴직 시기는 별도 조문의 날짜와 상반기/하반기 조건을 보존"],
 "02-050":["정년퇴직 시기 조문과 자진퇴직의 사직원/수속/승인을 구분", "정년퇴직에 자진퇴직 절차를 무조건 동일 적용하지 않음"],
 "02-067":["사직원만으로 퇴직 승인·수속 완료 아님", "퇴직/전근 등 사무인계 요건과 주체·방식은 원문대로", "제공하지 않은 결재시스템 처리 상태 창작 금지"],
 "02-088":["직원 정년과 정년퇴직 시기를 보존", "비정규직 계약기간 및 별도 종료 조건 구분", "서로 다른 적용대상의 종료를 같은 방식으로 확정하지 않음"],
 "02-098":["명예퇴직 근속요건의 휴직 제외 조항과 참조된 휴직사유를 대조", "가족돌봄휴직을 열거되지 않은 제외 사유로 추가하지 않음", "필요한 조문이 있으면 그 내용을 설명하고 근거가 없다고 잘못 말하지 않음"],
 "02-112":["정규직의 해임 사유/재량 표현 보존", "비정규직의 고용결격·계약해지 사유와 구분", "같은 신체/정신 문제라는 이유만으로 조치·적용대상 통합 금지"],
 "02-118":["인사관리지침 제101조의 실제 적용대상", "그 대상의 정년 연령을 원문대로", "다른 연구직 등의 대상/나이를 끌어오지 않음"],
 "03-036":["임원 비서 보직의 추천·추천자 재임기간 조건", "다른 직무/일반 업무 전환 제한과 관련 예외를 원문대로", "원문이 금지하는 것을 단순 재량으로 바꾸지 않음"],
 "03-041":["4직급의 전방위 보직 가능한 범위·장소·조건", "직장·직군 전환 조항의 제한 대상 및 예외", "보직 가능과 직군 전환 가능을 같은 것으로 확정하지 않음"],
 "04-049":["휴게시간 자유 이용과 질서·규율 한계", "외출 목적 등 별도 조항의 실제 범위", "개인 용무 외출/승인이 무조건 허용된다고 만들어 말하지 않음"],
 "05-004":["연차 계산기간은 전년도 입사일부터 당해 입사일 전일까지", "매년1월1일 일률 적용을 해당 조문 근거로 승인하지 않음"],
 "05-053":["휴가의 사전 허가 원칙", "참조 조문에 의한 대상 휴가 범위", "연차/질병휴가를 임의로 사후 허가 가능하다고 하지 않음"],
 "05-100":["연차 계산기간과 출근율 처리 규칙을 구분", "제공된 원문의 출근 간주/제외 조건·예외가 있는 범위를 설명", "계산기간 조문만으로 모든 휴직의 출근율 처리를 확정하지 않음"],
 "06-031":["직원 퇴직급여의 최소 근속요건", "연미만 지급률 문구를 최소요건 미달자에게 확대하지 않음", "임원 조문을 직원에게 적용하지 않음"],
 "06-056":["일반 직원 보수의 연결 규정", "비정규직 업무상 재해보상의 연결 규정과 장", "복지업무 실무지침으로 자동 대체하지 않음"],
 "07-041":["장기근속격려금의 실제 폐지 적용일", "질문의2013년12월과 적용일을 구분", "폐지 전이라는 사실만으로 구체 지급 자격/금액을 승인하지 않음"],
 "07-052":["복지지침상 공상·순직 인정 주체 및 미가입 사업장 예외", "비정규직 재해보상의 준용 규정", "두 조문을 곧바로 동일 적용한다고 일반화하지 않음"],
 "08-021":["근무평정기간 소급 및 연장 금지", "실적 부족을 이유로 기간을 바꾸거나 이전 실적을 임의 전용할 수 있다고 하지 않음"],
 "03-003":["교육과 일반 휴직(육아휴직 포함) 등은6개월이상이라는 원칙을 본문에 명시", "출산전후휴가에 이어 육아휴직3개월이상이라는 별도 예외를 본문에 구분", "동일직급 정원을 따로 보는 조건과 보충 가능(의무 아님)을 보존"],
}


def load_frozen(name):
    alias="server.closeout_frozen_"+name
    spec=importlib.util.spec_from_file_location(alias,ROOT/"baseline_code"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    sys.modules[alias]=module
    spec.loader.exec_module(module)
    return module


def prepare():
    from server import hr_evidence,benefit_explanation
    if (ROOT/"protocol.json").exists():raise SystemExit("Protocol already frozen; do not overwrite.")
    allowed={s["id"]:s for s in hr_evidence.corpus()[0]}
    gold={s["case_id"]:s for s in readl(shared.GOLD)}
    mappings={s["case_id"]:s for s in readl(shared.MAPPING)}
    previous=shared.ROOT
    cases=json.loads((previous/"retrieval-review-candidates.json").read_text(encoding="utf-8"))["cases"]
    ids=[c["case_id"] for c in cases]+["KEPCO-HR-03-003"]
    cohort=[]
    for cid in ids:
        g,m=gold[cid],mappings[cid]
        assert m["all_gold_answer_eligible"] and set(m["mapped_unit_ids"])<=allowed.keys()
        cohort.append(dict(case_id=cid,question=g["question"],task_code=g["task_code"],task_name=g["task_name"],
            purpose="prose_clarification" if cid.endswith("03-003") else "retrieval_coverage",
            required_points=POINTS[cid[-6:]],designated_ids=m["mapped_unit_ids"],original_evidence=g["evidence"],
            designated_full_sources=[allowed[s] for s in m["mapped_unit_ids"]],human_approved=False))
    shared.writel(ROOT/"cohort.jsonl",cohort)
    shutil.copy2(previous/"cohort.jsonl",ROOT/"previous_40_cohort.jsonl")
    (ROOT/"baseline_code").mkdir(exist_ok=True)
    for n in ("hr_answer","hr_evidence","hr_conditions","benefit_explanation"):
        shutil.copy2(REPO/"server"/(n+".py"),ROOT/"baseline_code"/(n+".py"))
    key,model=benefit_explanation.settings()
    write(ROOT/"protocol.json",dict(created_at=datetime.now(timezone.utc).isoformat(),
        baseline_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(),
        branch=subprocess.check_output(["git","branch","--show-current"],cwd=REPO,text=True).strip(),
        source_sha256=digest(CORPUS),gold_sha256=digest(shared.GOLD),mapping_sha256=digest(shared.MAPPING),
        cohort_sha256=digest(ROOT/"cohort.jsonl"),model=model,credential_configured=bool(key),
        source_summary=hr_evidence.summary(),baseline_codes={p.name:digest(p) for p in (ROOT/"baseline_code").glob("*.py")},
        target_cases=22,baseline_and_after_real_model_calls=True,previous_40_regression_questions=True,
        supabase_ingestion="HOLD_USER_REQUESTED",other_project_data_used=False,human_approved=False,
        acceptance="All22 question-relevant conditions/exceptions supported in prose; exact provenance; report refusals/errors, do not count source-card replay as a fresh successful model answer."))
    print(json.dumps(dict(cases=22,model=model,company="KEPCO",supabase_ingestion="HOLD"),ensure_ascii=False))


def generate(stage,workers,cases_only=None,regression=False):
    from server import hr_answer,hr_evidence
    answer=hr_answer
    os.environ['KLINK_HR_RETRIEVAL']='bm25' if stage=='baseline' else 'hybrid'
    if stage=="baseline":
        answer=load_frozen("hr_answer")
        answer.hr_evidence=load_frozen("hr_evidence")
        answer.hr_conditions=load_frozen("hr_conditions")
        answer.benefit_explanation=load_frozen("benefit_explanation")
    protocol=json.loads((ROOT/"protocol.json").read_text(encoding="utf-8"))
    assert digest(CORPUS)==protocol["source_sha256"] and digest(shared.GOLD)==protocol["gold_sha256"]
    cohort=readl(ROOT/("previous_40_cohort.jsonl" if regression else "cohort.jsonl"))
    if cases_only:cohort=[c for c in cohort if c["case_id"] in cases_only]
    hook=answer.validate
    current=threading.local()
    def checked(draft,sources,*a,**kw):
        try:return hook(draft,sources,*a,**kw)
        except answer.AnswerUnavailable as error:
            if not answer.hr_evidence.PRIVATE.search(draft.model_dump_json()):
                current.failures.append(dict(safe_reason=str(error),unvalidated_draft=draft.model_dump()))
            raise
    answer.validate=checked
    def one(case):
        path=ROOT/stage/"answers"/(case["case_id"]+".json")
        if path.exists():return None
        current.failures=[]
        start=time.monotonic()
        try:
            response=answer.generate(case["question"])
            error=None
        except answer.AnswerUnavailable as exc:
            response,error=None,dict(code=exc.code,safe_message=str(exc))
        record=dict(case_id=case["case_id"],question=case["question"],response=response,error=error,
            seconds=round(time.monotonic()-start,2),evaluation_mode="REAL_CONFIGURED_MODEL_RESPONSE_NOT_REPLAY",
            source_sha256=protocol["source_sha256"],human_approved=False)
        write(path,record)
        if current.failures:write(ROOT/stage/"rejected-local-only"/(case["case_id"]+".json"),current.failures)
        return dict(case_id=case["case_id"],status=(response or {}).get("status"),
            paragraphs=len((response or {}).get("paragraphs",[])),error=error,seconds=record["seconds"])
    write(ROOT/stage/"run-code.json",dict(files={p.name:digest(p) for p in (ROOT/"baseline_code").glob("*.py")} if stage=="baseline" else
        {n:digest(REPO/"server"/(n+".py")) for n in ("hr_answer","hr_evidence","hr_conditions","hr_vectors")},model=protocol["model"],
        retrieval='bm25' if stage=='baseline' else 'hybrid'))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(one,c) for c in cohort]):
            result=f.result()
            if result:print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=["prepare","generate"])
    p.add_argument("--stage",default="baseline")
    p.add_argument("--workers",type=int,choices=[1,2,3,4],default=2)
    p.add_argument("--cases",nargs="*")
    p.add_argument("--regression",action="store_true")
    args=p.parse_args()
    if args.command=="prepare":prepare()
    else:generate(args.stage,args.workers,args.cases,args.regression)
