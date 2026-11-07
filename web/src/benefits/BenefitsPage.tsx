import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowDownToLine,
  ArrowRight,
  Award,
  Bookmark,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Gift,
  GraduationCap,
  Heart,
  Home,
  Info,
  Leaf,
  LogOut,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from 'lucide-react'
import {
  benefitRequest,
  BenefitsError,
  type Config,
  type Evidence,
  type Profile,
  type Recommendations,
  type Session,
  type Status,
} from './api'
import './benefits.css'

const LABEL: Record<Status, string> = {
  eligible: '자격 충족',
  needs_review: '추가 확인 필요',
  ineligible: '해당 없음',
}
const EMPTY: Profile = {
  employment_consent: false,
  family_consent: false,
  hire_date: null,
  employment_type: null,
  children_ages: null,
  household_size: null,
}
const ICONS: Record<string, typeof Heart> = {
  family: Heart,
  leave: Leaf,
  learning: BookOpen,
  award: Award,
  school: GraduationCap,
  home: Home,
}
type Filter = 'all' | Status | 'saved'

function Dialog({
  title,
  children,
  close,
}: {
  title: string
  children: ReactNode
  close: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    ref.current?.showModal()
    const dialog = ref.current
    return () => dialog?.close()
  }, [])
  return (
    <dialog
      ref={ref}
      className="benefit-dialog"
      onCancel={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) close()
      }}
      aria-labelledby="benefit-dialog-title"
    >
      <header>
        <h2 id="benefit-dialog-title">{title}</h2>
        <button className="icon-button" aria-label="닫기" onClick={close}>
          <X size={20} />
        </button>
      </header>
      <div className="dialog-body">{children}</div>
    </dialog>
  )
}

