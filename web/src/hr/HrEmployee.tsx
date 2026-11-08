import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  FileCheck2,
  Inbox,
  MessageSquareText,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useHr } from "./HrContext";
import { WorkspaceDialog } from "./HrWorkspaceShell";
import {
  CASE_STATES,
  ControlError,
  control,
  count,
  dateTime,
  useControl,
  type CaseRecord,
  type OpsSession,
} from "./operations";
import "./employee.css";
import "./account.css";
import "./operations.css";

function EmployeeCaseAccess({
  children,
}: {
  children: (refresh: () => void) => ReactNode;
}) {
  const session = useControl<OpsSession>("/api/control/session");
  const [pending, setPending] = useState(false),
    [error, setError] = useState("");
  async function enter() {
    setPending(true);
    setError("");
    try {
      await control("/api/control/session/demo", "POST", { role: "employee" });
      session.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "문의를 시작하지 못했습니다.",
      );
    } finally {
      setPending(false);
    }
  }
  if (session.data && !session.error) return children(session.refresh);
  if (session.loading)
    return (
      <p role="status" className="emp-muted">
        내 문의 접속을 확인하고 있어요.
      </p>
    );
  return (
    <div className="emp-access">
      <MessageSquareText size={24} />
      <div>
        <strong>내 문의를 한 곳에서 확인하세요</strong>
        <p>
          등록·처리 안내를 로컬 체험 계정에 보관합니다. 실제 회사 접수·결재와
          연결되지 않습니다.
        </p>
      </div>
      <button
        className="emp-primary"
        onClick={() => void enter()}
        disabled={pending}
      >
        {pending ? "연결 중…" : "문의 체험 시작"}
        <ArrowRight size={15} />
      </button>
      {(error ||
        (session.error &&
          !(
            session.error instanceof ControlError &&
            session.error.status === 401
          ))) && <p role="alert">{error || session.error?.message}</p>}
    </div>
  );
}

