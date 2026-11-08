import { useState, type FormEvent } from "react";
import {
  Check,
  ChevronRight,
  FileClock,
  MessageSquareText,
  RefreshCw,
  Search,
  Send,
} from "lucide-react";
import { WorkspaceDialog } from "../HrWorkspaceShell";
import {
  CASE_STATES,
  control,
  dateTime,
  useControl,
  type AuditRecord,
  type CaseRecord,
} from "../operations";
import { Badge, Empty, Loading, PageTitle, QueryError } from "./ui";

export function AdminCases() {
  const query = useControl<{ items: CaseRecord[] }>("/api/control/admin/cases"),
    [filter, setFilter] = useState("all"),
    [q, setQ] = useState(""),
    [selected, setSelected] = useState<CaseRecord | null>(null),
    [notice, setNotice] = useState("");
  const items = query.data?.items ?? [],
    filtered = items.filter(
      (row) =>
        (filter === "all" || row.state === filter) &&
        (row.title + row.id + row.category).includes(q),
    );
  return (
    <>
      <PageTitle
        eyebrow="HR SERVICE DESK"
        title="직원 문의"
        description="문의의 맥락을 확인하고, 상태와 처리 안내를 한 곳에서 관리하세요."
      >
        <button className="ops-secondary" onClick={query.refresh}>
          <RefreshCw size={14} />
          새로고침
        </button>
      </PageTitle>
      <QueryError error={query.error} retry={query.refresh} />
      {notice && (
        <p className="ops-success" role="status">
          <Check size={15} />
          {notice}
        </p>
      )}
      <div className="ops-case-summary">
        <div>
          <span className="ops-dot blue" />
          신규 접수{" "}
          <strong>{items.filter((r) => r.state === "received").length}</strong>
        </div>
        <div>
          <span className="ops-dot amber" />
          진행·추가 확인{" "}
          <strong>
            {
              items.filter((r) =>
                ["in_review", "awaiting_info"].includes(r.state),
              ).length
            }
          </strong>
        </div>
        <div>
          <span className="ops-dot green" />
          완료{" "}
          <strong>{items.filter((r) => r.state === "resolved").length}</strong>
        </div>
        <span>로컬 문의 체험 · 실제 회사 신청·결재 미연결</span>
      </div>
      <section className="ops-panel">
        <div className="ops-table-toolbar">
          <label className="ops-search">
            <Search size={16} />
            <input
              aria-label="직원 문의 검색"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              maxLength={100}
              placeholder="제목·분야·문의 번호 검색"
            />
          </label>
          <select
            aria-label="직원 문의 상태"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">모든 상태</option>
            {Object.entries(CASE_STATES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        {query.loading && !query.data ? (
          <Loading />
        ) : filtered.length ? (
          <div className="ops-table-scroll">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>문의 제목</th>
                  <th>분야</th>
                  <th>상태</th>
                  <th>최근 변경</th>
                  <th>처리</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <button
                        className="ops-document-name"
                        onClick={() => setSelected(row)}
                      >
                        <span className="ops-file-icon">
                          <MessageSquareText size={18} />
                        </span>
                        <span>
                          <strong>{row.title}</strong>
                          <small>{row.id}</small>
                        </span>
                      </button>
                    </td>
                    <td>{row.category}</td>
                    <td>
                      <Badge state={row.state}>{CASE_STATES[row.state]}</Badge>
                    </td>
                    <td className="ops-muted">{dateTime(row.updated_at)}</td>
                    <td>
                      <button
                        className="ops-text-button"
                        onClick={() => setSelected(row)}
                      >
                        상세·처리
                        <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="접수된 문의가 없습니다."
            description="직원 화면에서 로컬 문의를 등록하면 이 큐에 표시됩니다."
            to="/hr/requests"
            action="직원 문의 화면 보기"
          />
        )}
      </section>
      {selected && (
        <CaseEditor
          key={selected.id + ":" + selected.revision}
          row={selected}
          close={() => setSelected(null)}
          saved={() => {
            setSelected(null);
            query.refresh();
            setNotice(
              "상태와 처리 안내를 저장했습니다. 직원이 같은 체험 세션에서 확인할 수 있습니다.",
            );
          }}
        />
      )}
    </>
  );
}
function CaseEditor({
  row,
  close,
  saved,
}: {
  row: CaseRecord;
  close: () => void;
  saved: () => void;
}) {
  const [state, setState] = useState(
      row.state === "cancelled" ? "received" : row.state,
    ),
    [reply, setReply] = useState(row.reply),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await control(`/api/control/admin/cases/${row.id}`, "PATCH", {
        state,
        reply: reply.trim(),
        revision: row.revision,
      });
      saved();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "처리하지 못했습니다.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <WorkspaceDialog title="문의 확인·처리" close={close}>
      <form className="ops-form ops-case-editor" onSubmit={save}>
        <div>
          <Badge state={row.state}>{CASE_STATES[row.state]}</Badge>
          <small>
            {row.id} · {row.category}
          </small>
        </div>
        <h3>{row.title}</h3>
        <blockquote>{row.body}</blockquote>
        <p className="ops-muted">
          접수 {dateTime(row.created_at)} · 마지막 변경{" "}
          {dateTime(row.updated_at)}
        </p>
        {row.state === "cancelled" ? (
          <div className="ops-inline-note">
            직원이 취소한 문의입니다. 기록은 보존되며 다시 처리하지 않습니다.
          </div>
        ) : (
          <>
            <label>
              처리 상태
              <select value={state} onChange={(e) => setState(e.target.value)}>
                {["received", "in_review", "awaiting_info", "resolved"].map(
                  (value) => (
                    <option key={value} value={value}>
                      {CASE_STATES[value]}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label>
              직원이 확인할 처리 안내
              <textarea
                rows={6}
                maxLength={1500}
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                placeholder="확인한 내용과 다음 절차를 적어주세요. 개인정보는 입력하지 마세요."
              />
            </label>
            <p className="ops-form-note">
              로컬 문의 상태와 안내만 변경합니다. 휴가·지급 승인이나 실제 회사
              결재가 아닙니다. 외부 이메일·메신저 알림은 보내지 않습니다.
            </p>
            {error && (
              <p role="alert" className="ops-error">
                {error}
              </p>
            )}
            <button
              className="ops-primary"
              disabled={
                busy ||
                (["awaiting_info", "resolved"].includes(state) &&
                  reply.trim().length < 5)
              }
            >
              <Send size={14} />
              {busy ? "저장 중…" : "상태·안내 저장"}
            </button>
          </>
        )}
      </form>
    </WorkspaceDialog>
  );
}

const AUDIT_NAMES: Record<string, string> = {
  demo_session_started: "체험 접속 시작",
  case_created: "직원 문의 등록",
  case_cancelled: "문의 취소",
  case_updated: "문의 상태·안내 변경",
  job_queued: "데이터 작업 접수",
  job_completed: "데이터 작업 완료",
  job_cancelled: "작업 중지 요청",
  review_recorded: "원문 검토 기록 저장",
  policy_saved: "예산·서비스 정책 변경",
  rate_saved_future_requests_only: "모델 계산 단가 변경",
  diagnostics_run: "서비스 진단 실행",
};
export function AdminAudit() {
  const query = useControl<{ items: AuditRecord[] }>(
      "/api/control/admin/audit",
    ),
    [q, setQ] = useState(""),
    [detail, setDetail] = useState<AuditRecord | null>(null),
    items = (query.data?.items ?? []).filter((item) =>
      (AUDIT_NAMES[item.action] + item.actor + item.target).includes(q),
    );
  return (
    <>
      <PageTitle
        eyebrow="AUDIT TRAIL"
        title="변경 이력"
        description="누가 어떤 작업을 실행했는지 확인하세요. 이 화면에서 기록을 수정·삭제하지 않습니다."
      >
        <button className="ops-secondary" onClick={query.refresh}>
          <RefreshCw size={14} />
          새로고침
        </button>
      </PageTitle>
      <QueryError error={query.error} retry={query.refresh} />
      <section className="ops-panel">
        <div className="ops-table-toolbar">
          <label className="ops-search">
            <Search size={16} />
            <input
              aria-label="변경 이력 검색"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="작업·체험 담당자·대상 ID 검색"
              maxLength={100}
            />
          </label>
          <span>최근 300개 기록</span>
        </div>
        {query.loading && !query.data ? (
          <Loading />
        ) : items.length ? (
          <div className="ops-table-scroll">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>시각</th>
                  <th>작업</th>
                  <th>실행 주체</th>
                  <th>대상</th>
                  <th>세부 정보</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="ops-muted">{dateTime(item.at)}</td>
                    <td>
                      <span className="ops-audit-action">
                        <FileClock size={15} />
                        {AUDIT_NAMES[item.action] ?? "운영 작업"}
                      </span>
                    </td>
                    <td>{item.actor}</td>
                    <td className="ops-mono">
                      {item.target || "워크스페이스"}
                    </td>
                    <td>
                      <button
                        className="ops-text-button"
                        onClick={() => setDetail(item)}
                      >
                        상세
                        <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="일치하는 변경 기록이 없습니다."
            description="로컬 운영 화면에서 실행한 작업만 기록됩니다."
          />
        )}
      </section>
      <p className="ops-page-footnote">
        현재 로컬 운영 저장소의 활동 이력입니다. 공급자 계정·회사 SSO·다른
        백엔드의 전체 감사 로그는 포함하지 않습니다.
      </p>
      {detail && (
        <WorkspaceDialog title="변경 기록 상세" close={() => setDetail(null)}>
          <div className="ops-audit-detail">
            <h3>{AUDIT_NAMES[detail.action] ?? "운영 작업"}</h3>
            <dl className="ops-key-values">
              <dt>시각</dt>
              <dd>{dateTime(detail.at)}</dd>
              <dt>실행 주체</dt>
              <dd>{detail.actor}</dd>
              <dt>대상</dt>
              <dd>{detail.target || "워크스페이스"}</dd>
            </dl>
            <details>
              <summary>기록된 변경 값</summary>
              <pre>{JSON.stringify(JSON.parse(detail.detail), null, 2)}</pre>
            </details>
            <p className="ops-muted">
              키·직원 프로필·질문·답변 본문은 이 기록에 포함하지 않습니다.
            </p>
          </div>
        </WorkspaceDialog>
      )}
    </>
  );
}
