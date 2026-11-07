import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileCheck2,
  Gift,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Wallet,
} from "lucide-react";
import { useHr } from "./HrContext";
import { attempt } from "./ui";
import "./home.css";

const SHORTCUTS = [
  {
    title: "휴가·근태",
    description: "휴가와 근무 기준 찾기",
    to: "/hr/library?tab=rules&q=휴가",
    icon: CalendarDays,
  },
  {
    title: "급여·수당",
    description: "지급일과 보수 규정 찾기",
    to: "/hr/library?tab=rules&q=급여",
    icon: Wallet,
  },
  {
    title: "양식·증빙",
    description: "필요한 서류 준비 안내",
    to: "/hr/library?tab=forms",
    icon: FileCheck2,
  },
  {
    title: "내 조건·동의",
    description: "직접 제공한 조건 관리",
    to: "/hr/profile",
    icon: Settings2,
  },
];
const QUESTIONS = [
  {
    topic: "휴가·증빙",
    question: "병가 때 진단서는 언제 제출해야 하나요?",
    icon: FileCheck2,
  },
  { topic: "급여", question: "정기 급여 지급일은 언제인가요?", icon: Wallet },
  {
    topic: "근무시간",
    question: "업무 사정으로 휴게시간을 바꿀 수 있나요?",
    icon: Clock3,
  },
];

