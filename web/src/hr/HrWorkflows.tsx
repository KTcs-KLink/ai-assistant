import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Bell,
  CheckCheck,
  ClipboardCheck,
  Plus,
  RefreshCw,
} from "lucide-react";
import { EmployeeCaseAccess } from "./HrEmployee";
import { WorkspaceDialog } from "./HrWorkspaceShell";
import { control, dateTime, useControl, type CaseRecord } from "./operations";
import {
  APPROVAL_STATES,
  type Approval,
  type EmployeeInbox,
  type SourceOption,
  type Agent,
} from "./workflows";
import "./workflows.css";

function ErrorText({ text }: { text: string }) {
  return text ? (
    <p className="wf-error" role="alert">
      {text}
    </p>
  ) : null;
}
export function ApprovalRecord({ row }: { row: Approval }) {
  return (
    <div className="wf-record">
      <span className={"ops-badge " + row.state}>
        {APPROVAL_STATES[row.state]}
      </span>
      <h3>{row.title}</h3>
      <p className="wf-muted">
        {row.id} · {row.document_id} ·{" "}
        {row.kind === "source_change"
          ? "변경 파일 보관 검토"
          : row.job_kind === "verify"
            ? "원문 무결성 점검"
            : "공식 원문 재수집"}
      </p>
      <blockquote>{row.reason}</blockquote>
      {row.version && (
        <div className="wf-hashes">
          <span>
            현재 답변 원문<code>{row.version.baseline_sha}</code>
          </span>
          <span>
            검토할 수집 파일<code>{row.version.sha256}</code>
          </span>
        </div>
      )}
      {row.version && (
        <p>
          <a
            className="wf-inline-link"
            href={`/api/control/admin/versions/${row.version.id}/download`}
          >
            해시 확인된 변경 파일 내려받기 →
          </a>
        </p>
      )}
      {row.note && (
        <div className="wf-note">
          <strong>{row.reviewer ?? "처리 안내"}</strong>
          <p>{row.note}</p>
        </div>
      )}
      {row.job_id && (
        <p className="wf-muted">연결된 실제 작업 · {row.job_id}</p>
      )}
      <ol className="wf-timeline">
        {row.events.map((e, i) => (
          <li key={i}>
            <strong>{APPROVAL_STATES[e.state] ?? e.state}</strong>
            <small>
              {dateTime(e.at)} · {e.actor}
            </small>
            <p>{e.note}</p>
          </li>
        ))}
      </ol>
      <p className="wf-muted">
        로컬 운영 요청입니다. 회사 결재·KTcs 적용 승인을 뜻하지 않습니다. 변경
        파일은 검토 후에도 현재 답변 원문에 자동 반영되지 않습니다.
      </p>
    </div>
  );
}

