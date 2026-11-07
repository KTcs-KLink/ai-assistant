import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowDownUp,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileCheck2,
  FolderOpen,
  ListFilter,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useHr } from "./HrContext";
import type { Preparation } from "./api";
import { WorkspaceDialog } from "./HrWorkspaceShell";
import { attempt } from "./ui";

type WorkStatus = "progress" | "ready" | "review";
type WorkFilter = "all" | WorkStatus;
const STATUS_LABELS: Record<WorkStatus, string> = {
  progress: "진행 중",
  ready: "준비 완료",
  review: "재확인 필요",
};
function progress(plan: Preparation) {
  const total = plan.checklist.length;
  const checked = new Set(
    plan.checked.filter(
      (index) => Number.isInteger(index) && index >= 0 && index < total,
    ),
  ).size;
  return {
    checked,
    total,
    percent: total ? Math.round((checked / total) * 100) : 0,
  };
}
function status(plan: Preparation): WorkStatus {
  if (plan.stale) return "review";
  const value = progress(plan);
  return value.total > 0 && value.checked === value.total
    ? "ready"
    : "progress";
}
const QUESTIONS = [
  "병가 증빙은 언제 제출해야 하나요?",
  "정기 급여 지급일은 언제인가요?",
  "업무 사정으로 휴게시간을 바꿀 수 있나요?",
];
const RESOURCES = [
  {
    title: "휴가·근태",
    description: "휴가와 근무 기준",
    query: "휴가",
    icon: Clock3,
  },
  {
    title: "급여·보수",
    description: "지급일과 수당 기준",
    query: "보수",
    icon: FileCheck2,
  },
  {
    title: "취업규칙",
    description: "복무와 인사 규정",
    query: "취업규칙",
    icon: BookOpen,
  },
];