export function HrHome() {
  const {
    session,
    plans,
    catalog,
    profile,
    readiness,
    updates,
    busy,
    reminders,
    refresh,
  } = useHr();
  const [question, setQuestion] = useState("");
  const navigate = useNavigate();
  const research = readiness?.research;
  const referenceAvailable =
    research?.company === "KEPCO" && research.source_count > 0;
  const exampleSession = session?.mode === "demo";
  const today = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date());
  function openDraft(text: string) {
    const draftQuestion = text.trim();
    if (draftQuestion.length < 2 || draftQuestion.length > 500) return;
    navigate("/hr/assistant", { state: { draftQuestion } });
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    openDraft(question);
  }
  return (
    <div className="hr-home">
      <header className="hr-home-welcome">
        <div>
          <span className="hr-home-eyebrow">MY WORKSPACE</span>
          <h1>오늘의 업무, 여기서 시작하세요.</h1>
          <p>궁금한 규정을 확인하고, 준비 중인 일을 이어가세요.</p>
        </div>
        <span className="hr-home-date">
          <CalendarDays size={16} />
          {today}
        </span>
      </header>

      <div className="hr-home-start">
        <section className="hr-home-hero" aria-labelledby="hr-home-ai-title">
          <div className="hr-home-hero-heading">
            <span>
              <Sparkles size={16} /> K:LINK AI 업무 도우미
            </span>
            <span className="hr-home-reference">
              {referenceAvailable ? "한전 원문 기반" : "연결 확인 필요"}
            </span>
          </div>
          <h2 id="hr-home-ai-title">
            찾기 어려운 규정,
            <br />
            K:LINK에 물어보세요.
          </h2>
          <p>답변의 근거가 된 원문과 조건을 함께 확인할 수 있어요.</p>
          <form
            className="hr-home-question"
            onSubmit={submit}
            aria-label="홈 인사 질문 작성"
          >
            <label className="p-sr-only" htmlFor="hr-home-question">
              궁금한 인사 질문
            </label>
            <textarea
              id="hr-home-question"
              rows={2}
              maxLength={500}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="어떤 인사 업무가 궁금하세요?"
            />
            <div>
              <span>{question.length}/500</span>
              <button type="submit" disabled={question.trim().length < 2}>
                AI 도우미로 이동
                <ArrowUpRight size={17} />
              </button>
            </div>
          </form>
          <div className="hr-home-question-hint">
            <ShieldCheck size={13} />
            <span>
              개인정보는 입력하지 마세요. 이동 후 질문을 확인하고 전송할 수
              있어요.
            </span>
          </div>
          <div className="hr-home-suggestions" aria-label="질문 작성 바로가기">
            <span>이렇게 물어보세요</span>
            {QUESTIONS.slice(0, 2).map((item) => (
              <button key={item.topic} onClick={() => openDraft(item.question)}>
                {item.topic}
                <ChevronRight size={13} />
              </button>
            ))}
          </div>
        </section>

        <section
          className="hr-home-queue"
          aria-labelledby="hr-home-queue-title"
        >
          <header>
            <div>
              <span className="hr-home-eyebrow">
                PICK UP WHERE YOU LEFT OFF
              </span>
              <h2 id="hr-home-queue-title">
                내 준비 목록 <span>{plans ? plans.length : "—"}</span>
              </h2>
            </div>
            <FileCheck2 size={22} />
          </header>
          <span className="hr-home-caption">
            {exampleSession
              ? "예시 직원의 준비 현황"
              : "현재 접속 계정의 준비 현황"}
          </span>
          {plans === null ? (
            <div className="hr-home-empty">
              <CircleHelp size={27} />
              <strong>준비 목록을 불러오지 못했어요</strong>
              <button className="p-text-link" onClick={() => void refresh()}>
                다시 조회
                <ArrowRight size={14} />
              </button>
            </div>
          ) : plans.length ? (
            <ul className="hr-home-plan-list">
              {plans.slice(0, 3).map((plan) => (
                <li key={plan.id}>
                  <Link to="/hr/preparations">
                    <span
                      className={
                        "hr-home-plan-icon" + (plan.stale ? " stale" : "")
                      }
                    >
                      <FileCheck2 size={18} />
                    </span>
                    <div>
                      <strong>{plan.title}</strong>
                      <small>
                        {plan.stale
                          ? "조건·규정 재확인 필요"
                          : `${plan.checked.length}/${plan.checklist.length}개 준비 항목 확인`}
                      </small>
                    </div>
                    <ChevronRight size={15} />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className="hr-home-empty">
              <span className="hr-home-empty-icon">
                <Check size={26} />
              </span>
              <strong>진행 중인 준비가 없어요.</strong>
              <p>
                준비할 항목을 담으면
                <br />
                이곳에서 이어갈 수 있어요.
              </p>
            </div>
          )}
          <footer>
            <p>실제 신청·결재는 연결 전입니다.</p>
            <Link to="/hr/preparations">
              준비 목록 보기
              <ArrowRight size={15} />
            </Link>
          </footer>
        </section>
      </div>

      <nav className="hr-home-shortcuts" aria-label="업무 빠른 실행">
        {SHORTCUTS.map(({ title, description, to, icon: Icon }) => (
          <Link key={title} to={to}>
            <span className="hr-home-shortcut-icon">
              <Icon size={23} />
            </span>
            <div>
              <strong>{title}</strong>
              <small>{description}</small>
            </div>
            <ArrowUpRight size={16} />
          </Link>
        ))}
      </nav>

      <div className="hr-home-content">
        <section
          className="hr-home-topics"
          aria-labelledby="hr-home-topics-title"
        >
          <header className="hr-home-section-heading">
            <div>
              <span className="hr-home-eyebrow">START WITH A QUESTION</span>
              <h2 id="hr-home-topics-title">이런 업무가 궁금하다면</h2>
            </div>
            <Link to="/hr/library?tab=rules">
              원문 직접 찾기
              <Search size={15} />
            </Link>
          </header>
          <div className="hr-home-topic-list">
            {QUESTIONS.map(({ topic, question: text, icon: Icon }, index) => (
              <button key={topic} onClick={() => openDraft(text)}>
                <span className="hr-home-topic-number">0{index + 1}</span>
                <Icon size={20} />
                <div>
                  <small>{topic} · 한전 참고자료</small>
                  <strong>{text}</strong>
                </div>
                <ArrowUpRight size={17} />
              </button>
            ))}
          </div>
          <p className="hr-home-footnote">
            <BookOpen size={14} />
            질문을 선택하면 AI 도우미의 작성창으로 이어집니다.
          </p>
        </section>

        <aside className="hr-home-trust" aria-labelledby="hr-home-trust-title">
          <header className="hr-home-section-heading">
            <div>
              <span className="hr-home-eyebrow">KNOW YOUR SOURCES</span>
              <h2 id="hr-home-trust-title">지금 연결된 범위</h2>
            </div>
            <ShieldCheck size={22} />
          </header>
          <Link className="hr-home-source" to="/hr/library?tab=rules">
            <span
              className={
                "hr-home-source-dot" + (referenceAvailable ? " live" : "")
              }
            />
            <div>
              <strong>한국전력 공개 원문</strong>
              <small>
                {referenceAvailable
                  ? `${research.source_count}개 조문 · ${research.document_count}개 문서`
                  : "원문 연결 확인 필요"}
              </small>
            </div>
            <span className="hr-home-state">
              {referenceAvailable ? "조회 가능" : "확인 필요"}
            </span>
          </Link>
          <p>한전 참고자료의 KTcs 적용과 현행성은 확인이 필요해요.</p>
          <dl>
            <div>
              <dt>KTcs 승인 규정</dt>
              <dd>
                {readiness
                  ? `${readiness.approved_policy_count}건 · 적용 확인 필요`
                  : "미확인"}
              </dd>
            </div>
            <div>
              <dt>공식 양식</dt>
              <dd>
                {readiness
                  ? readiness.official_form_count
                    ? `${readiness.official_form_count}건 · 권한 확인 필요`
                    : "미연결"
                  : "미확인"}
              </dd>
            </div>
            <div>
              <dt>회사 계정·SSO</dt>
              <dd>미연결</dd>
            </div>
          </dl>
          <Link className="hr-home-trust-link" to="/hr/status">
            연결 상태 자세히 보기
            <ArrowRight size={15} />
          </Link>
        </aside>
      </div>

      <div className="hr-home-supporting">
        <section className="hr-home-benefits">
          <span className="hr-home-shortcut-icon">
            <Gift size={24} />
          </span>
          <div>
            <h2>
              맞춤 혜택 살펴보기{" "}
              <span className="hr-home-example">
                {catalog
                  ? catalog.synthetic
                    ? "예시 카탈로그"
                    : "자격 확인 필요"
                  : "조회 확인 필요"}
              </span>
            </h2>
            <p>
              {catalog?.synthetic
                ? "예시 직원 조건으로 기능을 체험할 수 있어요. 실제 KTcs 혜택·자격은 확인 전입니다."
                : catalog
                  ? "제공한 조건과 근거를 살펴보세요. 최종 자격과 회사 적용은 별도 확인이 필요해요."
                  : "추천을 불러오지 못했어요. AI 질문과 원문 검색은 계속 이용할 수 있어요."}
            </p>
            <small>
              {profile?.employment_consent
                ? "제공한 근무 조건 활용에 동의한 상태"
                : "근무 조건 활용 동의 전"}
            </small>
          </div>
          <Link to="/hr/benefits" aria-label="맞춤 혜택 살펴보기">
            <ArrowRight size={19} />
          </Link>
        </section>
        <details className="hr-home-updates">
          <summary>
            <Clock3 size={19} />
            <div>
              <strong>변경·마감 안내 설정</strong>
              <small>
                {updates?.enabled
                  ? "이 화면의 안내 사용 중"
                  : "원할 때 켜고 끌 수 있어요"}
              </small>
            </div>
            <ChevronRight size={17} />
          </summary>
          <div>
            {updates ? (
              <>
                <label className="hr-native-check">
                  <input
                    type="checkbox"
                    checked={updates.enabled}
                    disabled={busy}
                    onChange={(event) =>
                      void attempt(reminders(event.target.checked))
                    }
                  />
                  <span>이 화면에서 변경·마감 안내 받기</span>
                </label>
                {updates.enabled && (
                  <ul>
                    {updates.updates.length ? (
                      updates.updates.map((item, index) => (
                        <li key={item.benefit_id + index}>
                          <Link
                            to={
                              "/hr/benefits?benefit=" +
                              encodeURIComponent(item.benefit_id)
                            }
                          >
                            {updates.synthetic && (
                              <span className="hr-home-example">
                                예시 규정 일정
                              </span>
                            )}
                            <p>{item.message}</p>
                            <ChevronRight size={14} />
                          </Link>
                        </li>
                      ))
                    ) : (
                      <li>현재 표시할 변경·마감이 없어요.</li>
                    )}
                  </ul>
                )}
                <p>
                  화면 안의 안내입니다. 메일·문자·회사 알림은 발송하지 않아요.
                </p>
              </>
            ) : (
              <p>변경 안내를 불러오지 못했어요.</p>
            )}
          </div>
        </details>
      </div>
      <Link className="hr-home-previous" to="/hr/home-previous">
        이전 홈 구성 보기
        <ArrowUpRight size={13} />
      </Link>
    </div>
  );
}
