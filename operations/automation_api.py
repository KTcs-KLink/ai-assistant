"""Permission-scoped local workflow API. No company SSO or production approval claims."""
import json
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import automation as flow, corpus, store


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Revision(Strict):
    revision: int = Field(ge=1)


class ApprovalIn(Strict):
    document_id: str = Field(max_length=80)
    job_kind: Literal["verify", "recollect"] = "verify"
    reason: str = Field(min_length=5, max_length=1000)


class Decision(Revision):
    state: Literal["approved", "rejected", "needs_info"]
    note: str = Field(min_length=5, max_length=1000)


class Resubmit(Revision):
    action: Literal["cancel", "resubmit"]
    reason: str = Field(default="", max_length=1000)


class Rule(Strict):
    category: Literal["규정 문의", "양식 문의", "AI 답변 확인", "서비스 이용"]
    team: Literal["인사 운영", "양식 지원", "AI 품질", "서비스 지원"]
    sla_hours: int = Field(ge=1, le=168)


class Config(Revision):
    watch_enabled: bool
    watch_documents: list[str] = Field(max_length=5)
    watch_interval_minutes: int = Field(ge=15, le=10080)
    cost_warning_percent: int = Field(ge=1, le=100)
    slow_seconds: int = Field(ge=5, le=540)
    routing: list[Rule] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def complete_rules(self):
        if {r.category for r in self.routing} != set(flow.CATEGORIES):
            raise ValueError("네 문의 분류의 규칙을 각각 한 개씩 지정해 주세요.")
        if self.watch_enabled and not self.watch_documents:
            raise ValueError("자동 점검할 원문을 선택해 주세요.")
        return self


class AgentIn(Strict):
    name: str = Field(min_length=2, max_length=40)
    team: Literal["인사 운영", "양식 지원", "AI 품질", "서비스 지원"]
    active: bool = True
    capacity: int = Field(default=20, ge=1, le=100)


class AgentUpdate(AgentIn, Revision):
    pass


class Assignment(Revision):
    mode: Literal["auto", "manual"]
    agent_id: str | None = Field(default=None, max_length=40)
    reason: str = Field(min_length=5, max_length=300)


class AlertUpdate(Revision):
    state: Literal["acknowledged", "open"]


class FeedbackIn(Strict):
    reason: Literal["근거 불일치", "조건·예외 확인", "답변 이해 어려움"]
    note: str = Field(default="", max_length=500)


class FeedbackUpdate(Revision):
    state: Literal["resolved", "dismissed"]
    resolution: str = Field(min_length=5, max_length=1000)


def categories(session):
    return {"owner": ["cost", "quality", "source", "routing"], "analyst": ["cost", "quality"],
            "hr_admin": ["quality", "routing", "source"], "data_admin": ["source"]}.get(session["role"], [])