export function HrEmployeeHome() {
  const { session, readiness } = useHr();
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  function ask(event: FormEvent) {
    event.preventDefault();
    if (question.trim().length >= 2)
      navigate("/hr/assistant", { state: { draftQuestion: question.trim() } });
  }
  return (
    <div className="emp-home">
      <div className="emp-intro">
        <div>
          <p className="emp-eyebrow">MY WORKSPACE</p>
          <h1>{session?.name ?? "직원"}님, 안녕하세요.</h1>
          <p>필요한 규정을 찾고, 확인할 업무를 이어서 처리하세요.</p>
        </div>
        <span className="emp-account">
          직원 화면 <i /> 예시 계정
        </span>
      </div>
      <section className="emp-ai-start">
        <div className="emp-ai-heading">
          <span>
            <Sparkles size={20} />
          </span>
          <div>
            <h2>업무의 시작은, 필요한 답부터.</h2>
            <p>연결된 한전 원문을 검색하고 답변의 근거까지 확인합니다.</p>
          </div>
          <span className="emp-live">원문 연결</span>
        </div>
        <form onSubmit={ask}>
          <label className="p-sr-only" htmlFor="emp-ai-query">
            AI에게 물어볼 질문
          </label>
          <input
            id="emp-ai-query"
            value={question}
            maxLength={500}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="예: 휴가 신청과 허가는 어떤 절차로 진행하나요?"
          />
          <button disabled={question.trim().length < 2}>
            <ArrowRight size={20} />
            <span className="p-sr-only">AI 질문 이어 쓰기</span>
          </button>
        </form>
        <div className="emp-question-links">
          {[
            "병가 증빙은 언제 필요한가요?",
            "정기 급여 지급일은 언제인가요?",
            "휴게시간을 바꿀 수 있나요?",
          ].map((text) => (
            <button
              key={text}
              onClick={() =>
                navigate("/hr/assistant", { state: { draftQuestion: text } })
              }
            >
              {text}
              <ChevronRight size={12} />
            </button>
          ))}
        </div>
        <footer>
          <ShieldCheck size={12} />
          한전 참고자료 {count(readiness?.research.source_count)}조문 · KTcs
          적용은 별도 확인이 필요합니다.
        </footer>
      </section>
      <nav className="emp-shortcuts" aria-label="직원 업무 바로가기">
        <Link to="/hr/requests?new=1">
          <MessageSquareText />
          <div>
            <strong>담당자에게 문의</strong>
            <span>궁금한 업무를 등록하고 진행 확인</span>
          </div>
          <ChevronRight size={17} />
        </Link>
        <Link to="/hr/library">
          <BookOpen />
          <div>
            <strong>규정·양식 찾기</strong>
            <span>원문과 공식 양식의 연결 상태 확인</span>
          </div>
          <ChevronRight size={17} />
        </Link>
        <Link to="/hr/library?tab=forms">
          <FileCheck2 />
          <div>
            <strong>공식 양식 확인</strong>
            <span>회사 양식의 연결 상태와 안내 확인</span>
          </div>
          <ChevronRight size={17} />
        </Link>
      </nav>
      <div className="emp-home-grid">
        <section className="emp-panel">
          <header>
            <div>
              <h2>내 문의</h2>
              <p>최근 등록한 문의와 처리 안내</p>
            </div>
            <Link to="/hr/requests">
              전체 보기
              <ArrowRight size={14} />
            </Link>
          </header>
          <EmployeeCaseAccess>{() => <CaseList compact />}</EmployeeCaseAccess>
        </section>
        <aside className="emp-panel emp-rule-links">
          <header>
            <div>
              <h2>자주 찾는 규정</h2>
              <p>필요한 원문으로 바로 이동하세요.</p>
            </div>
            <BookOpen size={17} />
          </header>
          {[
            {
              title: "휴가·휴직",
              description: "신청 절차와 확인할 조건",
              q: "휴가 허가",
            },
            {
              title: "급여·보수",
              description: "지급일과 계산 기준의 원문",
              q: "보수 지급일",
            },
            {
              title: "근무·휴게시간",
              description: "근무 유형별 규정 확인",
              q: "휴게시간",
            },
          ].map((item) => (
            <Link
              key={item.q}
              to={"/hr/library?tab=rules&q=" + encodeURIComponent(item.q)}
            >
              <span>
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </span>
              <ChevronRight size={15} />
            </Link>
          ))}
          <div className="emp-source-foot">
            <span className="emp-status-dot" />
            답변용 {count(readiness?.research.source_count)}조문
            <span>검토 자료는 별도 구분</span>
          </div>
        </aside>
      </div>
      <div className="emp-bottom-note">
        <CircleHelp size={15} />
        <span>현재는 한전 참고자료와 로컬 체험 계정으로 이용 중입니다.</span>
        <Link to="/hr/status">
          회사 연결 상태
          <ArrowRight size={13} />
        </Link>
      </div>
    </div>
  );
}

