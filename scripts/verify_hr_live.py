"""Verify the isolated live HR BFF. --live-llm performs three bounded, generic reference calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]


def verify():
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default="http://127.0.0.1:8826")
    parser.add_argument("--output", type=Path, default=ROOT.parent/"outputs/klink_hr_domain_20261107/live.json")
    parser.add_argument("--live-llm", action="store_true")
    parser.add_argument("--skip-connectivity", action="store_true", help="Do not probe credentials while the user edits .env")
    parser.add_argument("--llm-limit", type=int, choices=[1, 2, 3], default=3)
    args = parser.parse_args()
    report = dict(checks=[], llm_cases=[], actual_company_eligibility_validated=False, actual_submission=False)
    source = ROOT.parent/"outputs/kepco_hr_full_20261102/data/reviewed_units.jsonl"
    before = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None

    def check(value, name):
        if not value:
            raise AssertionError(name)
        report["checks"].append(name)

    with httpx.Client(base_url=args.origin, timeout=75) as client:
        check(client.get("/api/benefits/hr/capabilities").json()["app"] == "KLINK_HR_DOMAIN", "correct isolated HR service")
        check(client.get("/api/benefits/hr/catalog").status_code == 401, "authentication required")
        check(client.post("/api/benefits/session/demo").status_code == 200, "demo session created")
        profile = client.post("/api/benefits/profile/example").json()
        first = client.get("/api/benefits/hr/catalog").json()
        check(first["counts"] == dict(eligible=3, needs_review=2, ineligible=1), "six fictional policies return expected three-state counts")
        check(not first["production_eligibility_verified"], "fictional conditions do not become company eligibility")
        card = next(c for c in first["cards"] if c["id"] == "childcare")
        payload = dict(conditions_revision=first["conditions_revision"], policy_sha256=card["policy_sha256"])
        plan = client.post("/api/benefits/hr/preparations/childcare", json=payload).json()
        for index in range(len(plan["checklist"])):
            check(client.patch("/api/benefits/hr/preparations/"+plan["id"], json={"index":index,"checked":True}).status_code == 200, f"preparation checklist {index} recorded")
        check(client.post("/api/benefits/hr/preparations/"+plan["id"]+"/submit").status_code == 409, "real submission blocked")
        forms = client.get("/api/benefits/hr/forms").json()["forms"]
        check(len(forms) == 6 and not any(f["official_available"] for f in forms), "six form types remain honest about missing official company files")
        check(not client.get("/api/benefits/hr/updates").json()["enabled"], "reminders require opt-in")
        client.put("/api/benefits/hr/reminders", json={"enabled":True})
        check(any(x["kind"] == "deadline" for x in client.get("/api/benefits/hr/updates").json()["updates"]), "in-app example deadline detected")
        client.put("/api/benefits/profile", json=profile|dict(family_consent=False))
        changed = client.get("/api/benefits/hr/catalog").json()
        check(next(c for c in changed["cards"] if c["id"]=="childcare")["status"]=="needs_review", "revoked family scope yields unknown")
        check(client.get("/api/benefits/hr/preparations").json()["plans"][0]["stale"], "changed profile invalidates previous checklist")
        check(any(x["kind"] == "conditions_or_policy_changed" for x in client.get("/api/benefits/hr/updates").json()["updates"]), "personal-condition change detected")
        client.put("/api/benefits/profile", json=profile)
        queries = ["병가는 어떤 경우에 사용할 수 있나요?", "연차유급휴가의 기본 조건과 예외는 무엇인가요?", "육아휴직 기간은 어떤 조문에서 확인하나요?"]
        for case_index, question in enumerate(queries):
            result = client.get("/api/benefits/hr/evidence", params={"q":question})
            result.raise_for_status()
            data=result.json()
            check(bool(data["results"]) and data["company"] == "KEPCO" and not data["ktcs_applicable"], "actual local HR references retrieved: "+question)
            check(all(hashlib.sha256(r["text"].encode()).hexdigest()==r["sha256"] for r in data["results"]), "reference text hashes match: "+question)
            if args.live_llm and case_index < args.llm_limit:
                response = client.post("/api/benefits/hr/answer", json={"question":question})
                case=dict(question=question,http_status=response.status_code,result=response.json())
                report["llm_cases"].append(case)
                if response.status_code==200:
                    answer=response.json()
                    check(answer["company"]=="KEPCO" and answer["employee_data_sent"] is False and answer["human_approved"] is False, "live GPT remains a reference draft: "+question)
        client.delete("/api/benefits/profile")
        check(client.get("/api/benefits/hr/preparations").json()["plans"]==[], "revocation clears HR plans")
        check(not client.get("/api/benefits/hr/updates").json()["enabled"], "revocation clears reminder consent")
        report["readiness"] = client.get("/api/benefits/hr/readiness").json()
        check(not report["readiness"]["production_ready"], "unmet production gates remain blocked")
        report["connectivity"] = dict(status="pending_user_env_edit") if args.skip_connectivity else client.get("/api/benefits/config").json()["supabase"]
        client.delete("/api/benefits/session")
        check(client.get("/api/benefits/hr/catalog").status_code==401, "logout invalidates access")
    after = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
    check(before == after, "original HR corpus unchanged")
    report["corpus_sha256_before"] = before
    report["corpus_sha256_after"] = after
    report["check_count"] = len(report["checks"])
    report["llm_call_count"] = len(report["llm_cases"])
    report["llm_http_success"] = sum(c["http_status"] == 200 for c in report["llm_cases"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:report[k] for k in ["check_count","llm_call_count","llm_http_success","actual_company_eligibility_validated","actual_submission"]}))


if __name__ == "__main__":
    verify()