export function HrWorkspace() {
  const { plans, readiness, session, refresh, check, busy } = useHr();
  const [filter, setFilter] = useState<WorkFilter>("all"),
    [query, setQuery] = useState(""),
    [order, setOrder] = useState<"title" | "progress">("title"),
    [question, setQuestion] = useState(""),
    [selectedId, setSelectedId] = useState<string | null>(null);
  const navigate = useNavigate();
  const research = readiness?.research;
  const selected = plans?.find((plan) => plan.id === selectedId);
  const referenceAvailable =
    research?.company === "KEPCO" && research.source_count > 0;
  const counts = plans
    ? {
        all: plans.length,
        progress: plans.filter((plan) => status(plan) === "progress").length,
        ready: plans.filter((plan) => status(plan) === "ready").length,
        review: plans.filter((plan) => status(plan) === "review").length,
      }
    : null;
  const filtered =
    plans?.filter(
      (plan) =>
        (filter === "all" || status(plan) === filter) &&
        plan.title
          .toLocaleLowerCase("ko")
          .includes(query.trim().toLocaleLowerCase("ko")),
    ) ?? [];
  const shown = [...filtered].sort((a, b) =>
    order === "title"
      ? a.title.localeCompare(b.title, "ko")
      : progress(b).percent - progress(a).percent ||
        a.title.localeCompare(b.title, "ko"),
  );
  function openQuestion(text: string) {
    const draftQuestion = text.trim();
    if (draftQuestion.length < 2 || draftQuestion.length > 500) return;
    navigate("/hr/assistant", { state: { draftQuestion } });
  }
  function submitQuestion(event: FormEvent) {
    event.preventDefault();
    openQuestion(question);
  }
  const today = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date());
  return (
    <div className="ws-dashboard">
      <header className="ws-page-heading">
        <div>
          <h1>업무 현황</h1>
          <p>준비 중인 업무와 필요한 규정을 확인하세요.</p>
        </div>
        <div className="ws-page-heading-actions">
          <span>{today}</span>
          <Link className="ws-primary" to="/hr/assistant">
            <Sparkles size={16} />
            AI 질문 작성
          </Link>
        </div>
      </header>
      <section className="ws-metrics" aria-label="내 업무 요약">
        <button
          onClick={() => setFilter("all")}
          aria-pressed={filter === "all"}
        >
          <div>
            <span>전체 준비 업무</span>
            <FileCheck2 size={17} />
          </div>
          <strong>
            {counts?.all ?? "—"}
            <small>건</small>
          </strong>
          <p>현재 접속 계정의 준비 목록</p>
        </button>
        <button
          onClick={() => setFilter("progress")}
          aria-pressed={filter === "progress"}
        >
          <div>
            <span>진행 중</span>
            <Clock3 size={17} />
          </div>
          <strong>
            {counts?.progress ?? "—"}
            <small>건</small>
          </strong>
          <p>확인할 준비 항목이 있는 업무</p>
        </button>
        <button
          onClick={() => setFilter("review")}
          aria-pressed={filter === "review"}
          className={counts?.review ? "ws-metric-review" : ""}
        >
          <div>
            <span>재확인 필요</span>
            <CircleHelp size={17} />
          </div>
          <strong>
            {counts?.review ?? "—"}
            <small>건</small>
          </strong>
          <p>규정·조건 확인이 필요한 업무</p>
        </button>
        <Link to="/hr/library?tab=rules">
          <div>
            <span>검색 가능한 조문</span>
            <BookOpen size={17} />
          </div>
          <strong>
            {referenceAvailable
              ? research.source_count.toLocaleString("ko-KR")
              : "—"}
            <small>개</small>
          </strong>
          <p>
            {referenceAvailable
              ? `한전 공개 참고자료 · ${research.document_count}개 문서`
              : "원문 연결 확인 필요"}
          </p>
        </Link>
      </section>

      <div className="ws-dashboard-grid">
        <section
          className="ws-card ws-work-panel"
          aria-labelledby="ws-work-title"
        >
          <header className="ws-card-heading">
            <div>
              <h2 id="ws-work-title">나의 준비 업무</h2>
              <span>
                {session?.mode === "demo"
                  ? "예시 직원의 준비 목록"
                  : "현재 접속 계정의 준비 목록"}
              </span>
            </div>
            <Link to="/hr/preparations">
              준비 목록 열기
              <ArrowUpRight size={15} />
            </Link>
          </header>
          <div className="ws-work-filters" aria-label="준비 업무 상태 필터">
            {(["all", "progress", "ready", "review"] as const).map((item) => (
              <button
                key={item}
                aria-pressed={filter === item}
                onClick={() => setFilter(item)}
              >
                {item === "all" ? "전체" : STATUS_LABELS[item]}
                <span>{counts?.[item] ?? "—"}</span>
              </button>
            ))}
          </div>
          <div className="ws-table-toolbar">
            <label className="ws-local-search">
              <Search size={15} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="업무명 검색"
                aria-label="준비 업무명 검색"
              />
            </label>
            <label className="ws-sort">
              <ArrowDownUp size={14} />
              <select
                aria-label="준비 업무 정렬"
                value={order}
                onChange={(event) =>
                  setOrder(event.target.value as "title" | "progress")
                }
              >
                <option value="title">이름순</option>
                <option value="progress">준비 진행순</option>
              </select>
            </label>
          </div>
          {plans === null ? (
            <div className="ws-work-empty" role="status">
              <CircleHelp size={31} />
              <h3>업무 목록을 불러오지 못했어요</h3>
              <p>연결을 확인한 뒤 다시 조회해 주세요.</p>
              <button className="ws-secondary" onClick={() => void refresh()}>
                다시 조회
                <ArrowRight size={14} />
              </button>
            </div>
          ) : shown.length ? (
            <div
              className="ws-table-scroll"
              tabIndex={0}
              aria-label="준비 업무 표"
            >
              <table>
                <thead>
                  <tr>
                    <th scope="col">업무명</th>
                    <th scope="col">준비 현황</th>
                    <th scope="col">상태</th>
                    <th scope="col">
                      <span className="p-sr-only">상세 보기</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((plan) => {
                    const value = progress(plan),
                      state = status(plan);
                    return (
                      <tr key={plan.id}>
                        <td>
                          <button
                            className="ws-work-name"
                            onClick={() => setSelectedId(plan.id)}
                          >
                            <span>
                              <FileCheck2 size={17} />
                            </span>
                            <div>
                              <strong>{plan.title}</strong>
                              <small>
                                {plan.stale
                                  ? "규정·조건 재확인 필요"
                                  : "신청 전 준비 항목"}
                                {session?.mode === "demo" ? " · 예시" : ""}
                              </small>
                            </div>
                          </button>
                        </td>
                        <td>
                          <div className="ws-progress">
                            <div>
                              <span style={{ width: `${value.percent}%` }} />
                            </div>
                            <span>
                              {value.checked}/{value.total}
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className={"ws-badge " + state}>
                            {state === "ready" && <CheckCircle2 size={12} />}
                            {STATUS_LABELS[state]}
                          </span>
                        </td>
                        <td>
                          <button
                            className="ws-row-open"
                            onClick={() => setSelectedId(plan.id)}
                            aria-label={plan.title + " 준비 항목 열기"}
                          >
                            <ChevronRight size={16} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ws-work-empty">
              <span className="ws-empty-icon">
                {plans.length ? (
                  <ListFilter size={28} />
                ) : (
                  <FolderOpen size={29} />
                )}
              </span>
              <h3>
                {plans.length
                  ? "조건에 맞는 업무가 없습니다"
                  : "등록된 준비 업무가 없습니다"}
              </h3>
              <p>
                {plans.length
                  ? "검색어나 상태 필터를 변경해 보세요."
                  : "필요한 규정과 증빙을 먼저 확인해 보세요."}
              </p>
              {plans.length ? (
                <button
                  className="ws-secondary"
                  onClick={() => {
                    setFilter("all");
                    setQuery("");
                  }}
                >
                  필터 초기화
                </button>
              ) : (
                <Link className="ws-secondary" to="/hr/library?tab=rules">
                  <Search size={14} />
                  규정부터 찾아보기
                </Link>
              )}
            </div>
          )}
          <footer className="ws-table-footer">
            <span>
              {plans === null
                ? "목록 조회 확인 필요"
                : `${shown.length}개 표시 / 전체 ${plans.length}개`}
            </span>
            <span>준비 완료와 회사 신청·승인은 별도입니다.</span>
          </footer>
        </section>

        <aside className="ws-context-column">
          <section
            className="ws-card ws-ask-panel"
            aria-labelledby="ws-ask-title"
          >
            <header className="ws-card-heading">
              <div>
                <h2 id="ws-ask-title">
                  <Sparkles size={17} />
                  규정 질문
                </h2>
                <span>답변과 근거 원문을 함께 확인하세요.</span>
              </div>
            </header>
            <form onSubmit={submitQuestion}>
              <label htmlFor="ws-question" className="p-sr-only">
                홈 인사 질문
              </label>
              <textarea
                id="ws-question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                maxLength={500}
                rows={3}
                placeholder="궁금한 인사 업무를 입력하세요."
              />
              <div>
                <span>{question.length}/500</span>
                <button
                  className="ws-primary"
                  disabled={question.trim().length < 2}
                >
                  질문 이어쓰기
                  <ArrowRight size={14} />
                </button>
              </div>
            </form>
            <p className="ws-privacy-hint">
              <ShieldCheck size={12} />
              개인정보 없이 질문하세요. 이동 후 전송할 수 있어요.
            </p>
            <div className="ws-quick-questions">
              {QUESTIONS.map((text) => (
                <button key={text} onClick={() => openQuestion(text)}>
                  {text}
                  <ArrowUpRight size={14} />
                </button>
              ))}
            </div>
          </section>
          <section className="ws-card ws-source-panel">
            <header>
              <ShieldCheck size={17} />
              <h2>데이터 적용 범위</h2>
              <Link to="/hr/status" aria-label="데이터 적용 범위 자세히 보기">
                <ArrowUpRight size={15} />
              </Link>
            </header>
            <div>
              <span
                className={"ws-dot" + (referenceAvailable ? " connected" : "")}
              />
              <strong>한국전력 공개 참고자료</strong>
              <span className="ws-badge">
                {referenceAvailable ? "검색 연결" : "확인 필요"}
              </span>
            </div>
            <p>KTcs 적용·현행성·최종 승인은 확인 전입니다.</p>
            {research?.source_scope === "expanded" && (
              <Link className="ws-review-scope" to="/hr/library?tab=review">
                검토 전용{" "}
                {research.review_only_count?.toLocaleString("ko-KR") ??
                  "미확인"}
                구간 · 답변 미사용
              </Link>
            )}
            <dl>
              <div>
                <dt>공식 양식</dt>
                <dd>
                  {readiness
                    ? readiness.official_form_count
                      ? "권한 확인 필요"
                      : "미연결"
                    : "미확인"}
                </dd>
              </div>
              <div>
                <dt>회사 인증·SSO</dt>
                <dd>미연결</dd>
              </div>
              <div>
                <dt>실제 신청·결재</dt>
                <dd>미연결</dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>
      <section
        className="ws-card ws-resources"
        aria-labelledby="ws-resources-title"
      >
        <header className="ws-card-heading">
          <div>
            <h2 id="ws-resources-title">업무 자료 바로가기</h2>
            <span>업무 주제별로 연결된 원문을 찾아보세요.</span>
          </div>
          <Link to="/hr/library">
            전체 자료
            <ArrowUpRight size={15} />
          </Link>
        </header>
        <div>
          {RESOURCES.map(
            ({ title, description, query: sourceQuery, icon: Icon }) => (
              <Link
                key={title}
                to={
                  "/hr/library?tab=rules&q=" + encodeURIComponent(sourceQuery)
                }
              >
                <span>
                  <Icon size={19} />
                </span>
                <div>
                  <strong>{title}</strong>
                  <small>{description}</small>
                </div>
                <ChevronRight size={15} />
              </Link>
            ),
          )}
          <Link to="/hr/library?tab=forms">
            <span>
              <FileCheck2 size={19} />
            </span>
            <div>
              <strong>양식·증빙</strong>
              <small>준비 안내 · 공식 파일 연결 전</small>
            </div>
            <ChevronRight size={15} />
          </Link>
        </div>
      </section>
      {selected && (
        <WorkspaceDialog
          title={selected.title}
          close={() => setSelectedId(null)}
        >
          <div className="ws-plan-detail">
            <div className="ws-plan-detail-status">
              <span className={"ws-badge " + status(selected)}>
                {STATUS_LABELS[status(selected)]}
              </span>
              {session?.mode === "demo" && (
                <span className="ws-badge warning">예시 직원의 준비 업무</span>
              )}
              {busy && (
                <span className="ws-badge" role="status">
                  저장 중…
                </span>
              )}
            </div>
            {selected.stale && (
              <p className="ws-stale-notice">
                규정과 내 조건을 다시 확인해야 합니다. 현재 준비 항목은 수정할
                수 없습니다.
              </p>
            )}
            <h3>준비 체크리스트</h3>
            {selected.checklist.length ? (
              <div className="ws-detail-checklist">
                {selected.checklist.map((item, index) => (
                  <label key={index}>
                    <input
                      type="checkbox"
                      checked={selected.checked.includes(index)}
                      disabled={busy || selected.stale}
                      onChange={(event) =>
                        void attempt(
                          check(selected, index, event.target.checked),
                        )
                      }
                    />
                    <span>{item}</span>
                  </label>
                ))}
              </div>
            ) : (
              <p>등록된 준비 항목이 없습니다.</p>
            )}
            <p className="ws-detail-note">
              체크 항목은 준비 현황에 반영됩니다. 실제 회사 신청·결재나 자격
              승인은 별도입니다.
            </p>
            <footer>
              <span>규정 버전 · {selected.policy_version}</span>
              <Link className="ws-secondary" to="/hr/preparations">
                준비 목록에서 확인
                <ArrowRight size={14} />
              </Link>
            </footer>
          </div>
        </WorkspaceDialog>
      )}
    </div>
  );
}