export function BenefitsPage() {
  const [config, setConfig] = useState<Config | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState<Profile>(EMPTY)
  const [data, setData] = useState<Recommendations | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [category, setCategory] = useState('전체 분야')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [profileOpen, setProfileOpen] = useState(false)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [loginOpen, setLoginOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  async function refresh() {
    const [p, d] = await Promise.all([
      benefitRequest<Profile>('/profile'),
      benefitRequest<Recommendations>('/recommendations'),
    ])
    setProfile(p)
    setData(d)
  }
  useEffect(() => {
    let active = true
    Promise.all([
      benefitRequest<Config>('/config'),
      benefitRequest<Session>('/session').catch((e) => {
        if (e instanceof BenefitsError && e.status === 401) return null
        throw e
      }),
    ])
      .then(async ([c, s]) => {
        if (!active) return
        setConfig(c)
        setSession(s)
        if (s) await refresh()
      })
      .catch(() => {
        if (active)
          setError(
            '혜택 서버에 연결하지 못했어요. 서버 실행 후 다시 시도해 주세요.',
          )
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  async function act(work: () => Promise<void>) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await work()
    } catch (e) {
      setError(e instanceof Error ? e.message : '다시 시도해 주세요.')
      if (e instanceof BenefitsError && e.status === 401) {
        setSession(null)
        setData(null)
        setProfile(EMPTY)
        setSelected(null)
        setProfileOpen(false)
      }
    } finally {
      setBusy(false)
    }
  }
  async function startDemo() {
    await act(async () => {
      const s = await benefitRequest<Session>('/session/demo', 'POST')
      setSession(s)
      await benefitRequest('/profile/example', 'POST')
      await refresh()
    })
  }
  async function login(e: FormEvent) {
    e.preventDefault()
    await act(async () => {
      const s = await benefitRequest<Session>('/session/login', 'POST', {
        email,
        password,
      })
      setPassword('')
      setEmail('')
      setSession(s)
      setLoginOpen(false)
      await refresh()
    })
    setPassword('')
  }
  const cards = data?.cards ?? []
  const activeCard = cards.find((c) => c.id === selected)
  const shown = cards.filter(
    (c) =>
      (filter === 'all' ||
        (filter === 'saved' ? c.saved : c.status === filter)) &&
      (category === '전체 분야' || c.category === category) &&
      `${c.title} ${c.description} ${c.category}`.includes(query.trim()),
  )
  const demo = session?.mode === 'demo'

  return (
    <div className="benefits-app">
      <a className="skip-link" href="#benefits-main">
        본문으로 건너뛰기
      </a>
      <header className="benefits-header">
        <div className="benefits-header-inner">
          <Link to="/benefits" className="benefits-logo">
            <span>
              <Sparkles size={21} />
            </span>
            K:LINK <small>WORK & LIFE</small>
          </Link>
          <nav aria-label="주요 메뉴">
            <Link to="/benefits" className="active">
              나의 혜택
            </Link>
            <button onClick={() => setEvidenceOpen(true)}>규정 찾아보기</button>
            <Link to="/">
              AI 대화 <ArrowRight size={14} />
            </Link>
          </nav>
          <div className="header-account">
            <span className="demo-pill">
              {session ? (demo ? '예시 체험' : '직원 로그인') : 'PREVIEW'}
            </span>
            {session && (
              <button
                aria-label="로그아웃"
                className="icon-button"
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await benefitRequest('/session', 'DELETE')
                    setSession(null)
                    setData(null)
                    setProfile(EMPTY)
                  })
                }
              >
                <LogOut size={17} />
              </button>
            )}
          </div>
        </div>
      </header>
      <main id="benefits-main" className="benefits-main">
        <div className="benefits-breadcrumb">
          홈 <ChevronRight size={12} /> 나의 혜택
        </div>
        <div className="benefits-heading">
          <div>
            <div className="eyebrow">
              <span /> EVERYDAY, A LITTLE BETTER
            </div>
            <h1>
              나를 위한 혜택,
              <br />
              빠짐없이 챙겨요<span>.</span>
            </h1>
            <p>나의 조건에 맞는 복지와 휴가를 한곳에서 확인하세요.</p>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="art-orbit" />
            <div className="art-card back">
              <Heart size={28} />
              <span />
            </div>
            <div className="art-card front">
              <Gift size={48} strokeWidth={1.4} />
              <div>
                <i />
                <i />
              </div>
              <span className="art-check">
                <Check size={20} />
              </span>
            </div>
            <Sparkles className="art-spark" size={24} />
          </div>
        </div>
        <div className="evidence-notice">
          <ShieldCheck size={18} />
          <p>
            <strong>현재는 가상 직원·가상 규정으로 체험하는 화면입니다.</strong>{' '}
            카드의 금액·조건·일정은 예시이며, 실제 KTcs의 지급·휴가 자격을
            검증한 결과가 아닙니다.
          </p>
        </div>
        {error && (
          <div className="benefit-error" role="alert">
            {error}{' '}
            <button onClick={() => window.location.reload()}>새로고침</button>
          </div>
        )}
        {notice && (
          <div className="benefit-notice" role="status">
            {notice}
          </div>
        )}
        {loading ? (
          <div className="benefit-loading" role="status">
            나의 혜택을 준비하고 있어요…
          </div>
        ) : !session ? (
          <section className="benefit-welcome">
            <div className="welcome-icon">
              <Gift size={30} />
            </div>
            <h2>어떤 혜택이 나에게 맞을까요?</h2>
            <p>
              가상 직원의 조건으로 추천 흐름을 살펴보세요.
              <br />
              실제 개인정보를 입력하지 않아도 체험할 수 있어요.
            </p>
            <button
              className="primary-button"
              disabled={busy || !config?.demo_enabled}
              onClick={startDemo}
            >
              예시 조건으로 둘러보기 <ArrowRight size={17} />
            </button>
            <button className="text-button" onClick={() => setLoginOpen(true)}>
              직원 계정으로 로그인
            </button>
            <small>
              예시: 2019년 입사 · 정규직 · 만 5세·9세 자녀 · 4인 가구
            </small>
          </section>
        ) : (
          <div className="benefits-columns">
            <div className="benefits-content">
              <section className="benefit-summary" aria-label="혜택 판정 요약">
                <div>
                  <span className="section-eyebrow">MY BENEFITS</span>
                  <h2>{demo ? '가상 직원' : session.name}의 맞춤 혜택</h2>
                  <p>
                    {demo
                      ? '예시 조건을 바꾸면 추천 결과도 달라져요.'
                      : '회사 규정 검증이 완료되기 전에는 자격을 확정하지 않아요.'}
                  </p>
                </div>
                <div className="summary-counts">
                  {(['eligible', 'needs_review', 'ineligible'] as Status[]).map(
                    (s) => (
                      <button
                        key={s}
                        onClick={() => setFilter(s)}
                        className={s}
                      >
                        <strong>
                          {data?.counts[s] ?? 0}
                          <small>건</small>
                        </strong>
                        <span>
                          {LABEL[s]}
                          {demo && ' (예시)'}
                        </span>
                      </button>
                    ),
                  )}
                </div>
              </section>
              <div className="benefit-toolbar">
                <h2>
                  놓치지 말아야 할 혜택 <span>{shown.length}</span>
                </h2>
                <select
                  aria-label="혜택 분야"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  {[
                    '전체 분야',
                    '가족·육아',
                    '휴가·휴직',
                    '성장·자기계발',
                    '수당·지원',
                  ].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div
                className="benefit-filters"
                role="group"
                aria-label="혜택 상태 필터"
              >
                {(
                  [
                    ['all', '전체'],
                    ['eligible', '자격 충족'],
                    ['needs_review', '추가 확인'],
                    ['ineligible', '해당 없음'],
                    ['saved', '저장한 혜택'],
                  ] as [Filter, string][]
                ).map(([key, label]) => (
                  <button
                    key={key}
                    aria-pressed={filter === key}
                    className={filter === key ? 'selected' : ''}
                    onClick={() => setFilter(key)}
                  >
                    {label}
                    {key === 'saved' && <Bookmark size={12} />}
                  </button>
                ))}
              </div>
              <label className="benefit-search">
                <Search size={17} />
                <input
                  placeholder="혜택 이름이나 관심 주제로 찾아보세요"
                  aria-label="혜택 검색"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                {query && (
                  <button
                    className="icon-button"
                    aria-label="검색 지우기"
                    onClick={() => setQuery('')}
                  >
                    <X size={15} />
                  </button>
                )}
              </label>
              <div className="benefit-grid" aria-live="polite">
                {shown.map((card) => {
                  const Icon = ICONS[card.icon] || Gift
                  return (
                    <article
                      className={`benefit-card ${card.status}`}
                      key={card.id}
                    >
                      <div className="card-top">
                        <span className={`benefit-icon ${card.icon}`}>
                          <Icon size={24} strokeWidth={1.6} />
                        </span>
                        <span className={`status-pill ${card.status}`}>
                          {card.status === 'eligible' ? (
                            <CheckCircle2 size={12} />
                          ) : card.status === 'needs_review' ? (
                            <Info size={12} />
                          ) : null}
                          {LABEL[card.status]}
                          {demo && ' · 예시'}
                        </span>
                        <button
                          className={`icon-button save-button ${card.saved ? 'saved' : ''}`}
                          aria-label={`${card.title} ${card.saved ? '저장 취소' : '저장'}`}
                          aria-pressed={card.saved}
                          disabled={busy}
                          onClick={() =>
                            act(async () => {
                              await benefitRequest(
                                `/${card.id}/bookmark`,
                                'PUT',
                                { saved: !card.saved },
                              )
                              await refresh()
                            })
                          }
                        >
                          <Bookmark
                            size={18}
                            fill={card.saved ? 'currentColor' : 'none'}
                          />
                        </button>
                      </div>
                      <span className="card-category">{card.category}</span>
                      <h3>{card.title}</h3>
                      <p className="card-description">{card.description}</p>
                      <div className="card-value">{card.value}</div>
                      <p className="card-value-note">{card.value_note}</p>
                      <div className="card-reason">
                        <span />
                        {card.reasons[0]}
                      </div>
                      <div className="card-bottom">
                        <span>
                          <Clock3 size={13} />
                          {card.deadline
                            ? `${card.deadline.slice(5).replace('-', '.')} 마감 · 예시`
                            : card.period}
                        </span>
                        <button onClick={() => setSelected(card.id)}>
                          조건·신청 준비 <ChevronRight size={15} />
                        </button>
                      </div>
                      {card.prepared && (
                        <span className="prepared-label">
                          <Check size={12} />
                          준비 목록 저장됨 · 미제출
                        </span>
                      )}
                    </article>
                  )
                })}
              </div>
              {shown.length === 0 && (
                <div className="benefit-empty">
                  <Search size={28} />
                  <h3>조건에 맞는 혜택이 없어요</h3>
                  <p>다른 분야나 상태를 선택해 보세요.</p>
                  <button
                    className="text-button"
                    onClick={() => {
                      setQuery('')
                      setCategory('전체 분야')
                      setFilter('all')
                    }}
                  >
                    전체 혜택 보기
                  </button>
                </div>
              )}
              <p className="catalog-footnote">
                예시 금액은 실제 수령액이 아니므로 합산하지 않아요. 추천은 신청
                준비를 돕는 안내이며, 최종 승인은 담당 부서에서 확인해야 합니다.
              </p>
            </div>
            <aside className="benefits-rail">
              <section className="profile-card">
                <div className="rail-title">
                  <h2>
                    <Users size={17} /> 나의 추천 조건
                  </h2>
                  <button
                    className="icon-button"
                    aria-label="추천 조건 수정"
                    onClick={() => setProfileOpen(true)}
                  >
                    <Settings2 size={17} />
                  </button>
                </div>
                <span className="profile-subtitle">
                  {demo
                    ? '실제 개인정보가 없는 예시'
                    : '직접 제공에 동의한 조건'}
                </span>
                <dl>
                  <div>
                    <dt>고용형태</dt>
                    <dd>
                      {profile.employment_type
                        ? {
                            regular: '정규직',
                            fixed_term: '기간제',
                            part_time: '시간제',
                          }[profile.employment_type]
                        : '확인 필요'}
                    </dd>
                  </div>
                  <div>
                    <dt>입사일</dt>
                    <dd>
                      {profile.hire_date?.replaceAll('-', '.') || '확인 필요'}
                    </dd>
                  </div>
                  <div>
                    <dt>자녀 연령</dt>
                    <dd>
                      {profile.children_ages === null
                        ? '미제공'
                        : profile.children_ages.length
                          ? profile.children_ages
                              .map((a) => `만 ${a}세`)
                              .join(', ')
                          : '자녀 없음'}
                    </dd>
                  </div>
                  <div>
                    <dt>가구원</dt>
                    <dd>
                      {profile.household_size
                        ? `${profile.household_size}명`
                        : '미제공'}
                    </dd>
                  </div>
                </dl>
                <button
                  className="secondary-button"
                  onClick={() => setProfileOpen(true)}
                >
                  내 조건 수정하기 <ArrowRight size={15} />
                </button>
                <p className="profile-privacy">
                  <ShieldCheck size={13} />
                  가족 정보는 동의한 범위에서만 사용해요.
                </p>
              </section>
              <section className="rail-tip">
                <span className="tip-icon">
                  <Sparkles size={19} />
                </span>
                <h2>상황이 달라졌나요?</h2>
                <p>
                  입사, 가족 구성, 자녀 나이가 달라지면 받을 수 있는 혜택도
                  달라져요.
                </p>
                <button onClick={() => setProfileOpen(true)}>
                  추천 조건 확인하기 <ArrowRight size={14} />
                </button>
              </section>
              <section className="rail-evidence">
                <BookOpen size={22} />
                <h2>혜택의 근거가 궁금하다면</h2>
                <p>
                  카드에서 판정 이유와 규정을 확인하세요. 로컬 한국전력 자료도
                  별도로 찾아볼 수 있어요.
                </p>
                <button
                  className="text-button"
                  onClick={() => setEvidenceOpen(true)}
                >
                  참고 규정 찾아보기 <ArrowRight size={14} />
                </button>
                <small>한국전력 규정은 KTcs 사규가 아닙니다.</small>
              </section>
              <div className="rail-update">
                <span /> 기준일{' '}
                {cards[0]?.as_of.replaceAll('-', '.') || '확인 중'}
                <br />
                <small>회사 규정 검증 · 미완료</small>
              </div>
            </aside>
          </div>
        )}
        <footer className="benefits-footer">
          <span>
            K:LINK <b>조금 더 나은 일과 일상</b>
          </span>
          <span>
            직원 조건은 자격 판정 코드에서만 사용하며 GPT에 보내지 않아요.
          </span>
        </footer>
      </main>
      {profileOpen && (
        <ProfileDialog
          profile={profile}
          demo={demo}
          busy={busy}
          serverError={error}
          close={() => setProfileOpen(false)}
          save={(p) =>
            act(async () => {
              await benefitRequest('/profile', 'PUT', p)
              await refresh()
              setProfileOpen(false)
              setNotice('추천 조건을 반영했어요.')
            })
          }
          revoke={() =>
            act(async () => {
              await benefitRequest('/profile', 'DELETE')
              await refresh()
              setProfileOpen(false)
              setNotice('정보 활용 동의를 철회하고 저장된 조건을 삭제했어요.')
            })
          }
        />
      )}
      {activeCard && (
        <Dialog title={activeCard.title} close={() => setSelected(null)}>
          <span className={`status-pill ${activeCard.status}`}>
            {LABEL[activeCard.status]}
            {demo && ' · 예시 판정'}
          </span>
          <h3 className="detail-value">{activeCard.value}</h3>
          <p>
            {activeCard.value_note} ·{' '}
            {activeCard.deadline
              ? `예시 마감 ${activeCard.deadline}`
              : activeCard.period}
          </p>
          <div className="detail-warning">
            가상 규정으로 확인한 결과입니다. 실제 KTcs 자격 충족·지급 승인
            결과가 아닙니다.
          </div>
          <h3>이렇게 확인했어요</h3>
          <ul className="check-list">
            {activeCard.checks.map((c) => (
              <li key={c.label} className={c.result}>
                <span>
                  {c.result === 'pass' ? (
                    <CheckCircle2 size={17} />
                  ) : (
                    <Info size={17} />
                  )}
                </span>
                <div>
                  <strong>{c.label}</strong>
                  <p>{c.reason}</p>
                </div>
              </li>
            ))}
          </ul>
          <details className="source-details">
            <summary>
              <BookOpen size={17} /> 예시 규정 근거 확인{' '}
              <ChevronRight size={16} />
            </summary>
            <strong>
              {activeCard.source.title} · {activeCard.source.section}
            </strong>
            <blockquote>{activeCard.source.quote}</blockquote>
            <dl>
              <div>
                <dt>회사·검토 상태</dt>
                <dd>DEMO · 실제 회사 규정 아님</dd>
              </div>
              <div>
                <dt>버전</dt>
                <dd>{activeCard.source.version}</dd>
              </div>
              <div>
                <dt>출처 ID</dt>
                <dd>{activeCard.source.id}</dd>
              </div>
              <div>
                <dt>본문 SHA-256</dt>
                <dd className="source-hash">{activeCard.source.sha256}</dd>
              </div>
            </dl>
          </details>
          <AiExplanation benefitId={activeCard.id} demo={demo} />
          <h3>신청 전 준비할 것</h3>
          <ol className="prepare-list">
            {activeCard.checklist.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ol>
          <div className="form-unavailable">
            <ArrowDownToLine size={18} />
            <div>
              <strong>{activeCard.form_status}</strong>
              <p>
                공식 양식과 신청 주소를 확인한 뒤 연결합니다. 가상 신청서를 회사
                양식으로 제공하지 않아요.
              </p>
            </div>
          </div>
          <button
            className="primary-button full-width"
            disabled={busy || activeCard.status !== 'eligible' || !demo}
            onClick={() =>
              act(async () => {
                const r = await benefitRequest<{ message: string }>(
                  `/${activeCard.id}/prepare`,
                  'POST',
                )
                await refresh()
                setNotice(r.message)
                setSelected(null)
              })
            }
          >
            {demo && activeCard.status === 'eligible'
              ? '예시 준비 목록 저장하기'
              : '조건·회사 규정 확인 후 준비 가능'}
          </button>
          <small className="dialog-footnote">
            실제 신청이나 결재는 제출하지 않습니다. 준비 목록과 저장한 혜택은
            현재 로그인 세션에서 유지돼요.
          </small>
        </Dialog>
      )}
      {evidenceOpen && (
        <EvidenceDialog
          session={session}
          configured={config?.local_evidence_configured ?? false}
          close={() => setEvidenceOpen(false)}
        />
      )}
      {loginOpen && (
        <Dialog
          title="직원 계정 로그인"
          close={() => {
            setLoginOpen(false)
            setPassword('')
          }}
        >
          <p className="detail-warning">
            Supabase 직원 인증과 개인 조건 저장소를 사용합니다. 현재 회사 규정에
            따른 자격 검증은 연결되지 않았어요.
          </p>
          <p className="connection-message">{config?.supabase.message}</p>
          <form onSubmit={login} className="profile-form">
            <label>
              이메일
              <input
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              비밀번호
              <input
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <button className="primary-button" disabled={busy}>
              {busy ? '확인 중…' : '로그인'}
            </button>
            {error && (
              <p role="alert" className="field-error">
                {error}
              </p>
            )}
          </form>
        </Dialog>
      )}
    </div>
  )
}

function AiExplanation({
  benefitId,
  demo,
}: {
  benefitId: string
  demo: boolean
}) {
  const [result, setResult] = useState<{
    summary: string
    quote: string
    source_id: string
  } | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  async function explain() {
    setPending(true)
    setError('')
    try {
      setResult(await benefitRequest(`/${benefitId}/explanation`, 'POST'))
    } catch (e) {
      setError(e instanceof Error ? e.message : '설명을 가져오지 못했어요.')
    } finally {
      setPending(false)
    }
  }
  return (
    <section className="ai-explanation">
      <h3>
        <Sparkles size={16} /> AI로 예시 규정 읽기
      </h3>
      <p>
        버튼을 누르면 이 카드의 가상 규정만 외부 GPT에 전송해 설명 초안을
        만듭니다. 직원 조건은 전송하지 않아요.
      </p>
      {result ? (
        <>
          <div className="ai-draft">
            <strong>AI 설명 초안 · 사람 검토 미완료</strong>
            <p>{result.summary}</p>
            <blockquote>{result.quote}</blockquote>
            <small>
              근거 {result.source_id} · 인용 일치 자동 검사 완료 · 자격 판정에
              반영하지 않음
            </small>
          </div>
        </>
      ) : (
        <button
          className="secondary-button"
          disabled={pending || !demo}
          onClick={explain}
        >
          {pending ? '규정만 읽고 있어요…' : '가상 규정을 쉽게 설명해 주세요'}
        </button>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}

function ProfileDialog({
  profile,
  demo,
  busy,
  serverError,
  close,
  save,
  revoke,
}: {
  profile: Profile
  demo: boolean
  busy: boolean
  serverError: string
  close: () => void
  save: (p: Profile) => void
  revoke: () => void
}) {
  const [draft, setDraft] = useState<Profile>({ ...profile })
  const [ages, setAges] = useState(profile.children_ages?.join(', ') ?? '')
  const [noChildren, setNoChildren] = useState(
    profile.children_ages?.length === 0,
  )
  const [error, setError] = useState('')
  function submit(e: FormEvent) {
    e.preventDefault()
    const values = !draft.family_consent
      ? null
      : noChildren
        ? []
        : ages.trim()
          ? ages.split(',').map((a) => Number(a.trim()))
          : null
    if (
      values?.some(
        (age, i) =>
          !/^\d+$/.test(ages.split(',')[i]?.trim() ?? '') ||
          !Number.isInteger(age) ||
          age < 0 ||
          age > 30,
      )
    ) {
      setError('자녀 나이를 0~30세 정수로 입력해 주세요. 예: 5, 9')
      return
    }
    save({ ...draft, children_ages: values })
  }
  return (
    <Dialog title="나의 추천 조건" close={close}>
      <p>
        {demo
          ? '가상 직원의 조건을 바꿔보세요. 실제 개인정보는 입력하지 마세요.'
          : '필요한 조건만 직접 제공할 수 있어요. HR에서 확인된 사실로 간주하지 않아요.'}
      </p>
      <form className="profile-form" onSubmit={submit}>
        <label className="consent-check">
          <input
            type="checkbox"
            checked={draft.employment_consent}
            onChange={(e) =>
              setDraft({ ...draft, employment_consent: e.target.checked })
            }
          />
          <span>
            <strong>근무 정보로 혜택 찾기</strong>
            <small>고용형태·입사일을 추천에 사용합니다.</small>
          </span>
        </label>
        <fieldset disabled={!draft.employment_consent || busy}>
          <label>
            고용형태
            <select
              value={draft.employment_type ?? ''}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  employment_type:
                    (e.target.value as Profile['employment_type']) || null,
                })
              }
            >
              <option value="">선택하지 않음</option>
              <option value="regular">정규직</option>
              <option value="fixed_term">기간제</option>
              <option value="part_time">시간제</option>
            </select>
          </label>
          <label>
            입사일
            <input
              type="date"
              min="1960-01-01"
              max={new Date().toLocaleDateString('en-CA')}
              value={draft.hire_date ?? ''}
              onChange={(e) =>
                setDraft({ ...draft, hire_date: e.target.value || null })
              }
            />
          </label>
        </fieldset>
        <label className="consent-check">
          <input
            type="checkbox"
            checked={draft.family_consent}
            onChange={(e) =>
              setDraft({ ...draft, family_consent: e.target.checked })
            }
          />
          <span>
            <strong>가족 정보로 혜택 찾기 (선택)</strong>
            <small>
              가구원 수·자녀 나이만 사용하며 이름·주민번호는 받지 않아요.
            </small>
          </span>
        </label>
        <fieldset disabled={!draft.family_consent || busy}>
          <label>
            가구원 수
            <input
              type="number"
              min={1}
              max={20}
              value={draft.household_size ?? ''}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  household_size: e.target.value
                    ? Number(e.target.value)
                    : null,
                })
              }
            />
          </label>
          <label>
            자녀 만 나이 (쉼표로 구분)
            <input
              placeholder="예: 5, 9 · 비우면 미제공"
              value={ages}
              disabled={noChildren}
              onChange={(e) => setAges(e.target.value)}
            />
          </label>
          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={noChildren}
              onChange={(e) => setNoChildren(e.target.checked)}
            />{' '}
            자녀 없음
          </label>
        </fieldset>
        {(error || serverError) && (
          <p role="alert" className="field-error">
            {error || serverError}
          </p>
        )}
        <div className="privacy-explainer">
          <ShieldCheck size={18} />
          <p>
            선택한 정보는 혜택 추천에만 사용하며 GPT에 보내지 않아요. 동의를
            끄고 저장하면 해당 정보를 삭제해요.{' '}
            {demo
              ? '예시 정보는 서버 메모리에만 보관하며 로그아웃하거나 서버를 재시작하면 삭제됩니다.'
              : '정보는 본인 인증과 접근 제한을 거쳐 Supabase에 저장합니다.'}
          </p>
        </div>
        <button className="primary-button full-width" disabled={busy}>
          {busy ? '저장 중…' : '조건 저장하고 다시 추천받기'}
        </button>
        <button
          type="button"
          className="revoke-button"
          disabled={busy}
          onClick={revoke}
        >
          모든 동의 철회 및 조건 삭제
        </button>
      </form>
    </Dialog>
  )
}