export function HrEmployeeInbox() {
  return (
    <div className="emp-requests">
      <div className="emp-intro">
        <div>
          <p className="emp-eyebrow">MY INBOX</p>
          <h1>내 할 일</h1>
          <p>승인 요청과 문의 처리 안내를 한 곳에서 이어서 확인하세요.</p>
        </div>
        <span className="emp-account">로컬 운영 기록</span>
      </div>
      <EmployeeCaseAccess>{() => <EmployeeInboxContent />}</EmployeeCaseAccess>
    </div>
  );
}
function EmployeeInboxContent() {
  const query = useControl<EmployeeInbox>("/api/control/inbox", true, 30000);
  const [creating, setCreating] = useState(false),
    [selected, setSelected] = useState<Approval | null>(null),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const approvals = query.data?.approvals ?? [],
    notifications = query.data?.notifications ?? [];
  async function change(action: "cancel" | "resubmit") {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await control(`/api/control/approvals/${selected.id}`, "PATCH", {
        action,
        reason: reason.trim(),
        revision: selected.revision,
      });
      setSelected(null);
      query.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="wf-page">
      <div className="wf-stats">
        <div>
          <span>승인 대기</span>
          <strong>
            {approvals.filter((r) => r.state === "pending").length}
          </strong>
        </div>
        <div>
          <span>보완할 요청</span>
          <strong>
            {approvals.filter((r) => r.state === "needs_info").length}
          </strong>
        </div>
        <div>
          <span>새 처리 안내</span>
          <strong>{notifications.filter((n) => !n.read_at).length}</strong>
        </div>
      </div>
      <ErrorText text={error || query.error?.message || ""} />
      <div className="wf-columns">
        <section className="wf-panel">
          <header>
            <div>
              <ClipboardCheck size={19} />
              <h2>내 승인 요청</h2>
            </div>
            <button className="wf-primary" onClick={() => setCreating(true)}>
              <Plus size={15} />
              원문 점검 요청
            </button>
          </header>
          <p className="wf-muted">
            등록된 원문의 무결성 확인이나 공식 파일 재수집을 요청할 수 있습니다.
          </p>
          {query.loading && !query.data && (
            <p role="status">내 요청을 불러오고 있습니다.</p>
          )}
          {!query.loading && !approvals.length && (
            <div className="wf-empty">
              <ClipboardCheck size={28} />
              <h3>등록한 요청이 없습니다</h3>
              <p>원문을 다시 확인해야 할 때 점검을 요청하세요.</p>
            </div>
          )}
          {approvals.map((row) => (
            <button
              className="wf-list-row"
              key={row.id}
              onClick={() => {
                setSelected(row);
                setReason(row.reason);
                setError("");
              }}
            >
              <span>
                <strong>{row.title}</strong>
                <small>{dateTime(row.updated_at)}</small>
              </span>
              <span className={"ops-badge " + row.state}>
                {APPROVAL_STATES[row.state]}
              </span>
              <ArrowRight size={15} />
            </button>
          ))}
        </section>
        <section className="wf-panel">
          <header>
            <div>
              <Bell size={19} />
              <h2>처리 안내</h2>
            </div>
            <button
              className="wf-quiet"
              aria-label="내 할 일 새로고침"
              onClick={query.refresh}
            >
              <RefreshCw size={16} />
            </button>
          </header>
          {!notifications.length && (
            <div className="wf-empty">
              <Bell size={28} />
              <h3>새 안내가 없습니다</h3>
              <p>문의 배정과 승인 처리 결과가 여기에 도착합니다.</p>
            </div>
          )}
          {notifications.map((n) => (
            <article
              className={"wf-notification " + (!n.read_at ? "unread" : "")}
              key={n.id}
            >
              <strong>{n.title}</strong>
              <p>{n.detail}</p>
              <small>{dateTime(n.created_at)}</small>
              <footer>
                <Link to={n.target}>
                  내용 확인 <ArrowRight size={13} />
                </Link>
                {!n.read_at && (
                  <button
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await control(
                          `/api/control/notifications/${n.id}/read`,
                          "POST",
                          {},
                        );
                        query.refresh();
                      } catch (e) {
                        setError(
                          e instanceof Error
                            ? e.message
                            : "확인하지 못했습니다.",
                        );
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    <CheckCheck size={14} />
                    읽음
                  </button>
                )}
              </footer>
            </article>
          ))}
        </section>
      </div>
      {creating && (
        <ApprovalRequest
          close={() => setCreating(false)}
          saved={() => {
            setCreating(false);
            query.refresh();
          }}
        />
      )}
      {selected && (
        <WorkspaceDialog title="승인 요청 상세" close={() => setSelected(null)}>
          <div className="wf-dialog">
            <ApprovalRecord row={selected} />
            {selected.state === "needs_info" && (
              <label>
                보완 설명
                <textarea
                  rows={4}
                  maxLength={1000}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
            )}
            <ErrorText text={error} />
            <footer>
              {selected.state === "needs_info" && (
                <button
                  className="wf-primary"
                  disabled={busy || reason.trim().length < 5}
                  onClick={() => void change("resubmit")}
                >
                  보완 후 다시 요청
                </button>
              )}
              {["pending", "needs_info"].includes(selected.state) && (
                <button
                  className="wf-secondary"
                  disabled={busy}
                  onClick={() => void change("cancel")}
                >
                  요청 취소
                </button>
              )}
            </footer>
          </div>
        </WorkspaceDialog>
      )}
    </div>
  );
}
function ApprovalRequest({
  close,
  saved,
}: {
  close: () => void;
  saved: () => void;
}) {
  const sources = useControl<{ items: SourceOption[] }>(
    "/api/control/workflow-sources",
  );
  const [documentId, setDocumentId] = useState(""),
    [kind, setKind] = useState("verify"),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await control("/api/control/approvals", "POST", {
        document_id: documentId,
        job_kind: kind,
        reason: reason.trim(),
      });
      saved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "요청하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <WorkspaceDialog title="원문 점검 요청" close={close}>
      <form className="wf-dialog wf-form" onSubmit={submit}>
        <p className="wf-note">
          관리자가 승인하면 실제 원문 점검 작업이 실행됩니다. 현재 답변 원문과
          검색 범위는 유지합니다.
        </p>
        <label>
          대상 원문
          <select
            required
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
          >
            <option value="">원문 선택</option>
            {sources.data?.items.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title} · {d.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          요청할 작업
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="verify">보관 원문 무결성 점검</option>
            <option value="recollect">공식 출처에서 다시 수집</option>
          </select>
        </label>
        <label>
          요청 사유
          <textarea
            required
            minLength={5}
            maxLength={1000}
            rows={4}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="개인정보 없이 확인할 내용을 적어주세요."
          />
        </label>
        <ErrorText text={error || sources.error?.message || ""} />
        <footer>
          <button
            className="wf-primary"
            disabled={busy || !documentId || reason.trim().length < 5}
          >
            {busy ? "등록 중…" : "승인 요청 등록"}
          </button>
        </footer>
      </form>
    </WorkspaceDialog>
  );
}

