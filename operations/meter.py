"""Count provider-reported usage once, never store questions or answers."""
from __future__ import annotations

import calendar
import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from . import store


def local_day():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def price(usage, rate):
    if not rate or not usage:
        return None
    inp, out = usage.get("input_tokens"), usage.get("output_tokens")
    details = usage.get("input_tokens_details") or {}
    cached, write = details.get("cached_tokens", 0), details.get("cache_write_tokens", 0)
    if any(type(v) is not int or v < 0 for v in [inp, out, cached, write]) or cached + write > inp:
        return None
    amount = (Decimal(inp - cached - write) * Decimal(rate["input"]) + Decimal(cached) * Decimal(rate["cached"])
              + Decimal(write) * Decimal(rate["write"]) + Decimal(out) * Decimal(rate["output"])) / Decimal(1000000)
    return format(amount.quantize(Decimal("0.000000001")), "f")


def start_request():
    policy = store.setting("policy")
    day = str(local_day())
    request_id = store.uid("REQ")
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        if policy["maintenance"]:
            return None, (503, "지금은 AI 서비스를 점검 중입니다. 원문 검색은 이용할 수 있습니다.")
        daily = c.execute("SELECT count(*) FROM requests WHERE day=?", (day,)).fetchone()[0]
        if daily >= policy["daily_request_limit"]:
            return None, (429, "오늘의 AI 질문 한도에 도달했습니다. 관리자에게 문의해 주세요.")
        if policy["budget_action"] == "block":
            monthly = c.execute("SELECT cost_usd FROM requests WHERE day>=?", (day[:7] + "-01",)).fetchall()
            # A missing receipt is never treated as a free request.
            if any(r[0] is None for r in monthly):
                return None, (429, "미집계 비용이 있어 예산 차단 정책에 따라 새 AI 요청을 보류했습니다.")
            if sum((Decimal(r[0]) for r in monthly), Decimal(0)) >= Decimal(policy["monthly_budget_usd"]):
                return None, (429, "이번 달 집계 비용이 설정한 한도에 도달했습니다. 원문 검색을 이용해 주세요.")
        c.execute("INSERT INTO requests(id,started_at,day) VALUES(?,?,?)", (request_id, store.now(), day))
    return request_id, None


def finish(request_id, status, elapsed_ms, receipt=None):
    calls = receipt.get("provider_calls") if isinstance(receipt, dict) else None
    rates = {r["model"]: r for r in store.setting("rates")}
    complete = isinstance(calls, list)
    totals = dict(input_tokens=0, output_tokens=0, cached_tokens=0)
    total_cost = Decimal(0)
    cost_known = complete
    with store.connect() as c:
        for call in calls or []:
            model = call.get("model") or receipt.get("model") or "unreported"
            usage = call.get("usage")
            valid = isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ["input_tokens", "output_tokens"])
            details = usage.get("input_tokens_details") or {} if valid else {}
            cached, write = details.get("cached_tokens", 0), details.get("cache_write_tokens", 0)
            valid = valid and type(cached) is int and type(write) is int and 0 <= cached + write <= usage["input_tokens"]
            if not valid:
                complete = False
            rate = rates.get(model)
            cost = price(usage, rate) if valid else None
            if cost is None:
                cost_known = False
            else:
                total_cost += Decimal(cost)
            for key in totals:
                totals[key] += (cached if key == "cached_tokens" else usage.get(key, 0)) if valid else 0
            c.execute("INSERT INTO generations(request_id,phase,model,input_tokens,output_tokens,cached_tokens,write_tokens,cost_usd,rate_snapshot) VALUES(?,?,?,?,?,?,?,?,?)",
                      (request_id, call.get("phase", "unreported"), model, usage["input_tokens"] if valid else None,
                       usage["output_tokens"] if valid else None, cached if valid else None, write if valid else None, cost,
                       json.dumps(rate) if rate else None))
        c.execute("UPDATE requests SET completed_at=?,status=?,latency_ms=?,answer_state=?,call_count=?,usage_complete=?,input_tokens=?,output_tokens=?,cached_tokens=?,cost_usd=?,model=?,validation=? WHERE id=?",
                  (store.now(), status, elapsed_ms, receipt.get("status") if receipt else None,
                   len(calls) if isinstance(calls, list) else None, int(complete),
                   *(totals[k] if complete else None for k in ["input_tokens", "output_tokens", "cached_tokens"]),
                   str(total_cost) if cost_known and complete else None,
                   receipt.get("model") if receipt else None, receipt.get("validation") if receipt else None, request_id))


def summary(days=7):
    today = local_day()
    first = today - timedelta(days=days - 1)
    requests = store.rows("SELECT * FROM requests WHERE day>=? ORDER BY started_at DESC", (str(first),))
    monthly = store.rows("SELECT * FROM requests WHERE day>=?", (str(today.replace(day=1)),))
    def aggregate(rows):
        measured = [r for r in rows if r["usage_complete"]]
        priced = [r for r in rows if r["cost_usd"] is not None]
        return dict(requests=len(rows), completed=sum(r["completed_at"] is not None for r in rows),
                    failed=sum(r["status"] is not None and r["status"] >= 400 for r in rows),
                    measured_requests=len(measured), unknown_usage=len(rows)-len(measured),
                    unpriced_requests=len(rows)-len(priced),
                    provider_calls=sum(r["call_count"] or 0 for r in rows),
                    input_tokens=sum(r["input_tokens"] or 0 for r in measured),
                    output_tokens=sum(r["output_tokens"] or 0 for r in measured),
                    cached_tokens=sum(r["cached_tokens"] or 0 for r in measured),
                    known_cost_usd=str(sum((Decimal(r["cost_usd"]) for r in priced), Decimal(0))))
    daily = []
    for offset in range(days):
        date = str(first + timedelta(days=offset))
        daily.append(dict(day=date, **aggregate([r for r in requests if r["day"] == date])))
    times = sorted(r["latency_ms"] for r in requests if r["latency_ms"] is not None)
    return dict(period_days=days, totals=aggregate(requests), monthly=aggregate(monthly), daily=daily,
                requests=requests[:100], median_latency_ms=times[len(times)//2] if times else None,
                rates=store.setting("rates"), policy=store.setting("policy"),
                started_at=store.rows("SELECT min(started_at) AS at FROM requests")[0]["at"],
                currency="USD", timezone="Asia/Seoul", cost_method="PROVIDER_USAGE_X_VERSIONED_RATE_ESTIMATE_NOT_INVOICE",
                history_scope="Only requests passing this local gateway since metering began; prior or direct 8846 requests excluded")
