import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  BookCheck,
  Boxes,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Database,
  Download,
  ExternalLink,
  FileSearch,
  Filter,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Square,
  Timer,
  Wallet,
  X,
} from "lucide-react";
import { WorkspaceDialog } from "../HrWorkspaceShell";
import {
  JOB_KINDS,
  JOB_STATES,
  control,
  count,
  dateTime,
  money,
  useControl,
  type JobRecord,
  type Overview,
  type ReviewRecord,
  type SourceCatalog,
  type SourceDocument,
} from "../operations";
import { useAdmin } from "./context";
import { Badge, Empty, Loading, PageTitle, QueryError, Stat } from "./ui";

export function AdminOverview() {
  const session = useAdmin(),
    query = useControl<Overview>("/api/control/admin/overview");
  const counts = useControl<{ alerts: number; pending_approvals: number }>(
    "/api/control/workflow-counts?admin=true",
    true,
    30000,
  );
  const [diagnostic, setDiagnostic] = useState<{
      database: boolean;
      corpus: boolean;
      upstream: boolean;
      at: string;
    } | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const data = query.data,
    usage = data?.usage,
    open =
      data?.cases
        .filter((row) => !["resolved", "cancelled"].includes(row.state))
        .reduce((sum, row) => sum + row.count, 0) ?? 0;
  async function diagnose() {
    setBusy(true);
    setError("");
    try {
      setDiagnostic(
        await control("/api/control/admin/diagnostics", "POST", {}),
      );
      query.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "진단하지 못했습니다.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="OVERVIEW"
        title="운영 현황"
        description="직원 서비스와 AI 데이터 운영의 현재 상태를 확인하세요."
      >
        <button className="ops-secondary" onClick={query.refresh}>
          <RefreshCw size={14} />
          새로고침
        </button>
        <button
          className="ops-primary"
          disabled={busy}
          onClick={() => void diagnose()}
        >
          <Activity size={15} />
          {busy ? "진단 중…" : "서비스 진단"}
        </button>
      </PageTitle>
      <QueryError error={query.error} retry={query.refresh} />
      <div className="ops-work-priorities" aria-label="운영 처리할 업무">
        {session.permissions.includes("approvals") && (
          <Link to="/hr/admin/approvals">
            <BookCheck size={19} />
            <span>
              <strong>통합 승인함</strong>
              <small>검토·결정이 필요한 요청</small>
            </span>
            <b>{counts.error ? "—" : count(counts.data?.pending_approvals)}</b>
            <ArrowRight size={16} />
          </Link>
        )}
        <Link to="/hr/admin/alerts">
          <Activity size={19} />
          <span>
            <strong>운영 알림</strong>
            <small>비용·품질·자료 운영 확인</small>
          </span>
          <b>{counts.error ? "—" : count(counts.data?.alerts)}</b>
          <ArrowRight size={16} />
        </Link>
        {session.permissions.includes("cases") && (
          <Link to="/hr/admin/cases">
            <Timer size={19} />
            <span>
              <strong>진행 중 문의</strong>
              <small>담당자·처리 기한 확인</small>
            </span>
            <b>{data ? count(open) : "—"}</b>
            <ArrowRight size={16} />
          </Link>
        )}
        {!session.permissions.includes("cases") &&
          session.permissions.includes("jobs") && (
            <Link to="/hr/admin/jobs">
              <Boxes size={19} />
              <span>
              <strong>최근 진행 작업</strong>
              <small>최근 5건 중 대기·실행 작업</small>
              </span>
              <b>
                {data
                  ? count(
                      data.jobs.filter((j) =>
                        ["queued", "running"].includes(j.state),
                      ).length,
                    )
                  : "—"}
              </b>
              <ArrowRight size={16} />
            </Link>
          )}
      </div>
      {error && (
        <p className="ops-error" role="alert">
          {error}
        </p>
      )}
      {query.loading && !data ? (
        <Loading />
      ) : (
        <>
          <div className="ops-context-line">
            <span className="ops-live">
              <i />
              한전 참고자료
            </span>
            <span>원문 기반 검색 연결</span>
            <span className="ops-context-right">
              조직 승인 {count(data?.approved_count)}건 · KTcs 적용 미확인
            </span>
          </div>
          <div className="ops-stats">
            <Stat
              label="답변 참고 조문"
              value={count(data?.source_count)}
              note="실제 답변 검색에 허용된 범위"
            >
              <Database size={17} />
            </Stat>
            <Stat
              label="추가 검토 구간"
              value={count(data?.review_count)}
              note="검토 전용 · 답변 생성에 미사용"
              tone="amber"
            >
              <BookCheck size={17} />
            </Stat>
            <Stat
              label="최근 7일 사용 토큰"
              value={
                usage
                  ? count(
                      usage.totals.input_tokens + usage.totals.output_tokens,
                    )
                  : "권한 없음"
              }
              note={
                usage
                  ? `모델 호출 ${count(usage.totals.provider_calls)}회 · 집계 시작 이후`
                  : "역할별 사용량 조회 권한 적용"
              }
            >
              <Activity size={17} />
            </Stat>
            <Stat
              label="이번 달 추정 비용"
              value={usage ? money(usage.monthly.known_cost_usd) : "권한 없음"}
              note={
                usage
                  ? `미산정 ${usage.monthly.unpriced_requests}건 · 청구서와 별도`
                  : "비용은 운영·분석 역할에서 확인"
              }
              tone="blue"
            >
              <Wallet size={17} />
            </Stat>
          </div>
          <div className="ops-overview-grid">
            <section className="ops-panel">
              <header>
                <div>
                  <h2>데이터 운영</h2>
                  <p>수집부터 검토·스테이징까지, 기존 버전을 보존합니다.</p>
                </div>
                {session.permissions.includes("jobs") && (
                  <Link to="/hr/admin/jobs">
                    작업 이력
                    <ArrowRight size={14} />
                  </Link>
                )}
              </header>
              <div className="ops-pipeline">
                {[
                  {
                    n: "01",
                    title: "원문 수집",
                    sub: "공식 출처 · 새 버전 보관",
                    icon: Download,
                  },
                  {
                    n: "02",
                    title: "무결성 확인",
                    sub: "파일·본문·출처 해시",
                    icon: ShieldCheck,
                  },
                  {
                    n: "03",
                    title: "스테이징 재적재",
                    sub: "답변·검토 색인 분리",
                    icon: Database,
                  },
                ].map((item) => (
                  <div key={item.n}>
                    <span>{item.n}</span>
                    <item.icon size={21} />
                    <strong>{item.title}</strong>
                    <small>{item.sub}</small>
                  </div>
                ))}
              </div>
              <div className="ops-pipeline-end">
                <span className="ops-badge held">서비스 반영 보류</span>
                <p>
                  새 색인은 별도 버전으로 보관합니다. 현재 챗봇·벡터와 Supabase
                  적재를 변경하지 않습니다.
                </p>
              </div>
              <div className="ops-panel-actions">
                {session.permissions.includes("sources") && (
                  <Link className="ops-primary" to="/hr/admin/sources">
                    원문 관리
                    <ArrowRight size={15} />
                  </Link>
                )}
                {session.permissions.includes("reviews") && (
                  <Link className="ops-secondary" to="/hr/admin/reviews">
                    검토할 자료 보기
                  </Link>
                )}
              </div>
            </section>
            <section className="ops-panel">
              <header>
                <div>
                  <h2>운영 연결</h2>
                  <p>
                    {diagnostic
                      ? dateTime(diagnostic.at) + " 진단 결과"
                      : "서비스 진단을 실행해 현재 연결을 확인하세요."}
                  </p>
                </div>
                <ShieldCheck size={18} />
              </header>
              <div className="ops-health-list">
                {[
                  {
                    title: "기존 원문·AI 서비스",
                    value: diagnostic
                      ? diagnostic.upstream
                        ? "연결 확인"
                        : "확인 필요"
                      : "진단 전",
                    state: diagnostic?.upstream ? "succeeded" : "neutral",
                  },
                  {
                    title: "로컬 운영 저장소",
                    value: diagnostic
                      ? diagnostic.database
                        ? "연결 확인"
                        : "확인 필요"
                      : "현재 사용 중",
                    state: "succeeded",
                  },
                  {
                    title: "원문 무결성 기록",
                    value: diagnostic
                      ? diagnostic.corpus
                        ? "확인 완료"
                        : "확인 필요"
                      : "목록 조회 확인",
                    state: "succeeded",
                  },
                  {
                    title: "회사 SSO·직원 권한",
                    value: "연결 전",
                    state: "held",
                  },
                  { title: "Supabase 적재", value: "HOLD", state: "held" },
                ].map((item) => (
                  <div key={item.title}>
                    <span>{item.title}</span>
                    <Badge state={item.state}>{item.value}</Badge>
                  </div>
                ))}
              </div>
              <Link className="ops-panel-bottom" to="/hr/admin/settings">
                전체 연결·권한 확인
                <ArrowRight size={14} />
              </Link>
            </section>
          </div>
          <div className="ops-overview-grid ops-bottom-grid">
            <section className="ops-panel">
              <header>
                <div>
                  <h2>최근 데이터 작업</h2>
                  <p>실제 실행된 작업의 진행 상태</p>
                </div>
                <Boxes size={18} />
              </header>
              {data?.jobs.length ? (
                <div className="ops-recent-jobs">
                  {data.jobs.map((job) => (
                    <Link key={job.id} to="/hr/admin/jobs">
                      <span className="ops-operation-icon">
                        <Boxes size={17} />
                      </span>
                      <div>
                        <strong>{JOB_KINDS[job.kind]}</strong>
                        <small>{job.message}</small>
                      </div>
                      <Badge state={job.state} />
                    </Link>
                  ))}
                </div>
              ) : (
                <Empty
                  title="아직 실행한 작업이 없습니다."
                  description="원문을 선택하고 정합성 검사·재수집·재적재를 시작하세요."
                  to={
                    session.permissions.includes("sources")
                      ? "/hr/admin/sources"
                      : undefined
                  }
                  action="원문 목록 열기"
                />
              )}
            </section>
            <section className="ops-panel">
              <header>
                <div>
                  <h2>
                    {session.permissions.includes("cases")
                      ? "인사 서비스"
                      : "집계 범위"}
                  </h2>
                  <p>처리할 업무와 운영 범위를 구분합니다.</p>
                </div>
                <CircleHelp size={18} />
              </header>
              {session.permissions.includes("cases") ? (
                <div className="ops-inbox-summary">
                  <span>처리 중인 직원 문의</span>
                  <strong>
                    {open}
                    <small>건</small>
                  </strong>
                  <Link to="/hr/admin/cases">
                    문의 큐로 이동
                    <ArrowRight size={15} />
                  </Link>
                  <p>로컬 문의 체험 · 실제 회사 신청·결재와 별도</p>
                </div>
              ) : (
                <div className="ops-scope-note">
                  사용량은 이 게이트웨이를 거친 새 요청부터 집계합니다. 공급자
                  계정의 전체 과거 사용량이나 실제 청구서가 아닙니다.
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}

export function AdminSources() {
  const session = useAdmin(),
    navigate = useNavigate(),
    query = useControl<SourceCatalog>("/api/control/admin/sources");
  const [q, setQ] = useState(""),
    [scope, setScope] = useState("all"),
    [page, setPage] = useState(1),
    [ids, setIds] = useState<string[]>([]),
    [detail, setDetail] = useState<SourceDocument | null>(null),
    [kind, setKind] = useState<"verify" | "recollect" | "reindex" | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const docs = query.data?.items ?? [],
    filtered = docs.filter(
      (doc) =>
        doc.title.toLocaleLowerCase().includes(q.toLocaleLowerCase()) &&
        (scope === "all" ||
          (scope === "answer" ? doc.answer_count > 0 : doc.review_count > 0)),
    ),
    pages = Math.max(1, Math.ceil(filtered.length / 15)),
    items = filtered.slice((page - 1) * 15, page * 15),
    selected = docs.filter((doc) => ids.includes(doc.id));
  function select(id: string) {
    setError("");
    setIds((previous) =>
      previous.includes(id)
        ? previous.filter((value) => value !== id)
        : previous.length < 5
          ? [...previous, id]
          : previous,
    );
  }
  async function run() {
    if (!kind) return;
    setBusy(true);
    setError("");
    try {
      await control("/api/control/admin/jobs", "POST", {
        kind,
        documents: ids,
      });
      setKind(null);
      navigate("/hr/admin/jobs");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "작업을 시작하지 못했습니다.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="KNOWLEDGE SOURCES"
        title="원문·데이터"
        description="공식 출처와 답변 허용 범위를 확인하고, 필요한 문서만 다시 처리하세요."
      >
        <button className="ops-secondary" onClick={query.refresh}>
          <RefreshCw size={14} />
          목록 새로고침
        </button>
      </PageTitle>
      <QueryError error={query.error} retry={query.refresh} />
      {query.loading && !query.data ? (
        <Loading />
      ) : (
        <>
          <div className="ops-source-summary">
            <div>
              <Database size={18} />
              <strong>{count(query.data?.total)}</strong>
              <span>원문 문서</span>
            </div>
            <div>
              <i className="ops-dot blue" />
              <strong>{count(query.data?.answer_units)}</strong>
              <span>답변용 조문</span>
            </div>
            <div>
              <i className="ops-dot amber" />
              <strong>{count(query.data?.review_units)}</strong>
              <span>검토 전용 구간</span>
            </div>
            <span>사람 승인·KTcs 적용 미확인</span>
          </div>
          <section className="ops-panel ops-source-panel">
            <div className="ops-table-toolbar">
              <label className="ops-search">
                <Search size={16} />
                <input
                  aria-label="관리할 원문 검색"
                  placeholder="문서명으로 검색"
                  value={q}
                  maxLength={100}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setPage(1);
                  }}
                />
              </label>
              <label className="ops-select">
                <Filter size={14} />
                <select
                  aria-label="원문 사용 범위"
                  value={scope}
                  onChange={(e) => {
                    setScope(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="all">전체 사용 범위</option>
                  <option value="answer">답변용 조문 포함</option>
                  <option value="review">검토 전용 포함</option>
                </select>
              </label>
              <span>{filtered.length}개 문서</span>
            </div>
            {session.permissions.includes("jobs") && (
              <div className="ops-selection-toolbar">
                <span>
                  <strong>{ids.length}</strong>개 선택{" "}
                  <small>한 번에 최대 5개</small>
                </span>
                <button
                  disabled={!ids.length}
                  onClick={() => setKind("verify")}
                >
                  <ShieldCheck size={14} />
                  정합성 검사
                </button>
                <button
                  disabled={!ids.length}
                  onClick={() => setKind("recollect")}
                >
                  <RefreshCw size={14} />
                  원문 재수집
                </button>
                <button
                  className="ops-primary"
                  disabled={!ids.length}
                  onClick={() => setKind("reindex")}
                >
                  <Database size={14} />
                  스테이징 재적재
                </button>
                {ids.length > 0 && (
                  <button
                    className="ops-clear"
                    onClick={() => setIds([])}
                    aria-label="원문 선택 해제"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            )}
            <div className="ops-table-scroll">
              <table className="ops-table">
                <thead>
                  <tr>
                    {session.permissions.includes("jobs") && (
                      <th className="ops-check-col">
                        <span className="p-sr-only">문서 선택</span>
                      </th>
                    )}
                    <th>문서명·출처</th>
                    <th>답변용 조문</th>
                    <th>검토 구간</th>
                    <th>회사 적용</th>
                    <th>원문</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((doc) => (
                    <tr key={doc.id}>
                      {session.permissions.includes("jobs") && (
                        <td>
                          <input
                            type="checkbox"
                            aria-label={doc.title + " 선택"}
                            checked={ids.includes(doc.id)}
                            disabled={!ids.includes(doc.id) && ids.length >= 5}
                            onChange={() => select(doc.id)}
                          />
                        </td>
                      )}
                      <td>
                        <button
                          className="ops-document-name"
                          onClick={() => setDetail(doc)}
                        >
                          <span className="ops-file-icon">
                            <FileSearch size={19} />
                          </span>
                          <span>
                            <strong>{doc.title}</strong>
                            <small>
                              {doc.id} · {doc.format.toUpperCase()} · 한국전력
                            </small>
                          </span>
                        </button>
                      </td>
                      <td>
                        {doc.answer_count ? (
                          <span className="ops-count-pill">
                            {count(doc.answer_count)}
                          </span>
                        ) : (
                          <span className="ops-muted">—</span>
                        )}
                      </td>
                      <td>
                        {doc.review_count ? (
                          <span className="ops-count-pill amber">
                            {count(doc.review_count)}
                          </span>
                        ) : (
                          <span className="ops-muted">—</span>
                        )}
                      </td>
                      <td>
                        <Badge state="held">KTcs 미확인</Badge>
                      </td>
                      <td>
                        <button
                          className="ops-text-button"
                          onClick={() => setDetail(doc)}
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
            {!items.length && (
              <Empty
                title="일치하는 원문이 없습니다."
                description="검색어 또는 사용 범위를 바꿔보세요."
              />
            )}
            <div className="ops-pagination">
              <span>
                {filtered.length
                  ? Math.min((page - 1) * 15 + 1, filtered.length)
                  : 0}
                –{Math.min(page * 15, filtered.length)} / {filtered.length}
              </span>
              <div>
                <button
                  aria-label="원문 이전 페이지"
                  disabled={page <= 1}
                  onClick={() => setPage((value) => value - 1)}
                >
                  <ChevronLeft size={15} />
                </button>
                <span>
                  {page} / {pages}
                </span>
                <button
                  aria-label="원문 다음 페이지"
                  disabled={page >= pages}
                  onClick={() => setPage((value) => value + 1)}
                >
                  <ChevronRight size={15} />
                </button>
              </div>
            </div>
          </section>
          <p className="ops-page-footnote">
            <ShieldCheck size={13} />
            파일·문자 위치 검증과 조직의 최종 적용 승인은 다릅니다. 검토 전용
            구간은 답변에 사용하지 않습니다.
          </p>
        </>
      )}
      {kind && (
        <WorkspaceDialog
          title={JOB_KINDS[kind] + " 실행"}
          close={() => setKind(null)}
        >
          <div className="ops-job-confirm">
            <p>
              {kind === "recollect"
                ? "선택 문서의 한전 공식 주소에서 원문 파일을 새 버전으로 내려받습니다. 새 파일은 파싱·검토 전까지 격리 보관합니다."
                : kind === "reindex"
                  ? "현재 검증 기록에 맞는 원문으로 별도의 FTS 검색 색인을 만듭니다. 답변용·검토용을 분리하며 현재 챗봇·벡터를 교체하지 않습니다."
                  : "보존된 원본·정규화 파일과 검증 기록의 해시를 대조합니다."}
            </p>
            <ul>
              {selected.map((doc) => (
                <li key={doc.id}>
                  <FileSearch size={15} />
                  {doc.title}
                </li>
              ))}
            </ul>
            <div className="ops-inline-note">
              <ShieldCheck size={16} />
              기존 버전 보존 · 새 임베딩 없음 · Supabase 적재 HOLD
            </div>
            {error && (
              <p role="alert" className="ops-error">
                {error}
              </p>
            )}
            <footer>
              <button className="ops-secondary" onClick={() => setKind(null)}>
                돌아가기
              </button>
              <button
                className="ops-primary"
                disabled={busy}
                onClick={() => void run()}
              >
                <Play size={14} />
                {busy ? "작업 접수 중…" : "작업 실행"}
              </button>
            </footer>
          </div>
        </WorkspaceDialog>
      )}
      {detail && <SourceDetail doc={detail} close={() => setDetail(null)} />}
    </>
  );
}

function SourceDetail({
  doc,
  close,
}: {
  doc: SourceDocument;
  close: () => void;
}) {
  const excerpts = useControl<{
    items: {
      id: string;
      text: string;
      section: string;
      answer_eligible: boolean;
      sha256: string;
    }[];
  }>("/api/control/admin/sources/" + encodeURIComponent(doc.id) + "/excerpts");
  return (
    <WorkspaceDialog title="원문 상세" close={close}>
      <div className="ops-source-detail">
        <Badge state={doc.answer_count ? "succeeded" : "held"}>
          {doc.answer_count
            ? "답변용 조문 포함"
            : doc.review_count
              ? "검토 전용"
              : "검색 구간 없음"}
        </Badge>
        <h3>{doc.title}</h3>
        <div className="ops-detail-counts">
          <span>답변용 {count(doc.answer_count)}조문</span>
          <span>검토 전용 {count(doc.review_count)}구간</span>
        </div>
        <dl>
          <dt>출처</dt>
          <dd>한국전력 공개 참고자료</dd>
          <dt>원문 ID</dt>
          <dd>{doc.id}</dd>
          <dt>원본 SHA-256</dt>
          <dd>{doc.sha256}</dd>
          <dt>회사 적용</dt>
          <dd>KTcs 적용·현행성·사람 승인 미확인</dd>
        </dl>
        {doc.source_url && (
          <a
            href={doc.source_url}
            target="_blank"
            rel="noreferrer"
            className="ops-text-button"
          >
            공식 수집 주소
            <ExternalLink size={13} />
          </a>
        )}
        <QueryError error={excerpts.error} />
        {excerpts.data && !excerpts.data.items.length && (
          <Empty
            title="아직 검색 구간이 없는 문서입니다."
            description="원본은 보존되어 있으며, 분할·구조 검토 후 검색에 연결할 수 있습니다."
          />
        )}
        {excerpts.loading ? (
          <Loading />
        ) : (
          excerpts.data?.items.map((item) => (
            <details className="ops-excerpt" key={item.id}>
              <summary>
                {item.section}
                <Badge state={item.answer_eligible ? "succeeded" : "held"}>
                  {item.answer_eligible ? "답변 참고용" : "검토 전용"}
                </Badge>
              </summary>
              <blockquote>{item.text}</blockquote>
              <small>출처 ID {item.id}</small>
            </details>
          ))
        )}
        <p className="ops-muted">
          목록의 첫 원문 구간입니다. 검토 기록을 남겨도 답변 허용 범위는
          변경되지 않습니다.
        </p>
      </div>
    </WorkspaceDialog>
  );
}

export function AdminJobs() {
  const query = useControl<{ items: JobRecord[] }>(
      "/api/control/admin/jobs",
      true,
      (data) =>
        data?.items.some((job) => ["queued", "running"].includes(job.state))
          ? 2500
          : 0,
    ),
    [filter, setFilter] = useState("all"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [detail, setDetail] = useState<JobRecord | null>(null);
  const items = query.data?.items ?? [];
  async function act(job: JobRecord, action: "cancel" | "retry") {
    setBusy(job.id);
    setError("");
    try {
      await control(`/api/control/admin/jobs/${job.id}/${action}`, "POST", {});
      query.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "작업 상태를 변경하지 못했습니다.",
      );
    } finally {
      setBusy("");
    }
  }
  const filtered = items.filter(
    (job) => filter === "all" || job.state === filter,
  );
  return (
    <>
      <PageTitle
        eyebrow="COLLECTION & INGESTION"
        title="수집·재적재 작업"
        description="실행 상태와 버전별 결과를 확인하고, 실패한 작업은 새 버전으로 재시도하세요."
      >
        <button className="ops-secondary" onClick={query.refresh}>
          <RefreshCw size={14} />
          새로고침
        </button>
        <Link className="ops-primary" to="/hr/admin/sources">
          <Play size={14} />새 작업
        </Link>
      </PageTitle>
      <QueryError error={query.error} retry={query.refresh} />
      {error && (
        <p role="alert" className="ops-error">
          {error}
        </p>
      )}
      <div className="ops-stats ops-job-stats">
        <Stat
          label="실행·대기 중"
          value={
            items.filter((j) => ["queued", "running"].includes(j.state)).length
          }
          note="로컬 작업자 1개 · 순차 처리"
        >
          <Timer size={17} />
        </Stat>
        <Stat
          label="완료한 작업"
          value={items.filter((j) => j.state === "succeeded").length}
          note="기존 서비스 반영과 별도"
          tone="blue"
        >
          <Check size={17} />
        </Stat>
        <Stat
          label="실패·중단"
          value={
            items.filter((j) =>
              ["failed", "interrupted", "cancelled"].includes(j.state),
            ).length
          }
          note="기존 자료 유지 · 새 버전 재시도"
          tone="amber"
        >
          <Boxes size={17} />
        </Stat>
      </div>
      <div className="ops-inline-note">
        <Database size={16} />
        <span>
          재적재는 별도의 스테이징 검색 색인을 생성합니다. 서비스 반영·대규모
          재임베딩·클라우드 적재는 실행하지 않습니다.
        </span>
      </div>
      <section className="ops-panel">
        <div className="ops-filter-tabs">
          {["all", "running", "succeeded", "failed", "cancelled"].map(
            (value) => (
              <button
                key={value}
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {value === "all" ? "전체 작업" : JOB_STATES[value]}
              </button>
            ),
          )}
        </div>
        {query.loading && !query.data ? (
          <Loading />
        ) : filtered.length ? (
          <div className="ops-job-list">
            {filtered.map((job) => (
              <div className="ops-job-row" key={job.id}>
                <span className="ops-job-icon">
                  <Boxes size={20} />
                </span>
                <div className="ops-job-main">
                  <div>
                    <strong>{JOB_KINDS[job.kind]}</strong>
                    <Badge state={job.state} />
                    <small>{dateTime(job.created_at)}</small>
                  </div>
                  <p>{job.message}</p>
                  <div className="ops-job-meta">
                    <span>{job.id}</span>
                    <span>문서 {job.documents.length}개</span>
                    {job.retry_of && <span>이전 작업 재시도</span>}
                  </div>
                  {["running", "queued"].includes(job.state) && (
                    <div
                      className="ops-progress"
                      aria-label={"작업 진행 " + job.progress + "%"}
                    >
                      <i style={{ width: job.progress + "%" }} />
                    </div>
                  )}
                </div>
                <div className="ops-job-actions">
                  {["running", "queued"].includes(job.state) && (
                    <button
                      disabled={busy === job.id}
                      onClick={() => void act(job, "cancel")}
                    >
                      <Square size={12} />
                      중지
                    </button>
                  )}
                  {["failed", "cancelled", "interrupted"].includes(
                    job.state,
                  ) && (
                    <button
                      disabled={busy === job.id}
                      onClick={() => void act(job, "retry")}
                    >
                      <RefreshCw size={13} />
                      재시도
                    </button>
                  )}
                  {job.report && (
                    <button onClick={() => setDetail(job)}>
                      결과 보기
                      <ChevronRight size={13} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Empty
            title="이 상태의 작업이 없습니다."
            description="원문을 선택해 필요한 작업을 실행하세요. 실제 실행 이력만 표시합니다."
            to="/hr/admin/sources"
            action="원문 목록 열기"
          />
        )}
      </section>
      {detail?.report && (
        <WorkspaceDialog title="작업 결과" close={() => setDetail(null)}>
          <div className="ops-job-confirm">
            <Badge state={detail.state} />
            <h3>{JOB_KINDS[detail.kind]}</h3>
            <p>{detail.message}</p>
            <dl className="ops-key-values">
              <dt>버전·작업 ID</dt>
              <dd>{detail.id}</dd>
              <dt>답변용 조문</dt>
              <dd>{count(detail.report.answer_units)}</dd>
              <dt>검토 전용 구간</dt>
              <dd>{count(detail.report.review_units)}</dd>
              <dt>서비스 변경</dt>
              <dd>없음 · 현재 버전 유지</dd>
              <dt>새 임베딩</dt>
              <dd>{detail.report.new_embeddings}회</dd>
              {detail.report.index_sha256 && (
                <>
                  <dt>색인 SHA-256</dt>
                  <dd>{detail.report.index_sha256}</dd>
                </>
              )}
            </dl>
            {detail.kind === "recollect" &&
              detail.report.documents?.map((doc) => (
                <section className="ops-download-result" key={doc.id}>
                  <strong>{doc.title}</strong>
                  <Badge state={doc.same_as_preserved ? "succeeded" : "held"}>
                    {doc.same_as_preserved
                      ? "기존 파일과 동일"
                      : "새 파일 · 검토 필요"}
                  </Badge>
                  <p>수집 크기 {count(doc.downloaded_bytes)} bytes</p>
                  <small>
                    재수집 파일은 별도 보관됩니다. 새로운 파일의 파싱·검토와
                    서비스 반영은 별도입니다.
                  </small>
                </section>
              ))}
            <a
              className="ops-primary"
              href={`/api/control/admin/jobs/${detail.id}/report`}
              download
            >
              <ArrowDownToLine size={15} />
              검증 보고서 내려받기
            </a>
          </div>
        </WorkspaceDialog>
      )}
    </>
  );
}

export function AdminReviews() {
  const catalog = useControl<SourceCatalog>("/api/control/admin/sources"),
    ledger = useControl<{ items: ReviewRecord[] }>(
      "/api/control/admin/reviews",
    ),
    [q, setQ] = useState(""),
    [selected, setSelected] = useState<SourceDocument | null>(null),
    [notice, setNotice] = useState("");
  const records = new Map(
      (ledger.data?.items ?? []).map((row) => [row.id, row]),
    ),
    docs = (catalog.data?.items ?? []).filter(
      (doc) => doc.review_count > 0 && doc.title.includes(q),
    );
  function refresh() {
    catalog.refresh();
    ledger.refresh();
  }
  return (
    <>
      <PageTitle
        eyebrow="KNOWLEDGE REVIEW"
        title="원문 검토"
        description="검토 대상 문서에 담당 기록과 사유를 남기고, 답변 사용 여부와 구분해 관리하세요."
      >
        <button className="ops-secondary" onClick={refresh}>
          <RefreshCw size={14} />
          새로고침
        </button>
        <Link className="ops-primary" to="/hr/library?tab=review">
          <FileSearch size={15} />
          검토 발췌 검색
        </Link>
      </PageTitle>
      <QueryError error={catalog.error || ledger.error} retry={refresh} />
      {notice && (
        <p className="ops-success" role="status">
          <Check size={15} />
          {notice}
        </p>
      )}
      <div className="ops-inline-note amber">
        <BookCheck size={17} />
        검토 기록 완료는 조직 승인이나 답변 근거 승격이 아닙니다. 보류 문서의
        현재 답변 차단은 유지됩니다.
      </div>
      <section className="ops-panel">
        <div className="ops-table-toolbar">
          <label className="ops-search">
            <Search size={16} />
            <input
              aria-label="검토 문서 검색"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="검토할 문서명"
            />
          </label>
          <span>검토 구간이 있는 문서 {docs.length}개</span>
        </div>
        {catalog.loading && !catalog.data ? (
          <Loading />
        ) : (
          <div className="ops-table-scroll">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>검토 문서</th>
                  <th>검토 구간</th>
                  <th>검토 기록</th>
                  <th>최근 기록</th>
                  <th>작업</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => {
                  const record = records.get(doc.id);
                  return (
                    <tr key={doc.id}>
                      <td>
                        <strong>{doc.title}</strong>
                        <small className="ops-cell-sub">
                          {doc.id} · 한전 참고자료
                        </small>
                      </td>
                      <td>
                        <span className="ops-count-pill amber">
                          {count(doc.review_count)}
                        </span>
                      </td>
                      <td>
                        <Badge state={record?.state ?? "held"}>
                          {record?.state === "reviewed"
                            ? "기록 완료"
                            : record?.state === "in_review"
                              ? "검토 중"
                              : record
                                ? "보류 유지"
                                : "검토 전"}
                        </Badge>
                      </td>
                      <td className="ops-muted">
                        {record ? dateTime(record.updated_at) : "—"}
                      </td>
                      <td>
                        <button
                          className="ops-text-button"
                          onClick={() => {
                            setSelected(doc);
                            setNotice("");
                          }}
                        >
                          기록하기
                          <ChevronRight size={13} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {selected && (
        <ReviewEditor
          key={selected.id}
          doc={selected}
          record={records.get(selected.id)}
          close={() => setSelected(null)}
          saved={() => {
            setSelected(null);
            ledger.refresh();
            setNotice(
              "검토 기록을 저장했습니다. 답변 허용 범위와 사람 승인 상태는 변경하지 않았습니다.",
            );
          }}
        />
      )}
    </>
  );
}
function ReviewEditor({
  doc,
  record,
  close,
  saved,
}: {
  doc: SourceDocument;
  record?: ReviewRecord;
  close: () => void;
  saved: () => void;
}) {
  const [state, setState] = useState(record?.state ?? "in_review"),
    [note, setNote] = useState(record?.note ?? ""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await control("/api/control/admin/reviews", "PUT", {
        document_id: doc.id,
        state,
        note: note.trim(),
        revision: record?.revision ?? 0,
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
    <WorkspaceDialog title="원문 검토 기록" close={close}>
      <form className="ops-form" onSubmit={save}>
        <h3>{doc.title}</h3>
        <p className="ops-muted">
          검토 전용 {count(doc.review_count)}구간 · KTcs 적용 미확인
        </p>
        <label>
          검토 상태
          <select value={state} onChange={(e) => setState(e.target.value)}>
            <option value="in_review">검토 중</option>
            <option value="held">보류 유지</option>
            <option value="reviewed">검토 기록 완료 · 답변 승격 없음</option>
          </select>
        </label>
        <label>
          확인한 내용·남은 사유
          <textarea
            required
            minLength={5}
            maxLength={1000}
            rows={6}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="원문 경계, 표 구조, 적용 범위 등의 확인 내용을 남겨주세요."
          />
        </label>
        <div className="ops-inline-note amber">
          <ShieldCheck size={16} />
          저장 후에도 검토 전용 자료의 답변 사용은 차단됩니다.
        </div>
        {error && (
          <p className="ops-error" role="alert">
            {error}
          </p>
        )}
        <button
          className="ops-primary"
          disabled={busy || note.trim().length < 5}
        >
          <Check size={15} />
          {busy ? "저장 중…" : "검토 기록 저장"}
        </button>
      </form>
    </WorkspaceDialog>
  );
}