export function AnswerFeedback({ requestId }: { requestId: string }) {
  const [open, setOpen] = useState(false),
    [reason, setReason] = useState("근거 불일치"),
    [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [sent, setSent] = useState(false),
    [error, setError] = useState("");
  if (sent)
    return (
      <p className="wf-feedback-sent" role="status">
        답변 검토를 요청했습니다. 처리 안내는{" "}
        <Link to="/hr/inbox">내 할 일</Link>에서 확인하세요.
      </p>
    );
  return (
    <div className="wf-feedback">
      <button className="wf-quiet" onClick={() => setOpen(true)}>
        답변 검토 요청
      </button>
      <small>이 답변의 요청 기록에 연결</small>
      {open && (
        <WorkspaceDialog title="답변 검토 요청" close={() => setOpen(false)}>
          <form
            className="wf-dialog wf-form"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                await control(`/api/control/feedback/${requestId}`, "POST", {
                  reason,
                  note: note.trim(),
                });
                setSent(true);
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "등록하지 못했습니다.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <p className="wf-note">
              질문·답변 본문을 추가 저장하지 않고 요청 번호와 검토 사유를
              연결합니다. 확인할 조문 번호를 적어주시면 검토에 도움이 됩니다.
            </p>
            <label>
              검토 사유
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              >
                {["근거 불일치", "조건·예외 확인", "답변 이해 어려움"].map(
                  (r) => (
                    <option key={r}>{r}</option>
                  ),
                )}
              </select>
            </label>
            <label>
              추가 설명
              <textarea
                value={note}
                maxLength={500}
                rows={4}
                onChange={(e) => setNote(e.target.value)}
                placeholder="개인정보나 회사 비공개 내용을 입력하지 마세요."
              />
            </label>
            <ErrorText text={error} />
            <footer>
              <button className="wf-primary" disabled={busy}>
                {busy ? "등록 중…" : "검토 요청 등록"}
              </button>
            </footer>
          </form>
        </WorkspaceDialog>
      )}
    </div>
  );
}

export function CaseAssignment({
  row,
  saved,
}: {
  row: CaseRecord;
  saved: () => void;
}) {
  const agents = useControl<{ items: Agent[] }>("/api/control/admin/agents"),
    [agentId, setAgentId] = useState(row.agent_id ?? ""),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function assign(mode: string) {
    setBusy(true);
    setError("");
    try {
      await control(`/api/control/admin/cases/${row.id}/assignment`, "PATCH", {
        revision: row.revision,
        mode,
        agent_id: agentId || null,
        reason: reason.trim(),
      });
      saved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "배정하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="wf-assignment">
      <strong>담당자 · {row.team || "팀 미지정"}</strong>
      <p>
        {row.agent_name ?? "배정 대기"} · 목표{" "}
        {row.due_at ? dateTime(row.due_at) : "미설정"}
      </p>
      <small>{row.assignment_reason}</small>
      {!["resolved", "cancelled"].includes(row.state) && (
        <>
          <label>
            담당자 선택
            <select
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
            >
              <option value="">담당자 선택</option>
              {agents.data?.items
                .filter((a) => a.active)
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} · {a.team} · {a.open_cases}/{a.capacity}건
                  </option>
                ))}
            </select>
          </label>
          <label>
            배정 사유
            <input
              value={reason}
              maxLength={300}
              onChange={(e) => setReason(e.target.value)}
              placeholder="자동 재배정 또는 변경 사유"
            />
          </label>
          <ErrorText text={error || agents.error?.message || ""} />
          <div className="wf-actions">
            <button
              type="button"
              className="wf-secondary"
              disabled={busy || reason.trim().length < 5}
              onClick={() => void assign("auto")}
            >
              규칙으로 다시 배정
            </button>
            <button
              type="button"
              className="wf-primary"
              disabled={busy || !agentId || reason.trim().length < 5}
              onClick={() => void assign("manual")}
            >
              선택 담당자에 배정
            </button>
          </div>
        </>
      )}
    </section>
  );
}
