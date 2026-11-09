import { useState, type FormEvent } from "react";
import {
  Activity,
  ArrowDownToLine,
  Check,
  CircleHelp,
  Coins,
  Database,
  ExternalLink,
  RefreshCw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Wallet,
} from "lucide-react";
import { WorkspaceDialog } from "../HrWorkspaceShell";
import {
  ROLE_NAMES,
  control,
  count,
  dateTime,
  money,
  useControl,
  type Policy,
  type Rate,
  type Settings,
  type Usage,
  type UsageRequest,
} from "../operations";
import { useAdmin } from "./context";
import { Badge, Empty, Loading, PageTitle, QueryError, Stat } from "./ui";

export function AdminUsage() {
  const [days, setDays] = useState(7),
    [metric, setMetric] = useState<"tokens" | "cost">("tokens"),
    [day, setDay] = useState(""),
    [detail, setDetail] = useState<UsageRequest | null>(null),
    query = useControl<Usage>("/api/control/admin/usage?days=" + days);
  const data = query.data,
    total = data?.totals,
    monthly = data?.monthly,
    rows = data?.requests.filter((row) => !day || row.day === day) ?? [];
  const values =
      data?.daily.map((item) =>
        metric === "tokens"
          ? item.input_tokens + item.output_tokens
          : Number(item.known_cost_usd),
      ) ?? [],
    max = Math.max(1e-9, ...values);
  return (
    <>
      <PageTitle
        eyebrow="AI OBSERVABILITY"
        title="토큰·비용"
        description="모델 응답에 기록된 실제 토큰과 호출 단계를 바탕으로 사용량을 확인하세요."
      >
        <select
          aria-label="사용량 조회 기간"
          value={days}
          onChange={(e) => {
            setDays(Number(e.target.value));
            setDay("");
          }}
        >
          {[1, 7, 30, 90].map((value) => (
            <option key={value} value={value}>
              최근 {value}일
            </option>
          ))}
        </select>
        <button className="ops-secondary" onClick={query.refresh}>
          <RefreshCw size={14} />
          새로고침
        </button>
        <a
          className="ops-primary"
          href="/api/control/admin/usage/export"
          download
        >
          <ArrowDownToLine size={14} />
          CSV 내보내기
        </a>
      </PageTitle>
      <QueryError error={query.error} retry={query.refresh} />
      {query.loading && !data ? (
        <Loading />
      ) : (
        <>
          <div className="ops-stats">
            <Stat
              label="AI 질문 요청"
              value={count(total?.requests)}
              note={`공급자 모델 호출 ${count(total?.provider_calls)}회`}
            >
              <Activity size={17} />
            </Stat>
            <Stat
              label="입력 토큰"
              value={count(total?.input_tokens)}
              note={`이 중 캐시 입력 ${count(total?.cached_tokens)}토큰`}
            >
              <Database size={17} />
            </Stat>
            <Stat
              label="출력 토큰"
              value={count(total?.output_tokens)}
              note={`사용량 미확인 ${count(total?.unknown_usage)}건`}
            >
              <Coins size={17} />
            </Stat>
            <Stat
              label="기간 추정 비용"
              value={money(total?.known_cost_usd)}
              note={`미산정 ${count(total?.unpriced_requests)}건 · USD 기준`}
              tone="blue"
            >
              <Wallet size={17} />
            </Stat>
          </div>
          <div className="ops-usage-grid">
            <section className="ops-panel ops-usage-chart">
              <header>
                <div>
                  <h2>사용량 추이</h2>
                  <p>
                    {data?.started_at
                      ? dateTime(data.started_at) +
                        " 집계 시작 · 서울 시간 기준"
                      : "집계 시작 후 실제 요청이 여기에 표시됩니다."}
                  </p>
                </div>
                <div className="ops-segment">
                  <button
                    aria-pressed={metric === "tokens"}
                    onClick={() => setMetric("tokens")}
                  >
                    전체 토큰
                  </button>
                  <button
                    aria-pressed={metric === "cost"}
                    onClick={() => setMetric("cost")}
                  >
                    추정 비용
                  </button>
                </div>
              </header>
              <div className="ops-chart-legend">
                <span>
                  <i className="ops-dot blue" />
                  {metric === "tokens"
                    ? "입력 + 출력 토큰"
                    : "단가 기준 USD 추정"}
                </span>
                <small>막대를 눌러 해당 일자의 요청 확인</small>
              </div>
              <div className="ops-chart-bars">
                {data?.daily.map((item, index) => (
                  <button
                    key={item.day}
                    className={day === item.day ? "selected" : ""}
                    aria-pressed={day === item.day}
                    aria-label={
                      item.day +
                      " " +
                      (metric === "tokens"
                        ? count(values[index]) + "토큰"
                        : money(item.known_cost_usd))
                    }
                    onClick={() =>
                      setDay((previous) =>
                        previous === item.day ? "" : item.day,
                      )
                    }
                    title={
                      item.day +
                      " · " +
                      (metric === "tokens"
                        ? count(values[index]) + "토큰"
                        : money(item.known_cost_usd))
                    }
                  >
                    <span>
                      <i
                        style={{ height: (values[index] / max) * 100 + "%" }}
                      />
                    </span>
                    <small>
                      {index % Math.ceil(days / 7) === 0
                        ? item.day.slice(5).replace("-", "/")
                        : ""}
                    </small>
                  </button>
                ))}
              </div>
              {total?.requests === 0 && (
                <p className="ops-chart-empty">
                  아직 이 기간에 집계된 요청이 없습니다. 예시 수치를 표시하지
                  않습니다.
                </p>
              )}
              <footer>
                <span>요청 {count(total?.requests)}건</span>
                <span>
                  중앙 응답 시간{" "}
                  {data?.median_latency_ms == null
                    ? "—"
                    : (data.median_latency_ms / 1000).toFixed(1) + "초"}
                </span>
              </footer>
            </section>
            <section className="ops-panel ops-budget-card">
              <header>
                <div>
                  <h2>이번 달 예산</h2>
                  <p>이 게이트웨이의 완료 요청 기준</p>
                </div>
                <Wallet size={18} />
              </header>
              <strong>
                {money(monthly?.known_cost_usd)}
                <small> / {money(data?.policy.monthly_budget_usd)}</small>
              </strong>
              <div className="ops-progress">
                <i
                  style={{
                    width:
                      Math.min(
                        100,
                        (Number(monthly?.known_cost_usd ?? 0) /
                          Math.max(
                            0.01,
                            Number(data?.policy.monthly_budget_usd ?? 1),
                          )) *
                          100,
                      ) + "%",
                  }}
                />
              </div>
              <dl>
                <dt>한도 동작</dt>
                <dd>
                  {data?.policy.budget_action === "block"
                    ? "누적 한도 도달 후 새 요청 차단"
                    : "사용량 관찰"}
                </dd>
                <dt>일일 요청 한도</dt>
                <dd>{count(data?.policy.daily_request_limit)}건</dd>
                <dt>이번 달 미산정</dt>
                <dd>{count(monthly?.unpriced_requests)}건</dd>
                <dt>비용 산정</dt>
                <dd>토큰 × 버전별 단가 추정</dd>
              </dl>
              <a href="/hr/admin/settings" className="ops-panel-bottom">
                예산·단가 설정
                <SlidersHorizontal size={14} />
              </a>
            </section>
          </div>
          <div className="ops-inline-note">
            <CircleHelp size={16} />
            <span>
              캐시 읽기·쓰기는 입력 토큰에 포함됩니다. 비용은 Standard 단가 기준
              추정이며 실제 청구서와 다를 수 있습니다. 집계 시작 전·8846 직접
              호출·공급자 계정 전체 사용량은 포함하지 않습니다.
            </span>
          </div>
          <section className="ops-panel">
            <header>
              <div>
                <h2>요청별 호출 기록 {day && <small>{day}</small>}</h2>
                <p>
                  질문·답변 본문은 저장하지 않고 호출·사용량 정보만 보관합니다.
                </p>
              </div>
              {day && (
                <button className="ops-text-button" onClick={() => setDay("")}>
                  일자 필터 해제
                </button>
              )}
            </header>
            {rows.length ? (
              <div className="ops-table-scroll">
                <table className="ops-table ops-usage-table">
                  <thead>
                    <tr>
                      <th>요청·시각</th>
                      <th>상태</th>
                      <th>모델 호출</th>
                      <th>입력 / 출력</th>
                      <th>추정 비용</th>
                      <th>응답 시간</th>
                      <th>상세</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <strong className="ops-mono">{row.id}</strong>
                          <small className="ops-cell-sub">
                            {dateTime(row.started_at)}
                          </small>
                        </td>
                        <td>
                          <Badge
                            state={
                              !row.completed_at
                                ? "running"
                                : row.status && row.status >= 400
                                  ? "failed"
                                  : row.answer_state === "needs_review"
                                    ? "held"
                                    : "succeeded"
                            }
                          >
                            {!row.completed_at
                              ? "처리 중"
                              : row.status && row.status >= 400
                                ? "오류"
                                : row.answer_state === "needs_review"
                                  ? "보류"
                                  : "답변"}
                          </Badge>
                        </td>
                        <td>
                          {row.call_count == null
                            ? "미확인"
                            : row.call_count + "회"}
                        </td>
                        <td>
                          {count(row.input_tokens)}{" "}
                          <span className="ops-muted">/</span>{" "}
                          {count(row.output_tokens)}
                        </td>
                        <td>{money(row.cost_usd)}</td>
                        <td>
                          {row.latency_ms == null
                            ? "—"
                            : (row.latency_ms / 1000).toFixed(1) + "초"}
                        </td>
                        <td>
                          <button
                            className="ops-text-button"
                            onClick={() => setDetail(row)}
                          >
                            호출 상세
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty
                title="집계된 요청이 없습니다."
                description="직원 화면의 실제 AI 질문이 처리되면 토큰과 호출 정보가 기록됩니다."
                to="/hr/assistant"
                action="AI 업무 도우미 열기"
              />
            )}
          </section>
        </>
      )}
      {detail && <UsageDetail row={detail} close={() => setDetail(null)} />}
    </>
  );
}