function EvidenceDialog({
  session,
  configured,
  close,
}: {
  session: Session | null
  configured: boolean
  close: () => void
}) {
  const [query, setQuery] = useState('복지')
  const [results, setResults] = useState<Evidence[]>([])
  const [source, setSource] = useState<Evidence | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  async function search(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSource(null)
    try {
      const r = await benefitRequest<{ results: Evidence[] }>(
        '/evidence/search?q=' + encodeURIComponent(query),
      )
      setResults(r.results)
      setSearched(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : '검색 실패')
    } finally {
      setLoading(false)
    }
  }
  async function open(id: string) {
    setError('')
    try {
      setSource(
        await benefitRequest<Evidence>('/evidence/' + encodeURIComponent(id)),
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : '원문 확인 실패')
    }
  }
  return (
    <Dialog title="참고 규정 찾아보기" close={close}>
      <div className="detail-warning">
        한국전력 공개 대체 자료입니다. KTcs 직원의 자격 판정에 적용하지
        않습니다. 기존 자동 검토 범위를 유지하며 사람 승인·현행성 확인은
        별도입니다.
      </div>
      {!session || session.mode !== 'demo' ? (
        <p>가상 직원 체험을 시작한 뒤 로컬 참고 자료를 볼 수 있어요.</p>
      ) : !configured ? (
        <p>
          로컬 규정 자료가 연결되지 않았어요. 승인된 자료 경로를 서버에서
          지정해야 합니다.
        </p>
      ) : (
        <>
          <form onSubmit={search} className="evidence-search">
            <input
              aria-label="참고 규정 검색어"
              minLength={2}
              maxLength={100}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button className="primary-button" disabled={loading}>
              {loading ? '찾는 중…' : '찾기'}
            </button>
          </form>
          <small>
            로컬 본문 키워드 조회 · 기존 BM25/Dense 성능 평가와 별개 · GPT 전송
            없음
          </small>
          {error && (
            <p role="alert" className="field-error">
              {error}
            </p>
          )}
          {results.map((r) => (
            <button
              key={r.id}
              className="evidence-result"
              onClick={() => open(r.id)}
            >
              <span>KEPCO · 사람 승인 미완료</span>
              <strong>{r.title}</strong>
              <small>{r.section}</small>
              <p>{r.excerpt}</p>
              <span>
                원문·해시 확인 <ArrowRight size={13} />
              </span>
            </button>
          ))}
          {searched && !loading && !results.length && (
            <p>허용된 범위에서 일치하는 근거를 찾지 못했어요.</p>
          )}
          {source && (
            <section className="local-source">
              <h3>{source.title}</h3>
              <p>{source.section}</p>
              <pre>{source.text}</pre>
              <small>버전: {source.version}</small>
              <code>{source.sha256}</code>
            </section>
          )}
        </>
      )}
    </Dialog>
  )
}
