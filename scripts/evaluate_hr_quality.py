"""Local, checkpointed HR quality experiment. Never writes to a database or changes sources.

The frozen gold questions/rubrics are evaluation inputs only, never retrieval inputs.
No credentials, employee profiles, SDK exception bodies or request headers are saved.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parent
ROOT = WORKSPACE / "outputs/klink_hr_answer_quality_20261107"
CORPUS = WORKSPACE / "outputs/kepco_hr_full_20261102/data/reviewed_units.jsonl"
GOLD = WORKSPACE / "outputs/kepco_hr_gold_960_20261102/data/golden_set.jsonl"
MAPPING = WORKSPACE / "outputs/kepco_hr_full_eval_960_20261102/data/gold_map.jsonl"
sys.path.insert(0, str(REPO))
os.environ["KLINK_LOCAL_REVIEWED_UNITS"] = str(CORPUS)
os.environ["KLINK_ENV_FILE"] = str(WORKSPACE / ".env")


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda:file.read(1048576),b''):value.update(block)
    return value.hexdigest()


def readl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def writel(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values), encoding="utf-8")


def load_baseline(name):
    alias = "server.quality_frozen_" + name
    spec = importlib.util.spec_from_file_location(alias, ROOT / "baseline_code" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


SELECTION = {
    1: [1, 12, 30, 10, 29], 2: [7, 14, 16, 8, 13],
    3: [1, 3, 12, 13, 2], 4: [1, 6, 9, 7, 15],
    5: [1, 39, 22, 26, 28], 6: [2, 3, 15, 6, 16],
    7: [1, 3, 7, 6, 15], 8: [2, 4, 8, 6, 13],
}

# Codex source-comparison checklist. These are test expectations, not human-approved rules.
# The complete original evidence is retained alongside each checklist; no short reference
# answer is used as an exhaustive oracle.
REQUIREMENTS = {
    "01-001": ["공개경쟁 원칙", "성별·신체조건·용모·학력·연령 등의 불합리한 제한 및 임직원 가족 우대 금지", "특수분야 전문직종 등의 제한경쟁 예외: 동일 조건 다수인 대상", "예외 시 직위·직무특성에 맞춘 구체적 기준/자격 사전 공개"],
    "01-012": ["입사제출서류 허위사실 발견자는 채용 불가", "허위사실에도 재량으로 채용 가능하다고 말하지 않음"],
    "01-030": ["비대치직군 정원 증가 또는 결원 발생 때에 한함", "송전담당(나)·배전담당(나)는 적격심사 부적격자 보직이라는 단서 보존"],
    "01-010": ["수시 특별채용 가능 사유: 법령, 긴급, 운동선수", "상임인사위원회 방침", "채용분야·자격·직급·승진인정일자 등 세부사항도 상임인사위원회가 정함", "삭제된 사유를 현행 사유로 복원하지 않음"],
    "01-029": ["확정된 채용대상자는 반환 청구 대상에서 제외", "채용여부 확정 후 본인 확인", "채용절차 공정화법/시행령 절차 준용", "반환 비용은 원칙적으로 공사 부담"],
    "02-007": ["재계약 대상자 제외, 고용권자가 지정한 날까지", "이력서(사진), 학력/경력(필요시), 주민등록등본/주민등록증 사본", "신원진술서(필요시), 자격증(필요시), 선서·서약서(인사관리규정 별표3), 기타 필요서류", "필요시 서류를 무조건 제출이라고 바꾸지 않음"],
    "02-014": ["일 단위 계약, 원칙 1년 이상", "예외 사유 발생일부터 종료일까지 가능", "예외: 휴직 대체인력, 특정 연구프로젝트 완성, 전력연구원 직접 연구 및 관련 실험·조사 지원", "삭제된 예외를 유효한 것으로 말하지 않음"],
    "02-016": ["만료 후 6개월 이내 재계약 시 공백을 계속근무 간주", "오직 재계약 판단에 한정, 임금·퇴직급여 전체로 일반화하지 않음", "다른 공사 내 사업소 근무도 포함", "4개월 공백은 위 기준 이내이나 자동 재고용 승인 아님"],
    "02-008": ["서면 계약", "기간, 근로시간/휴게, 임금 구성/계산/지불방법", "휴일/휴가, 장소/업무", "근로일·근로일별 근로시간은 단시간 근로자에 한함"],
    "02-013": ["신원보증보험증권으로 신원보증 대체 가능", "신원조사 및 보증은 총무규정 제4장 제1절 준용", "제공되지 않은 총무규정 세부절차 창작 금지"],
    "03-001": ["적재적소: 업무 소요자격에 가장 적합", "기회균등: 자력에 적합한 업무 기회", "욕구충족은 가능한 한이며 희망 보직 절대 보장 아님"],
    "03-003": ["교육·출장·파견·휴가·휴직·정년대기 등 6개월 이상", "출산전후휴가에 이어 제51조7호 육아휴직 3개월 이상이라는 별도 조건", "동일직급 정원이 따로 있는 것으로 보아 보충 가능, 자동 의무 아님"],
    "03-012": ["4직급 동일 1차사업소 10년 이상이면 타 1차사업소 이동 원칙", "이동기준 등 별도 세부기준", "업무상 필요에 따라 보직권자 승인 시 예외"],
    "03-013": ["직위 및 직무내용 유사", "담당업무 수행에 지장 없다고 인정", "위 조건 충족 시 겸직 명령 가능"],
    "03-002": ["직원 능력·경험·욕구", "업무 양·난이도·성격 종합 고려", "형평에 맞게 부여"],
    "04-001": ["휴게시간 제외 실근무 1일8시간/주40시간/주5일 원칙", "토요일 휴무, 일요일 유급 주휴일 구분", "정부지시 시 따름, 유연근무제 별도"],
    "04-006": ["통상근무자 낮12시~오후1시 원칙", "업무사정에 따라 달리 운영 가능", "일률적 고정 또는 무조건 자유 선택으로 바꾸지 않음"],
    "04-009": ["사전 소속장 승인 원칙", "불가피하면 당일이라도 사유 명확히 하여 사후승인", "정당한 이유 없이 절차 미이행 시 무단결근"],
    "04-007": ["자유 이용 가능", "공사 질서·규율 문란하게 하지 않는 한도"],
    "04-015": ["임신 여성 직원 연장근무 금지", "해당 직원 요구 시 쉬운 근무로 전환"],
    "05-001": ["1년간80%이상 출근:15일", "3년이상 근속: 최초1년 초과 근속 매2년 1일 가산", "가산 포함 총25일 한도"],
    "05-009": ["직무수행 불가/요양 필요 또는 감염병 전염우려 조건의 유급휴가 부여 가능", "일반 병가 연60일", "업무상 공상 연180일, 동일 사유 재직중1회"],
    "05-022": ["만8세이하 또는 초등2학년이하(입양 포함) 자녀 남녀 직원의 양육", "여성 임신·출산도 대상", "자녀1인3년이내, 분할가능", "육아휴직 신청 시 명하여야 함, 불이익금지", "현행 법률/KTCS 규정이라고 일반화하지 않음"],
    "05-026": ["조기복직: 복직30일전 복직원", "연장: 만료30일전 본인이 직접 사유 명시 신청", "연장은 제52조 한도 내, 무제한/자동 연장 아님"],
    "05-028": ["특별휴가자·휴직자 국외출국 전 공사에 보고", "방문목적·방문국가·체류기간·연락방법·연락처 등", "원문에 없는 주/일 단위 기한·승인권자 창작 금지"],
    "05-039": ["비정규직관리규정 제22조5항: 산재보험법 업무상 부상·질병 연60일 이내 병가 가능", "취업규칙 제30조의2 공상: 연180일, 동일사유 재직중1회", "서로 다른 규정/적용 범위로 구분하고 동일직원에게 자동 유리한 기준 적용 단정 금지"],
    "06-002": ["매월25일", "휴일 또는 토요일이면 전일", "계약서 양식의 다른 날짜를 모든 직원에게 적용 금지"],
    "06-003": ["신규채용: 발령일부터 일할", "승진·이동 등 신분변경: 발령일부터 일할", "질문 범위 아닌 퇴직 예외를 신규/승진에 잘못 적용하지 않음"],
    "06-015": ["입사일부터 퇴직 또는 사망일까지", "취업규칙54조 단서에도 불구", "연미만 월할, 월미만 절상 구분"],
    "06-006": ["기본연봉월액·직무급·가산급", "내부평가급 최소지급분 12분의1, 직무평가급 최소지급분 12분의1", "제외대상 별도라는 한계, 전직원 무조건 포함 단정 금지"],
    "06-016": ["생존 본인, 사망 유족 청구에 지급", "유족범위는 근로기준법 시행령", "제공되지 않은 유족순위/범위 창작 금지"],
    "07-001": ["지급기준일 현재 고등학교·대학 입학/재학 자녀 직원", "계약직원·예비군지휘관·청원경찰·상근촉탁 포함, 임원제외", "기준일: 고교2/5/8/11월말, 대학2/8월말"],
    "07-003": ["대학 학자금은 보조금 아닌 무이자 대부", "자녀수 제한없음, 등록금 실비 전액", "해외대학 연10000달러 한도와 지급월 제1근무일 최초 현찰 살때 환율이라는 해외 예외(해외도 전액이라고 일반화할 때 필수)"],
    "07-007": ["산재보험법상 근로복지공단 업무상재해 인정", "미가입 사업장은 공사 인정", "미가입 재해: 공단 승인기준, 자체 보상심의위원회 심의후 승인"],
    "07-006": ["해외지사 주재원 자녀 현지 초중고 입학/재학, 증빙", "자녀1인 월600USD, 연7200USD", "초과시 주관부서장 사전승인", "초과액65% 추가지급"],
    "07-015": ["매년1회이상", "지정의료기관 정기검진", "필요시 수시 실시 가능"],
    "08-002": ["출석 및 성적 미달: 낙제", "교육원 교육명령 수명자: 정당이유 없는 불출석 또는 중대한 위배는 퇴교", "모든 성적 미달을 퇴교라고 합치지 않음"],
    "08-004": ["일반 위탁교육 근태 교육, 학비지원형 휴직", "일반 인력개발 제비용 공사부담, 학비지원형 교육비만 부담"],
    "08-008": ["해외1개월이상 또는 국내6개월이상 위탁교육 이수자", "교육기간3배, 월환산 후 월미만 일수 절상", "1인교육비10만달러 초과시 최소2년, 그외 최소1년"],
    "08-006": ["교육총괄부서장, 결정권자 승인", "학위취득곤란/성적불량 및 보직변경 등 사유시", "휴학 또는 교육중지 명령 및 소환 가능, 무조건 자동중지 아님"],
    "08-013": ["업적: 협의한 목표 대비 기간중 실적", "역량: 협의한 역량요소, 공통·리더십(또는 공통)과 직무역량 구분", "중간평정자 없으면 확인평정자가 피평정자와 협의·평정"],
}


def prepare():
    from server import hr_evidence, benefit_explanation
    if (ROOT / "protocol.json").exists():
        raise SystemExit("Frozen protocol already exists; use it without overwriting.")
    ROOT.mkdir(parents=True, exist_ok=True)
    for name in ("hr_answer", "hr_evidence"):
        (ROOT / "baseline_code").mkdir(exist_ok=True)
        shutil.copy2(REPO / "server" / (name + ".py"), ROOT / "baseline_code" / (name + ".py"))
    allowed = {r["id"]: r for r in hr_evidence.corpus()[0]}
    gold = {r["case_id"]: r for r in readl(GOLD)}
    mappings = {r["case_id"]: r for r in readl(MAPPING)}
    cohort = []
    for task, numbers in SELECTION.items():
        for i, number in enumerate(numbers):
            identifier = f"KEPCO-HR-{task:02d}-{number:03d}"
            g, m = gold[identifier], mappings[identifier]
            assert m["all_gold_answer_eligible"] and set(m["mapped_unit_ids"]) <= allowed.keys()
            evidence = g["evidence"]
            for ev in evidence:
                assert hashlib.sha256(ev["quote"].encode()).hexdigest() == ev["quote_sha256"]
            cohort.append(dict(case_id=identifier, task_code=g["task_code"], task_name=g["task_name"],
                split="development" if i < 3 else "held_out_from_fix_selection", question=g["question"],
                designated_ids=m["mapped_unit_ids"], original_evidence=evidence,
                designated_full_sources=[allowed[s] for s in m["mapped_unit_ids"]],
                required_points=REQUIREMENTS[identifier[-6:]], checklist_human_approved=False))
    dev = {s for c in cohort if c["split"] == "development" for s in c["designated_ids"]}
    held = {s for c in cohort if c["split"] != "development" for s in c["designated_ids"]}
    assert not dev & held, "Question split must be disjoint at designated source-unit level"
    writel(ROOT / "cohort.jsonl", cohort)
    key, model = benefit_explanation.settings()
    write(ROOT / "protocol.json", dict(created_at=datetime.now(timezone.utc).isoformat(),
        branch=subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip(),
        baseline_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        model=model, credential_configured=bool(key), source_sha256=digest(CORPUS), gold_sha256=digest(GOLD),
        mapping_sha256=digest(MAPPING), cohort_sha256=digest(ROOT / "cohort.jsonl"),
        baseline_code={n: digest(ROOT / "baseline_code" / (n + ".py")) for n in ("hr_answer", "hr_evidence")},
        source_summary=hr_evidence.summary(), development_cases=24, held_out_cases=16,
        all_questions=960, source_unit_disjoint_split=True, full_document_disjoint_split=False,
        held_out_definition="Fixed before generation; not used to select fixes. Source documents are shared.",
        source_scope="449 automatically allowed KEPCO HR units; no KTCS applicability or human approval",
        no_supabase_calls=True, no_employee_data=True, preserve_all_attempts=True,
        judging="Codex source-derived checklist + configured-model automated semantic review; neither human nor independent expert approval",
        complete_rule="All question-relevant conditions, exceptions and required points supported; no unsupported claim; withheld/error/empty is not a complete answer",
        full_semantic_evaluation_of_543_or_960=False))
    print(json.dumps({"protocol": str(ROOT / "protocol.json"), "development":24, "held_out":16, "model":model}, ensure_ascii=False))


def retrieve(stage):
    from server import hr_evidence
    evidence = load_baseline("hr_evidence") if stage == "baseline" else hr_evidence
    allowed = {s["id"] for s in evidence.corpus()[0]}
    mapping = {r["case_id"]:r for r in readl(MAPPING)}
    result = []
    started = time.monotonic()
    for g in readl(GOLD):
        m = mapping[g["case_id"]]
        eligible = m["all_gold_answer_eligible"] and set(m["mapped_unit_ids"]) <= allowed
        hits = evidence.search(g["question"], 5)
        ids = [h["id"] for h in hits]
        required = set(m["mapped_unit_ids"])
        row = dict(case_id=g["case_id"], task_code=g["task_code"], fully_inside_runtime=eligible,
            designated_ids=sorted(required), retrieved_ids=ids,
            all_at_3=bool(required) and required<=set(ids[:3]), all_at_5=bool(required) and required<=set(ids),
            any_at_3=bool(required&set(ids[:3])), any_at_5=bool(required&set(ids)))
        if stage != "baseline" and hasattr(evidence,"bundle"):
            bundle=evidence.bundle(g["question"])
            row.update(bundle_ids=[s["id"] for s in bundle["sources"]],
                all_in_bundle=bool(required) and required<={s["id"] for s in bundle["sources"]},
                unresolved=bundle.get("unresolved_dependencies",[]))
        result.append(row)
    writel(ROOT / stage / "retrieval.jsonl",result)
    eligible=[r for r in result if r["fully_inside_runtime"]]
    from collections import Counter
    summary=dict(total=960,fully_inside_runtime=len(eligible),out_of_runtime=960-len(eligible),
        metrics={key:dict(numerator=sum(bool(r[key]) for r in eligible), denominator=len(eligible)) for key in ("all_at_3","all_at_5","any_at_3","any_at_5")},
        by_task={t:dict(total=sum(r["task_code"]==t for r in eligible),all_at_3=sum(r["task_code"]==t and r["all_at_3"] for r in eligible)) for t in sorted({r["task_code"] for r in result})},
        seconds=round(time.monotonic()-started,2),source_sha256=digest(CORPUS),semantic_accuracy=False)
    if eligible and "all_in_bundle" in eligible[0]:summary["metrics"]["all_in_bundle"]=dict(numerator=sum(r["all_in_bundle"] for r in eligible),denominator=len(eligible))
    write(ROOT / stage / "retrieval-summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


def generate(stage, split, workers, only_cases=None):
    from server import hr_answer
    if stage == "baseline":
        evidence=load_baseline("hr_evidence")
        answer=load_baseline("hr_answer")
        answer.hr_evidence=evidence
    else:
        answer=hr_answer
    protocol=json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
    assert protocol["source_sha256"]==digest(CORPUS)
    cases=[c for c in readl(ROOT / "cohort.jsonl") if (split=="all" or c["split"]==split) and (not only_cases or c["case_id"] in only_cases)]
    if stage!="baseline":
        original_validate=answer.validate
        current=threading.local()
        def captured_validation(draft,sources,*args,**kwargs):
            try:return original_validate(draft,sources,*args,**kwargs)
            except answer.AnswerUnavailable as error:
                safe=draft.model_dump()
                if not answer.hr_evidence.PRIVATE.search(json.dumps(safe,ensure_ascii=False)):
                    write(ROOT / stage / "withheld-candidates-local-only" / (current.case_id+".json"),
                        dict(case_id=current.case_id,withheld_not_user_visible=True,unvalidated_draft=safe,
                            safe_reason=str(error),source_ids=[s["id"] for s in sources]))
                raise
        answer.validate=captured_validation
    def one(case):
        destination=ROOT / stage / "answers" / (case["case_id"]+".json")
        if destination.exists():return dict(case_id=case["case_id"],cached=True)
        start=time.monotonic()
        if stage!="baseline":current.case_id=case["case_id"]
        try:
            response=answer.generate(case["question"])
            record=dict(case_id=case["case_id"],split=case["split"],question=case["question"],response=response,
                error=None,seconds=round(time.monotonic()-start,2))
        except answer.AnswerUnavailable as error:
            record=dict(case_id=case["case_id"],split=case["split"],question=case["question"],response=None,
                error=dict(code=error.code,safe_message=str(error)),seconds=round(time.monotonic()-start,2))
        write(destination,record)
        return dict(case_id=case["case_id"],status=(record["response"] or {}).get("status"),
            paragraphs=len((record["response"] or {}).get("paragraphs",[])),error=record["error"],seconds=record["seconds"])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs=[pool.submit(one,c) for c in cases]
        for future in as_completed(jobs):print(json.dumps(future.result(),ensure_ascii=False),flush=True)
    write(ROOT / stage / "code-fingerprints.json",dict(source_sha256=digest(CORPUS),
        files={n:digest(REPO / "server" / (n+".py")) for n in ("hr_answer","hr_evidence")}))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["prepare","retrieve","generate"])
    parser.add_argument("--stage",default="baseline")
    parser.add_argument("--split",default="development",choices=["all","development","held_out_from_fix_selection"])
    parser.add_argument("--workers",type=int,default=2,choices=[1,2])
    parser.add_argument("--cases",nargs="*",help="Explicit case IDs for a preserved diagnostic run")
    args=parser.parse_args()
    if args.command=="prepare":prepare()
    elif args.command=="retrieve":retrieve(args.stage)
    elif args.command=="generate":generate(args.stage,args.split,args.workers,args.cases)


if __name__=="__main__":main()
