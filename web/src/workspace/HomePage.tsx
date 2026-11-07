import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileCheck2,
  Gift,
  Heart,
  MessageSquare,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
} from 'lucide-react'
import { useWorkspace } from './WorkspaceContext'
import { BenefitCard, BenefitIcon, SectionTitle, StatusBadge } from './components'
import { EMPLOYMENT_LABEL, tenureYears } from './model'

export function HomePage() {
  const { benefits, preparations, profile, select } = useWorkspace()
  const eligible = benefits.filter((b) => b.status === 'eligible'),
    review = benefits.filter((b) => b.status === 'needs_review')
  const urgent = benefits
    .filter((b) => b.daysLeft !== null && b.daysLeft >= 0 && b.status !== 'ineligible')
    .sort((a, b) => a.daysLeft! - b.daysLeft!)
  return (
    <div className="kl-home">
      <div className="kl-home-greeting">
        <div>
          <div className="kl-home-date">
            <span />
            2026년 11월 7일 토요일 · 예시 기준일
          </div>
          <h1>
            나에게 필요한 일,
            <br className="kl-mobile-break" /> 오늘도 K:LINK와 함께.
          </h1>
          <p>놓치기 쉬운 혜택과 궁금했던 업무를 한곳에서 확인하세요.</p>
        </div>
        <Link className="kl-subtle-button" to="/workspace/profile">
          <SlidersHorizontal size={15} />
          추천 조건 확인
        </Link>
      </div>
      <div className="kl-home-hero-row">
        <section className="kl-home-hero">
          <div>
            <span className="kl-eyebrow">A LITTLE MORE, JUST FOR YOU</span>
            <h2>
              몰랐던 혜택까지,
              <br />
              나에게 맞게 챙겨드려요.
            </h2>
            <p>나의 조건으로 살펴본 복지·휴가·지원 혜택</p>
            <Link className="kl-hero-button" to="/workspace/benefits">
              나의 혜택 확인하기
              <ArrowRight size={16} />
            </Link>
          </div>
          <div className="kl-hero-visual" aria-hidden="true">
            <div className="kl-hero-orbit" />
            <div className="kl-floating-mini">
              <Heart size={24} />
              <span>나와 가족을 위한</span>
            </div>
            <div className="kl-floating-main">
              <span>
                <Gift size={31} />
              </span>
              <strong>나의 맞춤 혜택</strong>
              <div>
                <i />
                <i />
              </div>
              <b>
                <CheckCircle2 size={18} />
              </b>
            </div>
            <Sparkles className="kl-hero-spark" size={24} />
          </div>
        </section>
        <section className="kl-home-ai">
          <span className="kl-home-ai-icon">
            <Sparkles size={23} />
          </span>
          <span className="kl-eyebrow">AI ASSISTANT</span>
          <h2>
            규정이 어려울 땐,
            <br />
            편하게 물어보세요.
          </h2>
          <p>근거를 확인하며 업무를 이해해요.</p>
          <Link to="/workspace/assistant">
            AI와 대화하기
            <ArrowRight size={16} />
          </Link>
        </section>
      </div>
      <section className="kl-overview-stats" aria-label="나의 혜택 요약">
        <Link to="/workspace/benefits?status=eligible">
          <span className="kl-stat-icon green">
            <Gift size={20} />
          </span>
          <span>
            <small>
              조건에 맞는 혜택 <i>예시</i>
            </small>
            <strong>
              {eligible.length}
              <em>건</em>
            </strong>
          </span>
          <ChevronRight size={16} />
        </Link>
        <Link to="/workspace/benefits?status=needs_review">
          <span className="kl-stat-icon amber">
            <ShieldCheck size={20} />
          </span>
          <span>
            <small>추가로 확인할 혜택</small>
            <strong>
              {review.length}
              <em>건</em>
            </strong>
          </span>
          <ChevronRight size={16} />
        </Link>
        <Link to="/workspace/preparations">
          <span className="kl-stat-icon blue">
            <FileCheck2 size={20} />
          </span>
          <span>
            <small>내가 준비 중인 신청</small>
            <strong>
              {preparations.length}
              <em>건</em>
            </strong>
          </span>
          <ChevronRight size={16} />
        </Link>
      </section>
      <section className="kl-home-recommend">
        <SectionTitle title="지금 나에게 맞는 혜택" count={eligible.length}>
          <Link className="kl-text-link" to="/workspace/benefits">
            전체 혜택 보기
            <ChevronRight size={15} />
          </Link>
        </SectionTitle>
        <p className="kl-section-description">예시 조건에 맞는 혜택부터 먼저 살펴보세요.</p>
        {eligible.length ? (
          <div className="kl-benefit-grid home">
            {eligible.slice(0, 3).map((b) => (
              <BenefitCard key={b.id} benefit={b} />
            ))}
          </div>
        ) : (
          <div className="kl-home-consent">
            <ShieldCheck size={23} />
            <div>
              <strong>추천 조건을 알려주시면 더 잘 찾아드릴 수 있어요.</strong>
              <p>동의한 근무·가족 정보만 사용해요.</p>
            </div>
            <Link className="kl-button secondary" to="/workspace/profile">
              추천 조건 설정
              <ArrowRight size={15} />
            </Link>
          </div>
        )}
      </section>
      <div className="kl-home-bottom">
        <section className="kl-panel kl-deadlines">
          <SectionTitle title="놓치기 전에 확인하세요">
            <span className="kl-caption">예시 일정</span>
          </SectionTitle>
          {urgent.length ? (
            urgent.slice(0, 2).map((b) => (
              <button key={b.id} className="kl-deadline-row" onClick={() => select(b.id)}>
                <span className="kl-deadline-date">
                  <strong>{b.deadline?.slice(8)}</strong>
                  <small>11월</small>
                </span>
                <div>
                  <strong>{b.title}</strong>
                  <span>
                    {b.deadline?.replaceAll('-', '.')}까지 · {b.value}
                  </span>
                </div>
                <span className="kl-due-pill">D-{b.daysLeft}</span>
                <ChevronRight size={15} />
              </button>
            ))
          ) : (
            <p className="kl-caption">현재 예시 조건에서 마감 예정인 혜택이 없어요.</p>
          )}
          <div className="kl-deadline-note">
            <Clock3 size={13} />
            실제 회사 신청 일정은 연결 후 확인할 수 있어요.
          </div>
        </section>
        <section className="kl-panel kl-profile-summary">
          <SectionTitle title="추천에 사용한 내 조건">
            <Link aria-label="내 추천 조건 수정" className="kl-icon-button" to="/workspace/profile">
              <SlidersHorizontal size={17} />
            </Link>
          </SectionTitle>
          <div className="kl-condition-chips">
            {profile.employment_type && <span>{EMPLOYMENT_LABEL[profile.employment_type]}</span>}
            {profile.hire_date && <span>근속 {tenureYears(profile.hire_date)}년</span>}
            {profile.children_ages !== null && (
              <span>
                {profile.children_ages.length
                  ? `자녀 ${profile.children_ages.length}명`
                  : '자녀 없음'}
              </span>
            )}
            {profile.household_size && <span>{profile.household_size}인 가구</span>}
            {!profile.employment_consent && !profile.family_consent && (
              <span>제공한 정보 없음</span>
            )}
          </div>
          <p>
            근무 조건이나 가족 구성이 달라졌다면
            <br />
            추천 조건도 함께 확인해 주세요.
          </p>
          <Link className="kl-text-link" to="/workspace/profile">
            정보·동의 관리
            <ArrowRight size={15} />
          </Link>
        </section>
      </div>
      <section className="kl-home-quickwork">
        <SectionTitle title="자주 찾는 업무" />
        <div>
          {[
            {
              to: '/workspace/library?q=휴가',
              icon: FileCheck2,
              title: '휴가 신청 준비',
              text: '조건과 필요한 양식 확인',
            },
            {
              to: '/workspace/library?q=출장',
              icon: BookOpen,
              title: '출장·정산 안내',
              text: '사전 품의부터 정산까지',
            },
            {
              to: '/workspace/assistant',
              icon: MessageSquare,
              title: '궁금한 규정 물어보기',
              text: '근거와 함께 쉽게 이해',
            },
          ].map(({ to, icon: Icon, title, text }) => (
            <Link key={title} to={to}>
              <span>
                <Icon size={21} />
              </span>
              <div>
                <strong>{title}</strong>
                <small>{text}</small>
              </div>
              <ChevronRight size={16} />
            </Link>
          ))}
        </div>
      </section>
      {review.length > 0 && (
        <section className="kl-review-strip">
          <div>
            <ShieldCheck size={21} />
            <span>
              <strong>조금 더 확인하면 좋은 혜택이 있어요</strong>
              <small>필수 조건이 부족한 혜택은 확정해서 안내하지 않아요.</small>
            </span>
          </div>
          <div>
            {review.slice(0, 2).map((b) => (
              <button key={b.id} onClick={() => select(b.id)}>
                <BenefitIcon benefit={b} size={18} />
                <span>{b.title}</span>
                <StatusBadge status={b.status} short />
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
