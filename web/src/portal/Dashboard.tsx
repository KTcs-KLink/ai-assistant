import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileCheck2,
  Gift,
  Leaf,
  MessageSquare,
  Settings2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { EMPLOYMENT_LABEL, tenureYears } from "../workspace/model";
import { Badge, BenefitIcon, Modal, Note, SectionLink } from "./ui";

export function Dashboard() {
  const { benefits, profile, preparations, saved, select } = useWorkspace();
  const [quick, setQuick] = useState<
    "saved" | "profile" | "preparations" | null
  >(null);
  const eligible = benefits.filter((b) => b.status === "eligible");
  const review = benefits.filter((b) => b.status === "needs_review");
  const urgent = benefits
    .filter(
      (b) =>
        b.daysLeft !== null && b.daysLeft >= 0 && b.status !== "ineligible",
    )
    .sort((a, b) => a.daysLeft! - b.daysLeft!);
  const highlighted = eligible.length
    ? eligible.slice(0, 2)
    : review.slice(0, 2);
  return (
    <div className="p-dashboard">
      <section className="p-welcome">
        <div>
          <span className="p-welcome-date">
            2026.11.07 토요일 <i />
            가상 시연 기준일
          </span>
          <h1>
            반가워요, <strong>체험 직원님.</strong>
          </h1>
          <p>오늘의 업무와 나에게 필요한 혜택을 한눈에 확인하세요.</p>
        </div>
        <button
          className="p-welcome-profile"
          onClick={() => setQuick("profile")}
        >
          <span className="p-avatar large">K</span>
          <span>
            <small>MY WORK & LIFE</small>
            <strong>
              {profile.employment_type
                ? EMPLOYMENT_LABEL[profile.employment_type]
                : "조건 설정 전"}{" "}
              <i>·</i>{" "}
              {tenureYears(profile.hire_date) === null
                ? "근속 미확인"
                : `근속 ${tenureYears(profile.hire_date)}년`}
            </strong>
            <span>
              가상 조건 확인
              <ChevronRight size={13} />
            </span>
          </span>
        </button>
      </section>
      <section className="p-quickbar" aria-label="빠른 실행">
        <span className="p-quick-caption">
          빠른 실행<small>이 화면에서 바로</small>
        </span>
        <button onClick={() => select("family-leave")}>
          <span className="p-quick-icon sage">
            <Leaf size={21} />
          </span>
          <span>휴가 조건 확인</span>
          <ChevronRight size={15} />
        </button>
        <button onClick={() => setQuick("saved")}>
          <span className="p-quick-icon amber">
            <Bookmark size={20} />
          </span>
          <span>
            저장한 혜택<small>{saved.length}</small>
          </span>
          <ChevronRight size={15} />
        </button>
        <button onClick={() => setQuick("preparations")}>
          <span className="p-quick-icon blue">
            <FileCheck2 size={21} />
          </span>
          <span>
            준비 진행 확인<small>{preparations.length}</small>
          </span>
          <ChevronRight size={15} />
        </button>
        <button onClick={() => setQuick("profile")}>
          <span className="p-quick-icon rose">
            <Settings2 size={20} />
          </span>
          <span>내 추천 조건</span>
          <ChevronRight size={15} />
        </button>
      </section>
      <div className="p-dashboard-grid">
        <section className="p-dashboard-benefits">
          <div className="p-section-heading">
            <div>
              <span className="p-kicker">FOR YOU</span>
              <h2>나에게 맞는 혜택</h2>
            </div>
            <SectionLink to="/workspace/benefits">전체 보기</SectionLink>
          </div>
          <div className="p-status-summary">
            <Link to="/workspace/benefits?status=eligible">
              <span className="p-summary-icon">
                <CheckCircle2 size={17} />
              </span>
              <span>
                조건 충족 <b>{eligible.length}</b>
              </span>
              <ArrowUpRight size={16} />
            </Link>
            <Link to="/workspace/benefits?status=needs_review">
              <span className="p-summary-icon amber">
                <CircleHelpIcon />
              </span>
              <span>
                추가 확인 <b>{review.length}</b>
              </span>
              <ArrowUpRight size={16} />
            </Link>
            <span className="p-example-note">가상 규정 기준</span>
          </div>
          <div className="p-featured-benefits">
            {highlighted.map((benefit) => (
              <article key={benefit.id}>
                <div className="p-featured-top">
                  <BenefitIcon benefit={benefit} />
                  <Badge status={benefit.status} />
                </div>
                <span className="p-category">{benefit.category}</span>
                <h3>
                  <button onClick={() => select(benefit.id)}>
                    {benefit.title}
                    <ArrowUpRight size={18} />
                  </button>
                </h3>
                <strong className="p-featured-value">
                  {benefit.value}
                  <small>예시</small>
                </strong>
                <p>{benefit.reason}</p>
                <button
                  className="p-featured-footer"
                  onClick={() => select(benefit.id)}
                >
                  조건과 준비 살펴보기
                  <ArrowRight size={16} />
                </button>
              </article>
            ))}
          </div>
          <Note>
            동의한 가상 조건으로 살펴본 추천입니다. 실제 지급 자격은 회사 규정
            확인이 필요해요.
          </Note>
        </section>
        <aside className="p-attention">
          <div className="p-section-heading">
            <div>
              <span className="p-kicker">NEEDS ATTENTION</span>
              <h2>먼저 확인해 주세요</h2>
            </div>
            <span className="p-count">
              {urgent.length + (review.length ? 1 : 0)}
            </span>
          </div>
          <div className="p-task-list">
            {urgent.slice(0, 2).map((benefit) => (
              <button key={benefit.id} onClick={() => select(benefit.id)}>
                <span className="p-task-bullet">
                  <Clock3 size={18} />
                </span>
                <span>
                  <span className="p-task-tag">
                    D-{benefit.daysLeft} · 예시 일정
                  </span>
                  <strong>{benefit.title}</strong>
                  <small>
                    {benefit.deadline?.replaceAll("-", ".")}까지 확인
                  </small>
                </span>
                <ChevronRight size={16} />
              </button>
            ))}
            {review.length > 0 && (
              <Link to="/workspace/benefits?status=needs_review">
                <span className="p-task-bullet quiet">
                  <ShieldCheck size={18} />
                </span>
                <span>
                  <span className="p-task-tag quiet">추가 정보 확인</span>
                  <strong>확인하면 더 분명해져요</strong>
                  <small>재학·주거 등 미확인 조건 {review.length}건</small>
                </span>
                <ChevronRight size={16} />
              </Link>
            )}
          </div>
          <Link className="p-attention-footer" to="/workspace/preparations">
            <FileCheck2 size={16} />
            나의 준비 목록
            <span>
              {preparations.length}건<ChevronRight size={14} />
            </span>
          </Link>
        </aside>
        <section className="p-learning-banner">
          <div className="p-banner-lines" aria-hidden="true">
            <BookOpen size={96} strokeWidth={0.8} />
            <span />
          </div>
          <div>
            <span className="p-kicker">GROW AT YOUR OWN PACE</span>
            <h2>
              배우고 싶었던 것,
              <br />
              이번 달에 시작해 볼까요?
            </h2>
            <p>자기계발 지원의 조건과 준비할 내용을 살펴보세요.</p>
            <button onClick={() => select("learning")}>
              배움 지원 확인
              <ArrowUpRight size={17} />
            </button>
          </div>
          <span className="p-banner-label">가상 혜택 안내</span>
        </section>
        <section className="p-ai-launch">
          <span className="p-ai-symbol">
            <Sparkles size={24} />
          </span>
          <span className="p-kicker">YOUR WORK COMPANION</span>
          <h2>
            규정을 읽다가
            <br />
            궁금해졌다면
          </h2>
          <p>근거를 함께 보며 업무를 이해해요.</p>
          <Link to="/workspace/assistant">
            AI 업무 도우미
            <ArrowRight size={17} />
          </Link>
          <small>고정 예시 응답 · 외부 AI 미호출</small>
        </section>
      </div>
      <section className="p-resources">
        <div className="p-section-heading">
          <div>
            <span className="p-kicker">RESOURCES</span>
            <h2>필요한 자료, 빠르게 찾기</h2>
          </div>
          <SectionLink to="/workspace/library">자료실 전체</SectionLink>
        </div>
        <div className="p-resource-links">
          <Link to="/workspace/library?tab=rules&q=휴가">
            <Leaf size={21} />
            <span>
              <strong>휴가·휴직 규정</strong>
              <small>기간과 조건부터 확인</small>
            </span>
            <ArrowUpRight size={17} />
          </Link>
          <Link to="/workspace/library?tab=forms&q=출장">
            <FileCheck2 size={21} />
            <span>
              <strong>출장·정산 양식</strong>
              <small>준비할 항목 살펴보기</small>
            </span>
            <ArrowUpRight size={17} />
          </Link>
          <Link to="/workspace/library?tab=forms&q=퇴직">
            <BookOpen size={21} />
            <span>
              <strong>입사·퇴직 자료</strong>
              <small>필요한 양식 찾기</small>
            </span>
            <ArrowUpRight size={17} />
          </Link>
        </div>
      </section>
      {quick && (
        <Modal
          title={
            {
              saved: "저장한 혜택",
              profile: "내 추천 조건",
              preparations: "현재 준비 중인 항목",
            }[quick]
          }
          close={() => setQuick(null)}
        >
          <div className="p-modal-body">
            {quick === "profile" ? (
              <>
                <dl className="p-meta">
                  <div>
                    <dt>근무 정보 활용</dt>
                    <dd>
                      {profile.employment_consent
                        ? "가상 동의 · 고용형태·입사일"
                        : "동의 전 · 미사용"}
                    </dd>
                  </div>
                  <div>
                    <dt>가족 정보 활용</dt>
                    <dd>
                      {profile.family_consent
                        ? "가상 동의 · 자녀 나이·가구원 수"
                        : "동의 전 · 미사용"}
                    </dd>
                  </div>
                </dl>
                <Note>
                  실제 개인정보를 입력하지 않는 예시 조건입니다. 동의한 항목만
                  추천에 사용하며 언제든 철회할 수 있어요.
                </Note>
                <Link
                  className="p-button"
                  to="/workspace/profile"
                  onClick={() => setQuick(null)}
                >
                  추천 조건·동의 관리
                  <ArrowRight size={16} />
                </Link>
              </>
            ) : (
              <>
                {benefits
                  .filter((b) =>
                    quick === "saved"
                      ? saved.includes(b.id)
                      : preparations.some((p) => p.benefitId === b.id),
                  )
                  .map((b) => (
                    <button
                      className="p-quick-result"
                      key={b.id}
                      onClick={() => {
                        setQuick(null);
                        select(b.id);
                      }}
                    >
                      <BenefitIcon benefit={b} />
                      <strong>{b.title}</strong>
                      <ChevronRight size={17} />
                    </button>
                  ))}
                {(quick === "saved" ? saved.length : preparations.length) ===
                  0 && (
                  <div className="p-empty-compact">
                    <Gift size={30} />
                    <h3>아직 담은 항목이 없어요</h3>
                    <p>혜택 상세에서 저장하거나 준비 목록에 담아보세요.</p>
                  </div>
                )}
                <Link
                  className="p-button p-secondary"
                  to={
                    quick === "saved"
                      ? "/workspace/benefits?status=saved"
                      : "/workspace/preparations"
                  }
                  onClick={() => setQuick(null)}
                >
                  목록으로 이동
                  <ArrowRight size={16} />
                </Link>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
function CircleHelpIcon() {
  return <MessageSquare size={17} />;
}
