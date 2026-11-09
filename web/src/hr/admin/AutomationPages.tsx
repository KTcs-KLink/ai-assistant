import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Bell,
  Check,
  ClipboardCheck,
  FileClock,
  Play,
  RefreshCw,
  Users,
} from "lucide-react";
import { WorkspaceDialog } from "../HrWorkspaceShell";
import { ApprovalRecord } from "../HrWorkflows";
import {
  control,
  dateTime,
  useControl,
  type SourceCatalog,
} from "../operations";
import {
  ALERT_CATEGORIES,
  ALERT_STATES,
  APPROVAL_STATES,
  type Agent,
  type Alerts,
  type Approval,
  type AutomationConfig,
  type AutomationState,
  type Feedback,
} from "../workflows";
import { useAdmin } from "./context";
import { Empty, Loading, PageTitle, QueryError, Stat } from "./ui";
import "../workflows.css";

export function AdminApprovals() {
  const session = useAdmin(),
    query = useControl<{ items: Approval[] }>(
      "/api/control/admin/approvals",
      true,
      30000,
    );
  const [filter, setFilter] = useState("pending"),
    [selected, setSelected] = useState<Approval | null>(null),
    [notice, setNotice] = useState("");
  const rows = query.data?.items ?? [];
  return (
    <>
      <PageTitle
        eyebrow="UNIFIED INBOX"
        title="통합 승인함"
        description="원문 점검 요청과 변경 파일 검토를 한 곳에서 처리하세요."
      >
        <button className="ops-secondary" onClick={query.refresh}>
          <RefreshCw size={14} />
          새로고침
        </button>
      </PageTitle>
      <div className="ops-stats">
        <Stat
          label="승인 대기"
          value={rows.filter((r) => r.state === "pending").length}
          note="처리가 필요한 요청"
        />
        <Stat
          label="변경 후보"
          value={
            rows.filter(
              (r) => r.kind === "source_change" && r.state === "pending",
            ).length
          }
          note="공식 파일 바이트 비교"
        />
        <Stat
          label="보완 요청"
          value={rows.filter((r) => r.state === "needs_info").length}
          note="신청자 보완 대기"
        />
      </div>
      <QueryError error={query.error} retry={query.refresh} />
      {notice && (
        <p className="ops-success" role="status">
          <Check size={15} />
          {notice}
        </p>
      )}
      <section className="wf-panel">
        <header>
          <div>
            <ClipboardCheck size={19} />
            <h2>처리할 요청</h2>
          </div>
          <select
            aria-label="승인 상태 필터"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">모든 상태</option>
            {Object.entries(APPROVAL_STATES).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </header>
        {query.loading && !query.data ? (
          <Loading />
        ) : !rows.filter((r) => filter === "all" || r.state === filter)
            .length ? (
          <Empty
            title="해당하는 요청이 없습니다"
            description="직원이 원문 점검을 요청하거나 공식 파일 변경이 감지되면 여기에 표시됩니다."
          />
        ) : (
          rows
            .filter((r) => filter === "all" || r.state === filter)
            .map((r) => (
              <button
                className="wf-list-row"
                key={r.id}
                onClick={() => setSelected(r)}
              >
                <span className="wf-row-icon">
                  <FileClock size={19} />
                </span>
                <span>
                  <strong>{r.title}</strong>
                  <small>
                    {r.requester} ·{" "}
                    {r.kind === "source_change"
                      ? "변경 파일 보관 검토"
                      : "원문 점검·재수집"}{" "}
                    · {dateTime(r.updated_at)}
                  </small>
                </span>
                <span className={"ops-badge " + r.state}>
                  {APPROVAL_STATES[r.state]}
                </span>
                <span>상세 보기 →</span>
              </button>
            ))
        )}
        <p className="wf-note">
          점검 승인 시 실제 작업을 실행합니다. 변경 파일 보관 검토 승인은
          파싱·검색 반영이나 회사 규정 적용 승인이 아닙니다.
        </p>
      </section>
      {selected && (
        <ApprovalDecision
          key={selected.id}
          row={selected}
          canDecide={session.permissions.includes("jobs")}
          close={() => setSelected(null)}
          saved={() => {
            setSelected(null);
            query.refresh();
            setNotice(
              "처리 결과를 기록했습니다. 연결된 작업과 처리 이력을 확인하세요.",
            );
          }}
        />
      )}
    </>
  );
}
function ApprovalDecision({
  row,
  close,
  saved,
  canDecide,
}: {
  row: Approval;
  close: () => void;
  saved: () => void;
  canDecide: boolean;
}) {
  const [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function decide(state: string) {
    setBusy(true);
    setError("");
    try {
      await control(`/api/control/admin/approvals/${row.id}/decide`, "POST", {
        state,
        note: note.trim(),
        revision: row.revision,
      });
      saved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <WorkspaceDialog title="승인 요청 검토" close={close}>
      <div className="wf-dialog">
        <ApprovalRecord row={row} />
        {row.state === "pending" && canDecide && (
          <>
            <label>
              검토·처리 사유
              <textarea
                rows={4}
                maxLength={1000}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="확인한 내용과 신청자에게 전달할 안내를 적어주세요."
              />
            </label>
            {error && (
              <p className="wf-error" role="alert">
                {error}
              </p>
            )}
            <footer>
              <button
                className="wf-secondary"
                disabled={busy || note.trim().length < 5}
                onClick={() => void decide("rejected")}
              >
                보류·반려
              </button>
              {row.kind === "source_check" && (
                <button
                  className="wf-secondary"
                  disabled={busy || note.trim().length < 5}
                  onClick={() => void decide("needs_info")}
                >
                  보완 요청
                </button>
              )}
              <button
                className="wf-primary"
                disabled={busy || note.trim().length < 5}
                onClick={() => void decide("approved")}
              >
                {busy
                  ? "처리 중…"
                  : row.kind === "source_check"
                    ? "승인하고 점검 실행"
                    : "파일 보관 검토 승인"}
              </button>
            </footer>
          </>
        )}
        {!canDecide && (
          <p className="wf-note">
            열람 중입니다. 이 작업의 결정 권한은 데이터 관리자와 전체 관리자에게
            있습니다.
          </p>
        )}
      </div>
    </WorkspaceDialog>
  );
}

export function AdminAutomation() {
  const session = useAdmin(),
    [params, setParams] = useSearchParams(),
    tab = params.get("tab") ?? "watch";
  const query = useControl<AutomationState>(
    "/api/control/admin/automation",
    true,
    30000,
  );
  const [notice, setNotice] = useState("");
  return (
    <>
      <PageTitle
        eyebrow="AUTOMATION CONTROL"
        title="자동화 운영"
        description="규정 변경 점검, 문의 배정 규칙과 알림 기준을 관리하세요."
      >
        <button className="ops-secondary" onClick={query.refresh}>
          <RefreshCw size={14} />
          새로고침
        </button>
      </PageTitle>
      <nav className="wf-tabs" aria-label="자동화 설정">
        <button
          aria-current={tab === "watch" ? "page" : undefined}
          onClick={() => setParams({ tab: "watch" })}
        >
          <FileClock size={16} />
          규정 변경 감지
        </button>
        {session.permissions.includes("cases") && (
          <button
            aria-current={tab === "routing" ? "page" : undefined}
            onClick={() => setParams({ tab: "routing" })}
          >
            <Users size={16} />
            문의 자동 배정
          </button>
        )}
        <button
          aria-current={tab === "policy" ? "page" : undefined}
          onClick={() => setParams({ tab: "policy" })}
        >
          <Bell size={16} />
          알림 기준
        </button>
      </nav>
      <QueryError error={query.error} retry={query.refresh} />
      {notice && (
        <p className="ops-success" role="status">
          {notice}
        </p>
      )}
      {query.loading && !query.data && <Loading />}
      {query.data && (
        <ConfigEditor
          key={`${tab}:${query.data.config.revision}`}
          data={query.data}
          tab={tab}
          canEdit={session.permissions.includes("settings")}
          canCheck={session.permissions.includes("jobs")}
          canSources={session.permissions.includes("sources")}
          saved={() => {
            query.refresh();
            setNotice(
              "자동화 설정을 저장했습니다. 현재 원문·검색 범위는 유지됩니다.",
            );
          }}
        />
      )}
      {tab === "routing" && session.permissions.includes("cases") && (
        <AgentRoster canEdit={session.permissions.includes("settings")} />
      )}
    </>
  );
}
function ConfigEditor({
  data,
  tab,
  canEdit,
  canCheck,
  canSources,
  saved,
}: {
  data: AutomationState;
  tab: string;
  canEdit: boolean;
  canCheck: boolean;
  canSources: boolean;
  saved: () => void;
}) {
  const sources = useControl<SourceCatalog>(
    "/api/control/admin/sources",
    canSources,
  );
  const [config, setConfig] = useState<AutomationConfig>(data.config),
    [q, setQ] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [jobId, setJobId] = useState("");
  const docs =
    sources.data?.items.filter(
      (d) => d.source_url && (d.title + d.id).includes(q),
    ) ?? [];
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await control("/api/control/admin/automation", "PUT", config);
      saved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }
  async function check() {
    setBusy(true);
    setError("");
    try {
      const job = await control<{ id: string }>(
        "/api/control/admin/automation/check",
        "POST",
        {},
      );
      setJobId(job.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "점검하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="wf-form" onSubmit={save}>
      {tab === "watch" && (
        <div className="wf-columns">
          <section className="wf-panel">
            <header>
              <div>
                <FileClock size={19} />
                <h2>공식 파일 변경 점검</h2>
              </div>
              <span
                className={
                  "ops-badge " +
                  (data.config.watch_enabled ? "succeeded" : "held")
                }
              >
                {data.config.watch_enabled
                  ? "자동 점검 켜짐"
                  : "자동 점검 꺼짐"}
              </span>
            </header>
            <p className="wf-muted">
              선택한 한전 공식 첨부파일을 다시 받아 해시를 비교합니다. 파일
              차이는 변경 후보로 분류하고, 원문 내용과 시행 여부는 별도
              검토합니다.
            </p>
            <fieldset disabled={!canEdit || busy}>
              <label className="wf-check">
                <input
                  type="checkbox"
                  checked={config.watch_enabled}
                  onChange={(e) =>
                    setConfig({ ...config, watch_enabled: e.target.checked })
                  }
                />
                선택한 원문 자동 점검
              </label>
              <label>
                점검 주기
                <select
                  value={config.watch_interval_minutes}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      watch_interval_minutes: Number(e.target.value),
                    })
                  }
                >
                  {[15, 60, 360, 1440, 10080].map((n) => (
                    <option key={n} value={n}>
                      {n < 60
                        ? `${n}분`
                        : n < 1440
                          ? `${n / 60}시간`
                          : `${n / 1440}일`}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                점검 원문 찾기
                <input
                  value={q}
                  maxLength={100}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="원문 제목 또는 문서 번호"
                />
              </label>
              <p className="wf-muted">
                선택 {config.watch_documents.length}/5 · 저장 후 적용
              </p>
              <div className="wf-source-options">
                {docs.map((d) => (
                  <label className="wf-check" key={d.id}>
                    <input
                      type="checkbox"
                      checked={config.watch_documents.includes(d.id)}
                      disabled={
                        !config.watch_documents.includes(d.id) &&
                        config.watch_documents.length >= 5
                      }
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          watch_documents: e.target.checked
                            ? [...config.watch_documents, d.id]
                            : config.watch_documents.filter(
                                (id) => id !== d.id,
                              ),
                        })
                      }
                    />
                    <span>
                      {d.title}
                      <small>{d.id}</small>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            {!canEdit && (
              <p className="wf-note">
                설정 변경은 전체 관리자가 할 수 있습니다.
              </p>
            )}
            <QueryError error={sources.error} retry={sources.refresh} />
            <div className="wf-actions">
              {canEdit && (
                <button
                  className="wf-primary"
                  disabled={
                    busy ||
                    (config.watch_enabled && !config.watch_documents.length)
                  }
                >
                  점검 설정 저장
                </button>
              )}
              {canCheck && (
                <button
                  type="button"
                  className="wf-secondary"
                  disabled={busy || !data.config.watch_documents.length}
                  onClick={() => void check()}
                >
                  <Play size={14} />
                  저장된 대상으로 지금 점검
                </button>
              )}
            </div>
            <small className="wf-muted">
              자동 점검은 로컬 운영 서버가 실행 중일 때 동작합니다. 중지 기간의
              작업을 몰아서 실행하지 않습니다.
            </small>
          </section>
          <section className="wf-panel">
            <header>
              <h2>점검 이력</h2>
              <Link to="/hr/admin/jobs">작업 보기 →</Link>
            </header>
            <p className="wf-muted">
              다음 자동 점검 ·{" "}
              {data.config.watch_enabled && data.runtime.next_due
                ? dateTime(new Date(data.runtime.next_due * 1000).toISOString())
                : "예약 없음"}
            </p>
            {(jobId || data.runtime.last_job) && (
              <p className="wf-note">
                최근 작업 · {jobId || data.runtime.last_job}
              </p>
            )}
            {data.runtime.last_error && (
              <p className="wf-error" role="alert">
                {data.runtime.last_error}
              </p>
            )}
            {!data.checks.length && (
              <Empty
                title="아직 점검 이력이 없습니다"
                description="점검 대상을 저장한 뒤 지금 점검을 실행하세요."
              />
            )}
            {data.checks.map((d) => (
              <article className="wf-check-result" key={d.document_id}>
                <div>
                  <strong>{d.title}</strong>
                  <span
                    className={
                      "ops-badge " + (d.changed ? "held" : "succeeded")
                    }
                  >
                    {d.changed ? "보존 원문과 다름" : "파일 동일"}
                  </span>
                </div>
                <small>
                  {dateTime(d.checked_at)} · {d.job_id}
                </small>
                <code>{d.last_sha}</code>
              </article>
            ))}
            <Link className="wf-inline-link" to="/hr/admin/approvals">
              변경 후보는 통합 승인함에서 검토 <span>→</span>
            </Link>
          </section>
        </div>
      )}
      {tab === "routing" && (
        <section className="wf-panel">
          <header>
            <div>
              <Users size={19} />
              <h2>문의 분류별 배정 규칙</h2>
            </div>
          </header>
          <p className="wf-muted">
            새 문의는 해당 팀에서 처리 중인 문의가 가장 적은 활동 담당자에게
            배정됩니다. 담당자가 없거나 한도에 도달하면 팀 대기함과 배정 알림에
            남습니다. 기존 문의는 문의 상세에서 다시 배정할 수 있습니다.
          </p>
          <fieldset disabled={!canEdit || busy}>
            <div className="wf-rule-grid">
              <strong>문의 분류</strong>
              <strong>배정할 팀</strong>
              <strong>처리 목표 시간</strong>
              {config.routing.map((r, i) => (
                <div className="wf-rule" key={r.category}>
                  <span>{r.category}</span>
                  <select
                    aria-label={`${r.category} 배정 팀`}
                    value={r.team}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        routing: config.routing.map((x, j) =>
                          j === i ? { ...x, team: e.target.value } : x,
                        ),
                      })
                    }
                  >
                    {data.teams.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                  <label className="wf-number">
                    <input
                      aria-label={`${r.category} 처리 목표 시간`}
                      type="number"
                      min={1}
                      max={168}
                      value={r.sla_hours}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          routing: config.routing.map((x, j) =>
                            j === i
                              ? { ...x, sla_hours: Number(e.target.value) }
                              : x,
                          ),
                        })
                      }
                    />
                    시간
                  </label>
                </div>
              ))}
            </div>
          </fieldset>
          {canEdit && (
            <button className="wf-primary" disabled={busy}>
              배정 규칙 저장
            </button>
          )}
        </section>
      )}
      {tab === "policy" && (
        <section className="wf-panel wf-policy">
          <header>
            <div>
              <Bell size={19} />
              <h2>비용·품질 알림 기준</h2>
            </div>
          </header>
          <p className="wf-muted">
            실제 요청 기록을 기준으로 조건을 감지합니다. 알림 확인과 조건 해소
            상태를 분리해 관리합니다.
          </p>
          <fieldset disabled={!canEdit || busy}>
            <label>
              월 예산 경고 시점
              <div className="wf-number">
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={config.cost_warning_percent}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      cost_warning_percent: Number(e.target.value),
                    })
                  }
                />
                %
              </div>
              <small>
                현재 예산은 예산·권한·연결에서 설정합니다. 초과 시 추가 알림을
                표시합니다.
              </small>
            </label>
            <label>
              답변 지연 알림
              <div className="wf-number">
                <input
                  type="number"
                  min={5}
                  max={540}
                  value={config.slow_seconds}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      slow_seconds: Number(e.target.value),
                    })
                  }
                />
                초 이상
              </div>
            </label>
          </fieldset>
          <ul className="wf-rule-notes">
            <li>
              완료 요청의 비용 미확인 · 공급자 사용량이나 요금표가 없는 경우
            </li>
            <li>
              답변 연결 실패 · 서버 오류가 발생한 경우 (이번 달 최근 완료 요청
              최대 1,000건)
            </li>
            <li>직원 검토 요청 · 답변에 대한 피드백을 접수한 경우</li>
            <li>
              문의 배정 대기·목표 시간 초과 · 처리 담당자를 확인해야 하는 경우
            </li>
          </ul>
          <p className="wf-note">
            근거 부족 안내를 오답으로 판정하지 않습니다. 품질 알림은 확인할
            신호이며, 답변 의미 정확도나 사람 승인을 자동 보증하지 않습니다.
          </p>
          {canEdit && (
            <button className="wf-primary" disabled={busy}>
              알림 기준 저장
            </button>
          )}
          <Link className="wf-inline-link" to="/hr/admin/alerts">
            현재 운영 알림 확인 →
          </Link>
        </section>
      )}
      {error && (
        <p className="wf-error" role="alert">
          {error}
        </p>
      )}
      {jobId && (
        <p className="ops-success" role="status">
          {jobId} 실제 재수집 작업을 접수했습니다. 완료 결과는 작업 화면과 점검
          이력에서 확인하세요.
        </p>
      )}
    </form>
  );
}

