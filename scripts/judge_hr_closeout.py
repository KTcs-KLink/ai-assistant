"""Original-source comparison for the closeout cohort; no replay as new generation."""
import argparse
import sys
import time
from pathlib import Path
import judge_hr_quality as judge
from closeout_hr_quality import ROOT


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser()
    p.add_argument('--stage',default='baseline')
    p.add_argument('--workers',type=int,default=2,choices=[1,2,3])
    p.add_argument('--regression',action='store_true')
    p.add_argument('--follow',action='store_true')
    args=p.parse_args()
    judge.ROOT=ROOT
    judge.INSTRUCTIONS+=' 공통 notice의 한국전력 공개 수집자료라는 정보는 출처/파일 해시 확인 이력에 따른 사실이므로 단순히 본문에 공개라는 단어가 없다는 이유로 감점하지 마라. 질문의 각 대상과 예외를 따로 검토하라. 본문이 등으로 질문의 핵심 대상을 누락하면 엄격히 판단하라. source_conditions는 이번 본문 점수에 포함하지 않는다. omissions.original_quote는 실제 원문의 연속 구간만 그대로 복사하라. 떨어진 구간을 붙이지 마라. unsupported_claims.answer_claim은 후보 본문 또는 missing_information에 실제 존재하는 연속 문자열만 복사하라.'
    cohort=ROOT/('previous_40_cohort.jsonl' if args.regression else 'cohort.jsonl')
    name='regression-prose-review' if args.regression else 'source-prose-review'
    deadline=time.monotonic()+2400
    while True:
        judge.review(args.stage,args.workers,name,cohort,check_all_visible_fields=True)
        expected={c['case_id'] for c in judge.readl(cohort)}
        done={p.stem for p in (ROOT/args.stage/name).glob('KEPCO-HR-*.json')}
        if not args.follow or expected<=done:break
        if time.monotonic()>deadline:raise SystemExit('Review follow deadline exceeded; unfinished cases remain visible.')
        time.sleep(5)