function UsageDetail({ row, close }: { row: UsageRequest; close: () => void }) {
  const query = useControl<{
    generations: {
      phase: string;
      model: string;
      input_tokens: number | null;
      output_tokens: number | null;
      cached_tokens: number | null;
      write_tokens: number | null;
      cost_usd: string | null;
      rate_snapshot: string | null;
    }[];
  }>("/api/control/admin/usage/requests/" + row.id);
  const phases: Record<string, string> = {
    question_understanding: "질문 의미 확인",
    draft: "답변 초안",
    source_comparison: "원문 대조",
  };
  return (
    <WorkspaceDialog title="AI 호출 상세" close={close}>
      <div className="ops-usage-detail">
        <p className="ops-mono">{row.id}</p>
        <div className="ops-inline-note">
          <ShieldCheck size={15} />
          질문·답변 본문, 키와 직원 프로필은 이 사용량 저장소에 기록하지
          않습니다.
        </div>
        <QueryError error={query.error} />
        {query.loading ? (
          <Loading />
        ) : query.data?.generations.length ? (
          <div className="ops-generation-list">
            {query.data.generations.map((call, index) => (
              <section key={index}>
                <header>
                  <span>{index + 1}</span>
                  <strong>{phases[call.phase] ?? call.phase}</strong>
                  <Badge state="neutral">{call.model}</Badge>
                </header>
                <dl>
                  <dt>입력 토큰</dt>
                  <dd>{count(call.input_tokens)}</dd>
                  <dt>캐시 입력(읽기)</dt>
                  <dd>{count(call.cached_tokens)}</dd>
                  <dt>캐시 쓰기</dt>
                  <dd>{count(call.write_tokens)}</dd>
                  <dt>출력 토큰</dt>
                  <dd>{count(call.output_tokens)}</dd>
                  <dt>추정 비용</dt>
                  <dd>{money(call.cost_usd)}</dd>
                </dl>
                <small>
                  {call.rate_snapshot
                    ? "호출 시점의 단가 버전으로 계산 · 실제 청구액 아님"
                    : "사용량 또는 계산 단가 미확인"}
                </small>
              </section>
            ))}
          </div>
        ) : (
          <Empty
            title={
              row.call_count === 0
                ? "모델 호출 없이 처리된 요청입니다."
                : "호출 사용량을 확인하지 못했습니다."
            }
            description={
              row.call_count === 0
                ? "보류 문서 지정 등 모델을 호출하지 않는 경로입니다."
                : "오류·연결 중단 등의 미확인 비용을 무료로 집계하지 않습니다."
            }
          />
        )}
      </div>
    </WorkspaceDialog>
  );
}