function AgentRoster({ canEdit }: { canEdit: boolean }) {
  const query = useControl<{ items: Agent[]; teams: string[] }>(
    "/api/control/admin/agents",
    true,
    30000,
  );
  const [selected, setSelected] = useState<Agent | "new" | null>(null);
  return (
    <section className="wf-panel wf-roster">
      <header>
        <div>
          <Users size={19} />
          <h2>배정 담당자</h2>
        </div>
        {canEdit && (
          <button className="wf-secondary" onClick={() => setSelected("new")}>
            담당자 등록
          </button>
        )}
      </header>
      <p className="wf-note">
        로컬 배정용 표시 이름입니다. 실제 직원 계정·SSO·접근 권한과 연결되지
        않습니다.
      </p>
      <QueryError error={query.error} retry={query.refresh} />
      {!query.loading && !query.data?.items.length && (
        <Empty
          title="배정 담당자를 등록해 주세요"
          description="등록 전의 문의는 해당 팀 대기함에 보관됩니다."
        />
      )}
      {query.data?.items.map((a) => (
        <div className="wf-agent" key={a.id}>
          <span className="wf-avatar">{a.name.slice(0, 1)}</span>
          <span>
            <strong>{a.name}</strong>
            <small>
              {a.team} · {a.active ? "배정 가능" : "배정 중지"}
            </small>
          </span>
          <span>
            처리 중 <b>{a.open_cases}</b> / {a.capacity}건
          </span>
          {canEdit && (
            <button className="wf-quiet" onClick={() => setSelected(a)}>
              수정
            </button>
          )}
        </div>
      ))}
      {selected && (
        <AgentEditor
          key={selected === "new" ? "new" : selected.id}
          agent={selected === "new" ? null : selected}
          teams={query.data?.teams ?? []}
          close={() => setSelected(null)}
          saved={() => {
            setSelected(null);
            query.refresh();
          }}
        />
      )}
    </section>
  );
}
function AgentEditor({
  agent,
  teams,
  close,
  saved,
}: {
  agent: Agent | null;
  teams: string[];
  close: () => void;
  saved: () => void;
}) {
  const [name, setName] = useState(agent?.name ?? ""),
    [team, setTeam] = useState(agent?.team ?? teams[0] ?? "인사 운영"),
    [capacity, setCapacity] = useState(agent?.capacity ?? 20),
    [active, setActive] = useState(agent ? !!agent.active : true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <WorkspaceDialog
      title={agent ? "배정 담당자 수정" : "배정 담당자 등록"}
      close={close}
    >
      <form
        className="wf-dialog wf-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await control(
              "/api/control/admin/agents" + (agent ? `/${agent.id}` : ""),
              agent ? "PATCH" : "POST",
              {
                name: name.trim(),
                team,
                capacity,
                active,
                ...(agent ? { revision: agent.revision } : {}),
              },
            );
            saved();
          } catch (e) {
            setError(e instanceof Error ? e.message : "저장하지 못했습니다.");
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          표시 이름
          <input
            required
            minLength={2}
            maxLength={40}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="운영용 별칭"
          />
        </label>
        <label>
          담당 팀
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            {teams.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          동시 처리 한도
          <input
            required
            type="number"
            min={1}
            max={100}
            value={capacity}
            onChange={(e) => setCapacity(Number(e.target.value))}
          />
        </label>
        <label className="wf-check">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
          />
          신규 문의 배정 가능
        </label>
        <p className="wf-note">
          담당자 설정을 바꿔도 기존 문의 담당자는 자동 교체되지 않습니다. 배정
          중지 후 남은 문의는 문의 상세에서 다시 배정해 주세요.
        </p>
        {error && (
          <p className="wf-error" role="alert">
            {error}
          </p>
        )}
        <button className="wf-primary" disabled={busy}>
          {busy ? "저장 중…" : "담당자 저장"}
        </button>
      </form>
    </WorkspaceDialog>
  );
}