def create_router(permission, session_for, safe_text, submit):
    router = APIRouter(prefix="/api/control")

    def checked(value, minimum=5):
        value = safe_text(value)
        if len(value) < minimum:
            raise HTTPException(422, f"공백을 제외하고 {minimum}글자 이상 입력해 주세요.")
        return value

    @router.get("/workflow-counts")
    def workflow_counts(request: Request, admin: bool = False):
        s = session_for(request, admin=admin)
        with store.connect() as c:
            if not admin:
                unread = c.execute("SELECT count(*) FROM notifications WHERE owner=? AND read_at IS NULL", (s["id"],)).fetchone()[0]
                needs_info = c.execute("SELECT count(*) FROM approvals WHERE owner=? AND state='needs_info'", (s["id"],)).fetchone()[0]
                return dict(todo=unread+needs_info, unread=unread)
            allowed = categories(s)
            placeholders = ",".join("?" for _ in allowed) or "NULL"
            alerts = c.execute(f"SELECT count(*) FROM alerts WHERE state='open' AND category IN ({placeholders})", allowed).fetchone()[0]
            pending = c.execute("SELECT count(*) FROM approvals WHERE state='pending'").fetchone()[0] if s["role"] in {"owner", "hr_admin", "data_admin"} else 0
            return dict(alerts=alerts, pending_approvals=pending)

    @router.get("/workflow-sources")
    def workflow_sources(request: Request):
        session_for(request)
        try:
            data = corpus.load()
        except (ValueError, OSError, KeyError):
            raise HTTPException(503, "검증된 원문 목록을 확인하지 못했습니다.") from None
        return dict(items=[{k: d[k] for k in ["id", "title", "sha256", "source_url"]} for d in data["documents"]])

    @router.get("/inbox")
    def inbox(request: Request):
        s = session_for(request)
        return dict(approvals=flow.approval_items(s["id"]),
                    notifications=store.rows("SELECT id,title,detail,target,created_at,read_at FROM notifications WHERE owner=? ORDER BY created_at DESC LIMIT 200", (s["id"],)),
                    mode="LOCAL_DEMO", actual_hr_submission=False)

    @router.post("/notifications/{notification_id}/read")
    def read_notification(notification_id: str, request: Request):
        s = session_for(request)
        with store.connect() as c:
            if not c.execute("UPDATE notifications SET read_at=COALESCE(read_at,?) WHERE id=? AND owner=?", (store.now(), notification_id, s["id"])).rowcount:
                raise HTTPException(404, "본인의 알림을 찾을 수 없습니다.")
        return dict(read=True)

    @router.post("/approvals", status_code=201)
    def request_approval(payload: ApprovalIn, request: Request):
        s = session_for(request)
        reason = checked(payload.reason)
        try:
            _, docs = corpus.selected([payload.document_id])
        except (ValueError, OSError, KeyError):
            raise HTTPException(422, "검증된 원문을 선택해 주세요.") from None
        if payload.job_kind == "recollect" and not docs[0]["source_url"]:
            raise HTTPException(422, "공식 재수집 주소가 등록되지 않은 원문입니다.")
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT count(*) FROM approvals WHERE owner=?", (s["id"],)).fetchone()[0] >= 100:
                raise HTTPException(429, "체험 요청 한도에 도달했습니다.")
            if c.execute("SELECT id FROM approvals WHERE owner=? AND document_id=? AND job_kind=? AND state IN ('pending','needs_info')", (s["id"], payload.document_id, payload.job_kind)).fetchone():
                raise HTTPException(409, "같은 원문의 요청이 이미 대기 중입니다.")
            uid = store.uid("APR")
            c.execute("INSERT INTO approvals(id,owner,requester,kind,title,document_id,job_kind,reason,created_at,updated_at) VALUES(?,?,?,'source_check',?,?,?,?,?,?)",
                      (uid, s["id"], s["actor"], docs[0]["title"], payload.document_id, payload.job_kind, reason, store.now(), store.now()))
            flow.event(c, uid, s["actor"], "pending", reason)
            store.audit(c, s["actor"], "approval_requested", uid, dict(document_id=payload.document_id))
        return dict(id=uid, state="pending", actual_hr_submission=False)

    @router.patch("/approvals/{approval_id}")
    def resubmit(approval_id: str, payload: Resubmit, request: Request):
        s = session_for(request)
        reason = safe_text(payload.reason)
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM approvals WHERE id=? AND owner=?", (approval_id, s["id"])).fetchone()
            if not row:
                raise HTTPException(404, "본인의 요청을 찾을 수 없습니다.")
            if row["revision"] != payload.revision or row["state"] not in {"pending", "needs_info"}:
                raise HTTPException(409, "최신 요청 상태를 다시 불러와 주세요.")
            if payload.action == "resubmit" and (row["state"] != "needs_info" or len(reason) < 5):
                raise HTTPException(422, "보완 요청에 대한 설명을 다섯 글자 이상 입력해 주세요.")
            state = "cancelled" if payload.action == "cancel" else "pending"
            c.execute("UPDATE approvals SET state=?,reason=?,note='',revision=revision+1,updated_at=? WHERE id=?", (state, reason or row["reason"], store.now(), approval_id))
            flow.event(c, approval_id, s["actor"], state, reason)
            store.audit(c, s["actor"], "approval_" + payload.action, approval_id)
        return dict(state=state)

    @router.get("/admin/approvals")
    def approvals(s=Depends(permission("approvals"))):
        return dict(items=flow.approval_items(), active_service_changed=False)

    @router.post("/admin/approvals/{approval_id}/decide")
    def decide(approval_id: str, payload: Decision, s=Depends(permission("jobs"))):
        note = checked(payload.note)
        row = store.rows("SELECT kind FROM approvals WHERE id=?", (approval_id,))
        if row and row[0]["kind"] == "source_change" and payload.state == "needs_info":
            raise HTTPException(422, "자동 변경 후보는 보관 검토 승인 또는 보류로 처리해 주세요.")
        job = flow.decide(approval_id, payload.state, note, payload.revision, s)
        if job:
            submit(flow.run_job, *job)
        return dict(state=payload.state, job_id=job[0] if job else None, active_service_changed=False)

    @router.get("/admin/automation")
    def configuration(s=Depends(permission("health"))):
        config = store.setting("automation")
        config.pop("updated_at", None)
        return dict(config=config, teams=flow.TEAMS, categories=flow.CATEGORIES,
                    runtime=store.rows("SELECT * FROM watch_runtime WHERE id=1")[0],
                    checks=store.rows("SELECT * FROM source_checks ORDER BY checked_at DESC"),
                    versions=store.rows("SELECT * FROM source_versions ORDER BY checked_at DESC LIMIT 100"),
                    mode="LOCAL_DEMO", active_service_changed=False)

    @router.put("/admin/automation")
    def configure(payload: Config, s=Depends(permission("settings"))):
        if payload.watch_documents:
            try:
                _, docs = corpus.selected(payload.watch_documents)
            except (ValueError, OSError, KeyError):
                raise HTTPException(422, "실제 등록된 원문을 선택해 주세요.") from None
            if any(not d["source_url"] for d in docs):
                raise HTTPException(422, "공식 주소가 있는 문서만 자동 점검할 수 있습니다.")
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            current = json.loads(c.execute("SELECT value FROM settings WHERE id='automation'").fetchone()[0])
            if payload.revision != current["revision"]:
                raise HTTPException(409, "설정이 변경됐습니다. 다시 불러와 주세요.")
            value = payload.model_dump()
            value.update(revision=payload.revision+1)
            watch_changed = any(value[k] != current[k] for k in ["watch_enabled", "watch_documents", "watch_interval_minutes"])
            c.execute("UPDATE settings SET value=? WHERE id='automation'", (json.dumps(value, ensure_ascii=False),))
            if watch_changed:
                c.execute("UPDATE watch_runtime SET next_due=?,last_error='' WHERE id=1", (time.time()+60,))
            store.audit(c, s["actor"], "automation_configured", detail=value)
        flow.reconcile()
        return value

    @router.post("/admin/automation/check", status_code=202)
    def check_now(s=Depends(permission("jobs"))):
        cfg = store.setting("automation")
        if not cfg["watch_documents"]:
            raise HTTPException(422, "점검할 원문을 먼저 저장해 주세요.")
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            job = flow.enqueue(c, "recollect", cfg["watch_documents"], s["actor"])
            c.execute("UPDATE watch_runtime SET last_job=?,next_due=?,last_error='' WHERE id=1", (job, time.time()+cfg["watch_interval_minutes"]*60))
        submit(flow.run_job, job, "recollect", cfg["watch_documents"])
        return dict(id=job, state="queued", active_service_changed=False)

    @router.get("/admin/versions/{version_id}/download")
    def download_version(version_id: str, s=Depends(permission("sources"))):
        rows = store.rows("SELECT * FROM source_versions WHERE id=?", (version_id,))
        if not rows:
            raise HTTPException(404, "보관된 변경 파일이 없습니다.")
        row = rows[0]
        try:
            _, docs = corpus.selected([row["document_id"]])
            content = (store.DATA / "artifacts" / row["job_id"] / (row["document_id"] + ".source")).read_bytes()
            import hashlib
            if len(content) > 32*1024*1024 or hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise ValueError("hash mismatch")
        except (ValueError, OSError, KeyError):
            raise HTTPException(409, "검토 파일의 무결성을 확인하지 못했습니다.") from None
        suffix = docs[0]["format"].lower().lstrip(".")
        suffix = suffix if suffix in {"pdf", "hwp", "hwpx", "docx", "xlsx", "zip"} else "bin"
        filename = f"{row['document_id']}-{row['sha256'][:12]}.{suffix}"
        with store.connect() as c:
            store.audit(c, s["actor"], "source_candidate_downloaded", version_id)
        return Response(content, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    @router.get("/admin/agents")
    def agents(s=Depends(permission("cases"))):
        return dict(items=store.rows("""SELECT a.*,count(k.id) AS open_cases FROM agents a LEFT JOIN cases k
            ON k.agent_id=a.id AND k.state NOT IN ('resolved','cancelled') GROUP BY a.id ORDER BY a.team,a.name"""), teams=flow.TEAMS, identity_connected=False)

    @router.post("/admin/agents", status_code=201)
    def create_agent(payload: AgentIn, s=Depends(permission("settings"))):
        name = checked(payload.name, 2)
        with store.connect() as c:
            if c.execute("SELECT count(*) FROM agents").fetchone()[0] >= 100:
                raise HTTPException(429, "로컬 담당자 한도에 도달했습니다.")
            uid = store.uid("AGT")
            c.execute("INSERT INTO agents VALUES(?,?,?,?,?,1,?)", (uid, name, payload.team, int(payload.active), payload.capacity, store.now()))
            store.audit(c, s["actor"], "routing_agent_created", uid, dict(identity_connected=False))
        return dict(id=uid)

    @router.patch("/admin/agents/{agent_id}")
    def update_agent(agent_id: str, payload: AgentUpdate, s=Depends(permission("settings"))):
        name = checked(payload.name, 2)
        with store.connect() as c:
            if not c.execute("UPDATE agents SET name=?,team=?,active=?,capacity=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?",
                             (name, payload.team, int(payload.active), payload.capacity, store.now(), agent_id, payload.revision)).rowcount:
                raise HTTPException(409, "담당자 설정이 변경됐습니다. 다시 불러와 주세요.")
            store.audit(c, s["actor"], "routing_agent_updated", agent_id)
        return dict(id=agent_id)

    @router.patch("/admin/cases/{case_id}/assignment")
    def assign(case_id: str, payload: Assignment, s=Depends(permission("cases"))):
        reason = checked(payload.reason)
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
            if not row or row["revision"] != payload.revision or row["state"] in {"resolved", "cancelled"}:
                raise HTTPException(409, "처리 중인 최신 문의를 다시 불러와 주세요.")
            if payload.mode == "auto":
                flow.route_case(c, case_id, force=True)
            else:
                agent = c.execute("SELECT * FROM agents WHERE id=? AND active=1", (payload.agent_id,)).fetchone()
                if not agent:
                    raise HTTPException(422, "활동 중인 담당자를 선택해 주세요.")
                load = c.execute("SELECT count(*) FROM cases WHERE agent_id=? AND id!=? AND state NOT IN ('resolved','cancelled')", (agent["id"], case_id)).fetchone()[0]
                if load >= agent["capacity"]:
                    raise HTTPException(409, "해당 담당자의 처리 한도에 도달했습니다.")
                c.execute("UPDATE cases SET agent_id=?,team=?,assignment_reason=?,routing_locked=1,revision=revision+1,updated_at=? WHERE id=?",
                          (agent["id"], agent["team"], reason, store.now(), case_id))
                flow.notify(c, row["owner"], f"manual:{case_id}:{payload.revision+1}", "문의 담당자 변경", agent["team"] + " · " + agent["name"], "/hr/requests")
            store.audit(c, s["actor"], "case_assignment_changed", case_id, dict(mode=payload.mode, reason=reason))
        flow.reconcile()
        return dict(id=case_id)

    @router.get("/admin/alerts")
    def alerts(request: Request):
        s = session_for(request, admin=True)
        flow.reconcile()
        allowed = categories(s)
        placeholders = ",".join("?" for _ in allowed) or "NULL"
        items = store.rows(f"SELECT * FROM alerts WHERE category IN ({placeholders}) ORDER BY CASE state WHEN 'open' THEN 0 WHEN 'acknowledged' THEN 1 ELSE 2 END,updated_at DESC LIMIT 200", allowed)
        feedback = store.rows("SELECT f.id,f.request_id,f.reason,f.note,f.state,f.resolution,f.created_at,f.updated_at,f.revision,r.status,r.answer_state,r.latency_ms FROM feedback f JOIN requests r ON r.id=f.request_id ORDER BY f.updated_at DESC LIMIT 100") if "quality" in allowed else []
        return dict(items=items, feedback=feedback, allowed_categories=allowed, semantic_accuracy_measured=False)

    @router.patch("/admin/alerts/{alert_id}")
    def acknowledge(alert_id: str, payload: AlertUpdate, request: Request):
        s = session_for(request, admin=True)
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
            if not row or row["category"] not in categories(s):
                raise HTTPException(404, "현재 역할에서 확인할 수 있는 알림이 아닙니다.")
            if row["revision"] != payload.revision or row["state"] == "resolved":
                raise HTTPException(409, "알림 상태가 변경됐습니다. 다시 불러와 주세요.")
            c.execute("UPDATE alerts SET state=?,revision=revision+1,updated_at=? WHERE id=?", (payload.state, store.now(), alert_id))
            store.audit(c, s["actor"], "alert_" + payload.state, alert_id)
        return dict(id=alert_id)

    @router.post("/feedback/{request_id}", status_code=201)
    def feedback(request_id: str, payload: FeedbackIn, request: Request):
        s = session_for(request)
        note = safe_text(payload.note)
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT id FROM requests WHERE id=? AND owner_session=? AND completed_at IS NOT NULL AND status=200", (request_id, s["id"])).fetchone()
            if not row:
                raise HTTPException(404, "이 접속에서 받은 완료 답변을 찾을 수 없습니다.")
            if c.execute("SELECT id FROM feedback WHERE request_id=?", (request_id,)).fetchone():
                raise HTTPException(409, "이미 검토를 요청한 답변입니다.")
            uid = store.uid("FDB")
            c.execute("INSERT INTO feedback(id,request_id,owner,reason,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (uid, request_id, s["id"], payload.reason, note, store.now(), store.now()))
            store.audit(c, s["actor"], "answer_feedback_created", uid, dict(request_id=request_id))
        flow.reconcile()
        return dict(id=uid, state="open", human_approved=False)

    @router.patch("/admin/feedback/{feedback_id}")
    def resolve_feedback(feedback_id: str, payload: FeedbackUpdate, request: Request):
        s = session_for(request, admin=True)
        if s["role"] not in {"owner", "hr_admin"}:
            raise HTTPException(403, "인사 운영 또는 전체 관리자 권한이 필요합니다.")
        resolution = checked(payload.resolution)
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM feedback WHERE id=?", (feedback_id,)).fetchone()
            if not row or row["revision"] != payload.revision or row["state"] != "open":
                raise HTTPException(409, "최신 검토 요청을 다시 불러와 주세요.")
            c.execute("UPDATE feedback SET state=?,resolution=?,updated_at=?,revision=revision+1 WHERE id=?", (payload.state, resolution, store.now(), feedback_id))
            flow.notify(c, row["owner"], "feedback:" + feedback_id, "답변 검토 처리 안내", resolution, "/hr/inbox")
            store.audit(c, s["actor"], "answer_feedback_reviewed", feedback_id, dict(state=payload.state, semantic_accuracy_certified=False))
        flow.reconcile()
        return dict(id=feedback_id, semantic_accuracy_certified=False)

    return router