export function AdminSettings() {
  const session = useAdmin(),
    query = useControl<Settings>("/api/control/admin/settings"),
    [notice, setNotice] = useState("");
  const edit = session.permissions.includes("settings");
  return (
    <>
      <PageTitle
        eyebrow="WORKSPACE SETTINGS"
        title="예산·권한·연결"
        description="AI 이용 정책과 계산 단가를 관리하고, 실제 연결과 역할 범위를 확인하세요."
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
      {query.loading && !query.data ? (
        <Loading />
      ) : (
        query.data && (
          <>
            <div className="ops-settings-grid">
              <section className="ops-panel">
                <header>
                  <div>
                    <h2>예산·서비스 정책</h2>
                    <p>새 AI 질문에 적용되는 로컬 게이트웨이 정책</p>
                  </div>
                  <Wallet size={18} />
                </header>
                <PolicyForm
                  key={query.data.policy.revision}
                  policy={query.data.policy}
                  editable={edit}
                  saved={() => {
                    query.refresh();
                    setNotice(
                      "정책을 저장했습니다. 이 게이트웨이의 다음 AI 요청부터 적용합니다.",
                    );
                  }}
                />
              </section>
              <section className="ops-panel">
                <header>
                  <div>
                    <h2>모델별 계산 단가</h2>
                    <p>USD / 100만 토큰 · 과거 비용은 변경하지 않습니다.</p>
                  </div>
                  <Coins size={18} />
                </header>
                {query.data.rates.map((rate) => (
                  <RateForm
                    key={rate.model + ":" + rate.revision}
                    rate={rate}
                    editable={edit}
                    saved={() => {
                      query.refresh();
                      setNotice(
                        "단가를 저장했습니다. 이후 호출부터 새 버전으로 추정합니다.",
                      );
                    }}
                  />
                ))}
              </section>
            </div>
            <section className="ops-panel ops-settings-section">
              <header>
                <div>
                  <h2>연결 상태</h2>
                  <p>연결되지 않은 기능을 운영 완료로 표시하지 않습니다.</p>
                </div>
                <Activity size={18} />
              </header>
              <div className="ops-integration-grid">
                {query.data.integrations.map((item) => (
                  <div className="ops-integration" key={item.id}>
                    <span>
                      <Database size={18} />
                    </span>
                    <div>
                      <strong>{item.name}</strong>
                      <p>{item.detail}</p>
                    </div>
                    <Badge
                      state={item.state === "local" ? "succeeded" : "held"}
                    >
                      {item.state === "local"
                        ? "로컬 연결"
                        : item.state === "held"
                          ? "보류"
                          : "연결 전"}
                    </Badge>
                  </div>
                ))}
              </div>
            </section>
            <section className="ops-panel ops-settings-section">
              <header>
                <div>
                  <h2>역할별 권한</h2>
                  <p>
                    서버가 작업별 권한을 검사합니다. 회사 SSO·테넌트별 운영 권한
                    연결은 별도입니다.
                  </p>
                </div>
                <ShieldCheck size={18} />
              </header>
              <div className="ops-table-scroll">
                <table className="ops-table ops-permission-table">
                  <thead>
                    <tr>
                      <th>기능</th>
                      {["owner", "data_admin", "hr_admin", "analyst"].map(
                        (role) => (
                          <th key={role}>{ROLE_NAMES[role]}</th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { key: "sources", label: "원문 목록·출처 조회" },
                      { key: "jobs", label: "재수집·정합성·재적재" },
                      { key: "reviews", label: "원문 검토 기록" },
                      { key: "usage", label: "사용량·비용·CSV" },
                      { key: "cases", label: "직원 문의 처리" },
                      { key: "settings", label: "예산·단가·점검 정책 변경" },
                      { key: "audit", label: "변경 이력 조회" },
                    ].map((item) => (
                      <tr key={item.key}>
                        <td>{item.label}</td>
                        {["owner", "data_admin", "hr_admin", "analyst"].map(
                          (role) => (
                            <td key={role}>
                              {query.data?.permissions[role].includes(
                                item.key,
                              ) ? (
                                <Check size={16} aria-label="허용" />
                              ) : (
                                <span className="ops-muted">—</span>
                              )}
                            </td>
                          ),
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="ops-page-footnote">
                체험 역할은 상단 메뉴에서 바꿀 수 있습니다. 실제 조직에 관리자
                권한을 부여하는 기능은 연결 전입니다.
              </p>
            </section>
          </>
        )
      )}
    </>
  );
}

function PolicyForm({
  policy,
  editable,
  saved,
}: {
  policy: Policy;
  editable: boolean;
  saved: () => void;
}) {
  const [budget, setBudget] = useState(policy.monthly_budget_usd),
    [limit, setLimit] = useState(String(policy.daily_request_limit)),
    [action, setAction] = useState(policy.budget_action),
    [maintenance, setMaintenance] = useState(policy.maintenance),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await control("/api/control/admin/settings", "PUT", {
        monthly_budget_usd: budget,
        daily_request_limit: Number(limit),
        budget_action: action,
        maintenance,
        revision: policy.revision,
      });
      saved();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "저장하지 못했습니다.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="ops-form" onSubmit={submit}>
      <div className="ops-form-columns">
        <label>
          월 예산 (USD)
          <input
            type="number"
            required
            min="0.01"
            max="100000"
            step="0.01"
            disabled={!editable}
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
          />
        </label>
        <label>
          일일 AI 질문 한도
          <input
            type="number"
            required
            min={1}
            max={10000}
            disabled={!editable}
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
          />
        </label>
      </div>
      <label>
        예산에 도달했을 때
        <select
          value={action}
          disabled={!editable}
          onChange={(e) => setAction(e.target.value as "observe" | "block")}
        >
          <option value="observe">사용량 관찰 · 새 요청 유지</option>
          <option value="block">누적 한도 도달 후 새 요청 차단</option>
        </select>
      </label>
      <label className="ops-toggle-row">
        <span>
          <strong>AI 점검 모드</strong>
          <small>새 AI 답변 요청을 중지합니다. 원문 검색은 유지합니다.</small>
        </span>
        <input
          type="checkbox"
          aria-label="AI 점검 모드"
          disabled={!editable}
          checked={maintenance}
          onChange={(e) => setMaintenance(e.target.checked)}
        />
      </label>
      <div className="ops-form-note">
        <CircleHelp size={14} />
        <span>
          완료된 요청의 누적 추정액 기준입니다. 한 요청으로 한도를 넘을 수
          있으며, 차단 정책에서 미산정 비용이 있으면 새 요청도 보류합니다.
          공급자 계정의 청구 한도와는 별도입니다.
        </span>
      </div>
      {error && (
        <p className="ops-error" role="alert">
          {error}
        </p>
      )}
      <footer>
        <span>설정 버전 {policy.revision}</span>
        <button className="ops-primary" disabled={!editable || busy}>
          <Save size={14} />
          {busy ? "저장 중…" : "정책 저장"}
        </button>
      </footer>
    </form>
  );
}

function RateForm({
  rate,
  editable,
  saved,
}: {
  rate: Rate;
  editable: boolean;
  saved: () => void;
}) {
  const [input, setInput] = useState(rate.input),
    [cached, setCached] = useState(rate.cached),
    [write, setWrite] = useState(rate.write),
    [output, setOutput] = useState(rate.output),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await control("/api/control/admin/rates", "PUT", {
        model: rate.model,
        input,
        cached,
        write,
        output,
      });
      saved();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "단가를 저장하지 못했습니다.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="ops-form ops-rate-form" onSubmit={submit}>
      <div className="ops-rate-model">
        <strong>{rate.model}</strong>
        <Badge state="neutral">추정용 단가 v{rate.revision}</Badge>
      </div>
      <div className="ops-form-columns">
        {[
          { label: "일반 입력", value: input, set: setInput },
          { label: "캐시 입력", value: cached, set: setCached },
          { label: "캐시 쓰기", value: write, set: setWrite },
          { label: "출력", value: output, set: setOutput },
        ].map((item) => (
          <label key={item.label}>
            {item.label}
            <input
              type="number"
              required
              min={0}
              max={100000}
              step="0.000001"
              disabled={!editable}
              value={item.value}
              onChange={(e) => item.set(e.target.value)}
            />
          </label>
        ))}
      </div>
      <p className="ops-rate-reference">
        {rate.reference.startsWith("https://") ? (
          <a href={rate.reference} target="_blank" rel="noreferrer">
            공식 단가 참고
            <ExternalLink size={12} />
          </a>
        ) : (
          <span>관리자 입력 단가</span>
        )}
        <span>{rate.checked_at.slice(0, 10)} 확인</span>
      </p>
      <div className="ops-form-note">
        <CircleHelp size={14} />
        <span>
          기본 단가는 Standard 처리 기준입니다. 실제 처리 등급·지역·할인과 다를
          수 있어 청구액으로 확정하지 않습니다. reasoning 토큰은 출력에 포함하며
          중복 계산하지 않습니다.
        </span>
      </div>
      {error && (
        <p className="ops-error" role="alert">
          {error}
        </p>
      )}
      <footer>
        <span>과거 호출은 당시 단가 유지</span>
        <button className="ops-primary" disabled={!editable || busy}>
          <Save size={14} />
          {busy ? "저장 중…" : "단가 저장"}
        </button>
      </footer>
    </form>
  );
}