export function AdminAlerts() {
  const query = useControl<Alerts>("/api/control/admin/alerts", true, 30000),
    session = useAdmin();
  const [filter, setFilter] = useState("active"),
    [category, setCategory] = useState("all"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [feedback, setFeedback] = useState<Feedback | null>(null);
  const items = query.data?.items ?? [],
    visible = items.filter(
      (r) =>
        (filter === "all" ||
          (filter === "active"
            ? r.state !== "resolved"
            : r.state === filter)) &&
        (category === "all" || r.category === category),
    );
  async function acknowledge(id: string, revision: number, state: string) {
    setBusy(true);
    setError("");
    try {
      await control(`/api/control/admin/alerts/${id}`, "PATCH", {
        revision,
        state,
      });
      query.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="COST & QUALITY SIGNALS"
        title="운영 알림"
        description="비용, 답변 검토와 문의 처리에서 확인할 신호를 모았습니다."
      >
        <button className="ops-secondary" onClick={query.refresh}>
          <RefreshCw size={14} />
          새로고침
        </button>
      </PageTitle>
      <div className="ops-stats">
        <Stat
          label="확인 필요"
          value={items.filter((a) => a.state === "open").length}
          note="현재 역할에서 확인할 알림"
        />
        <Stat
          label="확인 중"
          value={items.filter((a) => a.state === "acknowledged").length}
          note="아직 조건이 해소되지 않은 알림"
        />
        <Stat
          label="직원 검토 요청"
          value={
            query.data?.feedback.filter((f) => f.state === "open").length ?? 0
          }
          note="의미 정확도 확정과 구분"
        />
      </div>
      <QueryError error={query.error} retry={query.refresh} />
      {error && (
        <p className="wf-error" role="alert">
          {error}
        </p>
      )}
      <section className="wf-panel">
        <header>
          <div>
            <Bell size={19} />
            <h2>알림 센터</h2>
          </div>
          <div className="wf-actions">
            <select
              aria-label="알림 종류"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="all">모든 종류</option>
              {query.data?.allowed_categories.map((c) => (
                <option value={c} key={c}>
                  {ALERT_CATEGORIES[c]}
                </option>
              ))}
            </select>
            <select
              aria-label="알림 상태"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="active">해결 전</option>
              <option value="all">모든 상태</option>
              {Object.entries(ALERT_STATES).map(([v, l]) => (
                <option value={v} key={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
        </header>
        {query.loading && !query.data ? (
          <Loading />
        ) : !visible.length ? (
          <Empty
            title="해당하는 알림이 없습니다"
            description="실제 요청·비용·작업 기록에서 조건이 감지되면 표시됩니다."
          />
        ) : (
          visible.map((a) => (
            <article className={"wf-alert " + a.severity} key={a.id}>
              <span className="wf-row-icon">
                <Bell size={18} />
              </span>
              <div>
                <span className="wf-muted">
                  {ALERT_CATEGORIES[a.category]} ·{" "}
                  {a.severity === "critical" ? "긴급 확인" : "주의"}
                </span>
                <h3>{a.title}</h3>
                <p>{a.detail}</p>
                <small>
                  {dateTime(a.updated_at)} · {ALERT_STATES[a.state]}
                </small>
                <footer>
                  <Link to={a.target}>관련 화면 →</Link>
                  {a.state !== "resolved" && (
                    <button
                      disabled={busy}
                      className="wf-quiet"
                      onClick={() =>
                        void acknowledge(
                          a.id,
                          a.revision,
                          a.state === "open" ? "acknowledged" : "open",
                        )
                      }
                    >
                      {a.state === "open"
                        ? "확인 중으로 표시"
                        : "미확인으로 되돌리기"}
                    </button>
                  )}
                </footer>
              </div>
            </article>
          ))
        )}
        <p className="wf-note">
          조건 해소는 실제 기록으로 판단합니다. 비용은 이 로컬 경로에서 수집한
          사용량의 예상 금액이며 공급사 전체 청구서가 아닙니다. 답변 의미
          정확도는 측정하지 않았습니다.
        </p>
      </section>
      {query.data?.allowed_categories.includes("quality") && (
        <section className="wf-panel wf-roster">
          <header>
            <h2>답변 검토 요청</h2>
          </header>
          {!query.data.feedback.length && (
            <Empty
              title="접수된 검토 요청이 없습니다"
              description="직원이 실제 받은 답변에서 검토를 요청하면 연결된 요청 번호가 표시됩니다."
            />
          )}
          {query.data.feedback.map((f) => (
            <button
              className="wf-list-row"
              key={f.id}
              onClick={() => setFeedback(f)}
            >
              <span>
                <strong>{f.reason}</strong>
                <small>
                  {f.request_id} · HTTP {f.status} · {f.latency_ms}ms
                </small>
              </span>
              <span className={"ops-badge " + f.state}>
                {f.state === "open"
                  ? "검토 대기"
                  : f.state === "resolved"
                    ? "처리 완료"
                    : "추가 조치 없음"}
              </span>
              <span>검토 →</span>
            </button>
          ))}
        </section>
      )}
      {feedback && (
        <FeedbackReview
          row={feedback}
          canEdit={["owner", "hr_admin"].includes(session.role)}
          close={() => setFeedback(null)}
          saved={() => {
            setFeedback(null);
            query.refresh();
          }}
        />
      )}
    </>
  );
}
function FeedbackReview({
  row,
  close,
  saved,
  canEdit,
}: {
  row: Feedback;
  close: () => void;
  saved: () => void;
  canEdit: boolean;
}) {
  const [resolution, setResolution] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function save(state: string) {
    setBusy(true);
    setError("");
    try {
      await control(`/api/control/admin/feedback/${row.id}`, "PATCH", {
        state,
        resolution: resolution.trim(),
        revision: row.revision,
      });
      saved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <WorkspaceDialog title="답변 검토 기록" close={close}>
      <div className="wf-dialog wf-form">
        <h3>{row.reason}</h3>
        <p className="wf-muted">
          {row.request_id} · {dateTime(row.created_at)}
        </p>
        <blockquote>{row.note || "추가 설명 없음"}</blockquote>
        <p className="wf-note">
          질문·답변 본문은 운영 저장소에 보관하지 않습니다. 요청 번호와 직원이
          남긴 조문·설명을 바탕으로 규정·양식에서 원문을 확인하세요. 처리 완료는
          답변 의미 정확도 인증을 뜻하지 않습니다.
        </p>
        <Link to="/hr/library?tab=rules">실제 원문 검색 열기 →</Link>
        {row.resolution && <p>{row.resolution}</p>}
        {canEdit && row.state === "open" && (
          <>
            <label>
              직원에게 전달할 검토 결과
              <textarea
                rows={5}
                maxLength={1000}
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
              />
            </label>
            {error && (
              <p className="wf-error" role="alert">
                {error}
              </p>
            )}
            <footer>
              <button
                className="wf-secondary"
                disabled={busy || resolution.trim().length < 5}
                onClick={() => void save("dismissed")}
              >
                추가 조치 없음
              </button>
              <button
                className="wf-primary"
                disabled={busy || resolution.trim().length < 5}
                onClick={() => void save("resolved")}
              >
                검토 결과 기록
              </button>
            </footer>
          </>
        )}
      </div>
    </WorkspaceDialog>
  );
}
