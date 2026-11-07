"""Bounded local runtime state. No raw profile, question or credential is logged."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import secrets
import time
from threading import RLock

from fastapi import HTTPException

LOCK = RLock()
WINDOWS: dict[str, tuple[float, int]] = {}
COUNTS: Counter = Counter()


def limit(bucket: str, subject: str, maximum: int, seconds: int):
    key = hashlib.sha256((bucket+":"+subject).encode()).hexdigest()
    now = time.monotonic()
    with LOCK:
        for expired in [k for k, (until, _) in WINDOWS.items() if until <= now]:
            WINDOWS.pop(expired, None)
        until, count = WINDOWS.get(key, (now+seconds, 0))
        if count >= maximum:
            raise HTTPException(429, "요청이 많아요. 잠시 후 다시 시도해 주세요.", headers={"Retry-After": str(max(1, int(until-now)))})
        if len(WINDOWS) >= 5000 and key not in WINDOWS:
            raise HTTPException(503, "현재 요청이 많아요. 잠시 후 다시 시도해 주세요.")
        WINDOWS[key] = until, count+1


def record(event: str):
    if event not in {"profile_saved", "consent_revoked", "plan_created", "plan_stale", "answer_checked", "answer_rejected", "login_rejected", "logout", "reminders_changed"}:
        raise ValueError("unrecognized audit event")
    with LOCK:
        COUNTS[event] += 1


def state(session: dict) -> dict:
    with LOCK:
        current = session.setdefault("hr", dict(profile_hash="", revision=secrets.token_urlsafe(12), plans={}, reminders=False, snapshot=None, answering=False))
        encoded = json.dumps(session["profile"].consented().model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
        if current["profile_hash"] and current["profile_hash"] != fingerprint:
            current["revision"] = secrets.token_urlsafe(12)
            for plan in current["plans"].values():
                plan.update(stale=True, checked=[])
        current["profile_hash"] = fingerprint
        return current


def aggregate() -> dict:
    with LOCK:
        return dict(COUNTS)