export function HrEmployeeAccount() {
  const { session } = useHr();
  return (
    <div className="emp-account-page">
      <div className="emp-intro">
        <div>
          <p className="emp-eyebrow">MY ACCOUNT</p>
          <h1>내 계정</h1>
          <p>현재 접속 범위와 정보가 보관되는 위치를 확인하세요.</p>
        </div>
        <span className="emp-account">
          {session?.mode === "demo" ? "예시 계정" : "연결 계정"}
        </span>
      </div>
      <div className="emp-home-grid">
        <section className="emp-panel">
          <header>
            <div>
              <h2>접속 정보</h2>
              <p>실제 회사 계정과 참고자료 체험을 구분합니다.</p>
            </div>
            <ShieldCheck size={19} />
          </header>
          <dl className="emp-account-fields">
            <dt>이름</dt>
            <dd>
              {session?.mode === "demo"
                ? "예시 직원"
                : (session?.name ?? "미확인")}
            </dd>
            <dt>회사 인증</dt>
            <dd>회사 SSO 연결 전</dd>
            <dt>조회 자료</dt>
            <dd>한국전력 공개 참고자료</dd>
            <dt>회사 적용</dt>
            <dd>KTcs 적용·현행성·최종 승인 미확인</dd>
          </dl>
          <Link className="emp-account-link" to="/hr/status">
            연결·적용 상태 자세히 보기
            <ArrowRight size={14} />
          </Link>
        </section>
        <section className="emp-panel">
          <header>
            <div>
              <h2>정보 보관 안내</h2>
              <p>필요한 업무 정보만 다룹니다.</p>
            </div>
            <CircleHelp size={18} />
          </header>
          <div className="emp-account-notes">
            <p>
              <strong>AI 대화</strong>
              <span>
                이 탭의 현재 화면에 유지됩니다. 운영 사용량 기록에는 질문·답변
                본문이나 직원 프로필을 보관하지 않습니다.
              </span>
            </p>
            <p>
              <strong>내 문의</strong>
              <span>
                일반 문의와 처리 안내를 로컬 체험 저장소에 보관합니다. 실제
                회사의 신청·결재와는 별도입니다.
              </span>
            </p>
            <p>
              <strong>개인 조건</strong>
              <span>
                현재 화면에서는 가족·자녀·가구·복지 자격 조건을 입력하거나
                조회하지 않습니다.
              </span>
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

export function HrEmployeeRequests() {
  return (
    <div className="emp-requests">
      <div className="emp-intro">
        <div>
          <p className="emp-eyebrow">MY REQUESTS</p>
          <h1>내 문의</h1>
          <p>문의한 내용을 확인하고, 담당자의 처리 안내를 이어서 확인하세요.</p>
        </div>
        <span className="emp-account">로컬 문의 체험</span>
      </div>
      <EmployeeCaseAccess>{() => <CaseList />}</EmployeeCaseAccess>
    </div>
  );
}

function CaseList({ compact = false }: { compact?: boolean }) {
  const navigate = useNavigate();
  const query = useControl<{ items: CaseRecord[] }>("/api/control/cases");
  const [filter, setFilter] = useState("all"),
    [selected, setSelected] = useState<CaseRecord | null>(null),
    [creating, setCreating] = useState(
      !compact &&
        new URLSearchParams(window.location.search).get("new") === "1",
    ),
    [title, setTitle] = useState(""),
    [body, setBody] = useState(""),
    [category, setCategory] = useState("규정 문의"),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const items = query.data?.items ?? [],
    open = items.filter(
      (item) => !["resolved", "cancelled"].includes(item.state),
    ),
    filtered = items
      .filter((item) => filter === "all" || item.state === filter)
      .slice(0, compact ? 4 : 100);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await control("/api/control/cases", "POST", {
        title: title.trim(),
        body: body.trim(),
        category,
      });
      setCreating(false);
      setTitle("");
      setBody("");
      query.refresh();
      setNotice(
        "로컬 문의가 등록됐습니다. 실제 회사 접수·알림은 전송되지 않습니다.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "등록하지 못했습니다.",
      );
    } finally {
      setPending(false);
    }
  }
  async function cancel(item: CaseRecord) {
    setPending(true);
    setError("");
    try {
      await control(`/api/control/cases/${item.id}/cancel`, "POST", {});
      setSelected(null);
      query.refresh();
      setNotice("문의를 취소했습니다.");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "취소하지 못했습니다.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      {!compact && (
        <>
          <div className="emp-request-stats">
            <div>
              <span>진행 중</span>
              <strong>
                {open.length}
                <small>건</small>
              </strong>
            </div>
            <div>
              <span>추가 확인</span>
              <strong>
                {items.filter((i) => i.state === "awaiting_info").length}
                <small>건</small>
              </strong>
            </div>
            <div>
              <span>처리 완료</span>
              <strong>
                {items.filter((i) => i.state === "resolved").length}
                <small>건</small>
              </strong>
            </div>
            <button
              className="emp-primary"
              onClick={() => {
                setError("");
                setCreating(true);
              }}
            >
              <Plus size={17} />새 문의 등록
            </button>
          </div>
          <div className="emp-request-toolbar">
            <div>
              {[
                "all",
                "received",
                "in_review",
                "awaiting_info",
                "resolved",
              ].map((value) => (
                <button
                  key={value}
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                >
                  {value === "all" ? "전체" : CASE_STATES[value]}
                </button>
              ))}
            </div>
            <button onClick={query.refresh} aria-label="내 문의 새로고침">
              <RefreshCw size={15} />
            </button>
          </div>
        </>
      )}
      {(error || query.error) && (
        <p className="emp-error" role="alert">
          {error || query.error?.message}
        </p>
      )}
      {notice && (
        <p className="emp-notice" role="status">
          <Check size={15} />
          {notice}
          <button aria-label="문의 안내 닫기" onClick={() => setNotice("")}>
            <X size={13} />
          </button>
        </p>
      )}
      {query.loading && !query.data ? (
        <p className="emp-muted" role="status">
          내 문의를 불러오고 있어요.
        </p>
      ) : filtered.length ? (
        <div className="emp-case-list">
          {filtered.map((item) => (
            <button
              className="emp-case-row"
              key={item.id}
              onClick={() => {
                setError("");
                setSelected(item);
              }}
            >
              <span className="emp-case-icon">
                <MessageSquareText size={18} />
              </span>
              <div>
                <small>
                  {item.category} · {item.id}
                </small>
                <strong>{item.title}</strong>
                <span>{dateTime(item.updated_at)}</span>
              </div>
              <span className={"ops-badge " + item.state}>
                {CASE_STATES[item.state]}
              </span>
              <ChevronRight size={15} />
            </button>
          ))}
        </div>
      ) : (
        <div className="emp-empty">
          <Inbox size={30} />
          <h3>
            {filter === "all"
              ? "등록한 문의가 없습니다."
              : "이 상태의 문의가 없습니다."}
          </h3>
          <p>AI 답변으로 해결되지 않은 내용은 문의로 남겨보세요.</p>
          <button
            onClick={() =>
              compact ? navigate("/hr/requests?new=1") : setCreating(true)
            }
          >
            문의 작성하기
            <ArrowRight size={14} />
          </button>
        </div>
      )}
      {!compact && (
        <p className="emp-muted emp-request-limit">
          현재 체험 계정의 일반 문의만 보관합니다. 주민번호·연락처·진단 내용·키
          등은 입력하지 마세요. 회사의 실제 신청·결재와는 별도입니다.
        </p>
      )}
      {creating && (
        <WorkspaceDialog title="새 문의 등록" close={() => setCreating(false)}>
          <form className="emp-case-form" onSubmit={submit}>
            <p>
              문의는 로컬 체험 저장소에 등록됩니다. 실제 직원 정보나 민감한
              내용을 입력하지 마세요.
            </p>
            <label>
              문의 분야
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              >
                {["규정 문의", "양식 문의", "AI 답변 확인", "서비스 이용"].map(
                  (value) => (
                    <option key={value}>{value}</option>
                  ),
                )}
              </select>
            </label>
            <label>
              제목
              <input
                required
                minLength={2}
                maxLength={100}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="어떤 도움이 필요한가요?"
              />
            </label>
            <label>
              문의 내용
              <textarea
                required
                minLength={5}
                maxLength={1500}
                rows={6}
                value={body}
                onChange={(event) => setBody(event.target.value)}
                placeholder="확인할 규정이나 절차를 구체적으로 적어주세요."
              />
            </label>
            {error && (
              <p className="emp-error" role="alert">
                {error}
              </p>
            )}
            <footer>
              <span>실제 회사 접수·알림 미연결</span>
              <button
                className="emp-primary"
                disabled={
                  pending || title.trim().length < 2 || body.trim().length < 5
                }
              >
                <Send size={15} />
                {pending ? "등록 중…" : "로컬 문의 등록"}
              </button>
            </footer>
          </form>
        </WorkspaceDialog>
      )}
      {selected && (
        <WorkspaceDialog title="문의 상세" close={() => setSelected(null)}>
          <div className="emp-case-detail">
            <div>
              <span className={"ops-badge " + selected.state}>
                {CASE_STATES[selected.state]}
              </span>
              <small>
                {selected.id} · {selected.category}
              </small>
            </div>
            <h3>{selected.title}</h3>
            <p className="emp-case-body">{selected.body}</p>
            <div className="emp-timeline">
              <span>
                <Check size={13} />
              </span>
              <div>
                <strong>문의 등록</strong>
                <p>{dateTime(selected.created_at)}</p>
              </div>
            </div>
            <div className="emp-timeline">
              <span>
                <ClipboardList size={14} />
              </span>
              <div>
                <strong>{CASE_STATES[selected.state]}</strong>
                <p>{dateTime(selected.updated_at)}</p>
              </div>
            </div>
            {selected.reply && (
              <section className="emp-case-reply">
                <strong>처리 안내</strong>
                <p>{selected.reply}</p>
                <small>로컬 관리자 체험에서 작성된 안내입니다.</small>
              </section>
            )}
            {error && (
              <p className="emp-error" role="alert">
                {error}
              </p>
            )}
            <footer>
              {!["resolved", "cancelled"].includes(selected.state) && (
                <button
                  disabled={pending}
                  onClick={() => void cancel(selected)}
                >
                  문의 취소
                </button>
              )}
              <span>회사 신청·결재와 별도인 문의 체험입니다.</span>
            </footer>
          </div>
        </WorkspaceDialog>
      )}
    </>
  );
}
