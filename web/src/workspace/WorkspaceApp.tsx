import { useEffect, useState, type FormEvent } from 'react'
import {
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  Navigate,
} from 'react-router-dom'
import {
  ArrowRight,
  Bell,
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Command,
  FileCheck2,
  Gift,
  Home,
  Menu,
  MessageSquare,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  X,
} from 'lucide-react'
import { WorkspaceProvider, useWorkspace } from './WorkspaceContext'
import { handleTabKey, Brand, Modal, SourceContent, BenefitIcon, StatusBadge } from './components'
import { HomePage } from './HomePage'
import { BenefitsBrowsePage } from './BenefitsBrowsePage'
import { AssistantPage } from './AssistantPage'
import { LibraryPage } from './LibraryPage'
import { PreparationsPage } from './PreparationsPage'
import { ProfilePage } from './ProfilePage'
import './workspace.css'

const NAV = [
  { path: '', label: '홈', icon: Home },
  { path: '/benefits', label: '나의 혜택', icon: Gift },
  { path: '/assistant', label: 'AI 어시스턴트', icon: MessageSquare },
  { path: '/library', label: '규정·양식', icon: BookOpen },
  { path: '/preparations', label: '신청 준비', icon: FileCheck2 },
]
export function WorkspaceApp() {
  return (
    <WorkspaceProvider>
      <Routes>
        <Route path="login" element={<PreviewLogin />} />
        <Route element={<WorkspaceShell />}>
          <Route index element={<HomePage />} />
          <Route path="benefits" element={<BenefitsBrowsePage />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="library" element={<LibraryPage />} />
          <Route path="preparations" element={<PreparationsPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/workspace" replace />} />
        </Route>
      </Routes>
    </WorkspaceProvider>
  )
}

function Navigation({ close }: { close?: () => void }) {
  const { preparations, saved } = useWorkspace()
  return (
    <>
      <Link className="kl-sidebar-brand" to="/workspace" onClick={close}>
        <Brand />
      </Link>
      <div className="kl-nav-caption">나의 워크스페이스</div>
      <nav className="kl-primary-nav" aria-label="워크스페이스 메뉴">
        {NAV.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={`/workspace${path}`}
            end={path === ''}
            onClick={close}
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            <Icon size={19} strokeWidth={1.7} />
            <span>{label}</span>
            {path === '/preparations' && preparations.length > 0 && (
              <span className="kl-nav-count">{preparations.length}</span>
            )}
            {path === '/assistant' && <span className="kl-ai-tag">AI</span>}
          </NavLink>
        ))}
      </nav>
      <div className="kl-sidebar-divider" />
      <div className="kl-nav-caption">빠르게 찾기</div>
      <nav className="kl-quick-nav" aria-label="빠른 메뉴">
        <Link to="/workspace/benefits?status=saved" onClick={close}>
          <span className="kl-small-dot green" />
          저장한 혜택<span>{saved.length}</span>
        </Link>
        <Link to="/workspace/library?tab=forms" onClick={close}>
          <span className="kl-small-dot amber" />
          신청 양식 찾기
          <ChevronRight size={13} />
        </Link>
      </nav>
      <div className="kl-sidebar-bottom">
        <div className="kl-sidebar-assistant">
          <span>
            <Sparkles size={18} />
          </span>
          <strong>어디서부터 시작할지 모르겠다면</strong>
          <p>궁금한 업무를 편하게 물어보세요.</p>
          <Link to="/workspace/assistant">
            AI에게 물어보기 <ArrowRight size={14} />
          </Link>
        </div>
        <NavLink to="/workspace/profile" onClick={close} className="kl-profile-nav">
          <span className="kl-avatar">K</span>
          <span>
            <strong>체험 직원</strong>
            <small>가상 정보로 둘러보는 중</small>
          </span>
          <Settings2 size={16} />
        </NavLink>
      </div>
    </>
  )
}
function WorkspaceShell() {
  const location = useLocation(),
    navigate = useNavigate()
  const { toast, clearToast, benefits, select, selectedId, startPreparation } = useWorkspace()
  const [searchOpen, setSearchOpen] = useState(false),
    [search, setSearch] = useState('')
  const [menuOpen, setMenuOpen] = useState(false),
    [notificationsOpen, setNotificationsOpen] = useState(false),
    [infoOpen, setInfoOpen] = useState(false)
  const [detailTab, setDetailTab] = useState('overview')
  const selected = benefits.find((b) => b.id === selectedId)
  useEffect(() => {
    document.title = 'K:LINK · 나의 업무와 혜택'
    window.scrollTo(0, 0)
    setMenuOpen(false)
  }, [location.pathname])
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(clearToast, 5500)
    return () => clearTimeout(timer)
  }, [toast, clearToast])
  useEffect(() => {
    setDetailTab('overview')
  }, [selectedId])
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
      }
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [])
  const current = location.pathname.endsWith('/profile')
    ? '내 정보·동의 관리'
    : (NAV.find((n) => n.path && location.pathname.startsWith(`/workspace${n.path}`))?.label ??
      '홈')
  function runSearch(event: FormEvent) {
    event.preventDefault()
    setSearchOpen(false)
    navigate('/workspace/library?q=' + encodeURIComponent(search))
  }
  return (
    <div className="kl-workspace">
      <a className="kl-skip" href="#workspace-main">
        본문으로 건너뛰기
      </a>
      <aside className="kl-sidebar">
        <Navigation />
      </aside>
      <div className="kl-workspace-body">
        <header className="kl-topbar">
          <div className="kl-topbar-left">
            <button
              className="kl-icon-button kl-mobile-menu"
              aria-label="전체 메뉴 열기"
              onClick={() => setMenuOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span className="kl-breadcrumb">
              <span>워크스페이스</span>
              <ChevronRight size={13} />
              {current}
            </span>
          </div>
          <div className="kl-topbar-actions">
            <button
              className="kl-global-search"
              onClick={() => setSearchOpen(true)}
              aria-label="통합 검색 열기"
            >
              <Search size={16} />
              <span>혜택, 규정, 양식 검색</span>
              <kbd>
                <Command size={11} /> K
              </kbd>
            </button>
            <button
              className="kl-icon-button kl-notification"
              aria-label="알림 보기"
              onClick={() => setNotificationsOpen(true)}
            >
              <Bell size={19} />
              <i />
            </button>
            <Link to="/workspace/profile" className="kl-topbar-profile" aria-label="내 정보 관리">
              <span className="kl-avatar small">K</span>
              <span>체험 직원</span>
              <ChevronDown size={13} />
            </Link>
          </div>
        </header>
        <div className="kl-preview-ribbon">
          <span>
            <ShieldCheck size={13} />
            디자인 미리보기
          </span>
          <p>가상 직원·예시 규정 기준이며 실제 회사 자격·신청은 확인 전입니다.</p>
          <button onClick={() => setInfoOpen(true)}>
            안내
            <CircleHelp size={13} />
          </button>
        </div>
        <main id="workspace-main" className="kl-main">
          <Outlet />
        </main>
        <footer className="kl-site-footer">
          <span>
            <b>K:LINK</b> 일과 일상을 더 가깝게
          </span>
          <span>화면 검토용 시안 · 실제 개인정보 입력 없이 체험하세요.</span>
        </footer>
      </div>
      <nav className="kl-bottom-nav" aria-label="모바일 주요 메뉴">
        {NAV.map(({ path, label, icon: Icon }) => (
          <NavLink key={path} to={`/workspace${path}`} end={path === ''}>
            <Icon size={20} strokeWidth={1.7} />
            <span>
              {label === 'AI 어시스턴트'
                ? 'AI'
                : label === '규정·양식'
                  ? '자료'
                  : label === '신청 준비'
                    ? '준비'
                    : label === '나의 혜택'
                      ? '혜택'
                      : label}
            </span>
          </NavLink>
        ))}
      </nav>
      {toast && (
        <div className="kl-toast" role="status">
          <ShieldCheck size={18} />
          <span>{toast}</span>
          <button aria-label="알림 닫기" onClick={clearToast}>
            <X size={15} />
          </button>
        </div>
      )}
      {menuOpen && (
        <Modal title="메뉴" close={() => setMenuOpen(false)} drawer>
          <div className="kl-mobile-navigation">
            <Navigation close={() => setMenuOpen(false)} />
          </div>
        </Modal>
      )}
      {searchOpen && (
        <Modal title="무엇을 찾고 계신가요?" close={() => setSearchOpen(false)}>
          <div className="kl-modal-body">
            <form className="kl-command-search" onSubmit={runSearch}>
              <Search size={20} />
              <input
                autoFocus
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="혜택, 규정, 신청 양식을 찾아보세요"
                aria-label="통합 검색어"
              />
              <button className="kl-button primary" type="submit">
                검색
              </button>
            </form>
            <span className="kl-field-caption">자주 찾는 업무</span>
            <div className="kl-chip-row">
              {['휴가', '돌봄', '교육', '출장', '퇴직'].map((q) => (
                <button
                  key={q}
                  className="kl-chip"
                  onClick={() => {
                    setSearchOpen(false)
                    navigate('/workspace/library?q=' + encodeURIComponent(q))
                  }}
                >
                  {q}
                  <ArrowRight size={13} />
                </button>
              ))}
            </div>
            <div className="kl-command-results">
              {benefits
                .filter((b) => !search || (b.title + b.category).includes(search))
                .slice(0, 4)
                .map((b) => (
                  <button
                    key={b.id}
                    onClick={() => {
                      setSearchOpen(false)
                      select(b.id)
                    }}
                  >
                    <BenefitIcon benefit={b} />
                    <span>
                      <strong>{b.title}</strong>
                      <small>{b.category} · 예시 혜택</small>
                    </span>
                    <ChevronRight size={16} />
                  </button>
                ))}
            </div>
          </div>
        </Modal>
      )}
      {notificationsOpen && (
        <Modal
          title="알림"
          subtitle="화면 검토용 예시 알림입니다."
          close={() => setNotificationsOpen(false)}
        >
          <div className="kl-modal-body kl-notifications">
            {[
              {
                title: '놓치기 전에 확인해 보세요',
                text: '자기계발 지원의 예시 마감은 11월 20일이에요.',
                id: 'learning',
                icon: Gift,
              },
              {
                title: '추천 조건을 최신으로 유지해요',
                text: '가족 구성이나 근무 조건이 달라졌다면 확인해 주세요.',
                id: null,
                icon: SlidersHorizontal,
              },
            ].map(({ title, text, id, icon: Icon }) => (
              <button
                key={title}
                onClick={() => {
                  setNotificationsOpen(false)
                  if (id) select(id)
                  else navigate('/workspace/profile')
                }}
              >
                <span>
                  <Icon size={20} />
                </span>
                <div>
                  <strong>{title}</strong>
                  <p>{text}</p>
                  <small>예시 알림</small>
                </div>
                <ChevronRight size={15} />
              </button>
            ))}
          </div>
        </Modal>
      )}
      {infoOpen && (
        <Modal title="K:LINK 화면 미리보기" close={() => setInfoOpen(false)}>
          <div className="kl-modal-body">
            <div className="kl-about-icon">
              <Sparkles size={30} />
            </div>
            <h3>먼저, 나의 업무가 편해지는 경험부터.</h3>
            <p className="kl-body-copy">
              이번 시안은 맞춤 혜택부터 규정 확인, AI 설명, 신청 준비까지의 화면 흐름을 검토하기
              위한 미리보기예요.
            </p>
            <ul className="kl-about-list">
              <li>직원 조건·규정·금액·일정은 모두 예시입니다.</li>
              <li>AI 대화는 예시 응답이며 외부 모델을 호출하지 않아요.</li>
              <li>정식 로그인·공식 양식·실제 신청은 연결 전이에요.</li>
              <li>조건·저장·대화는 현재 화면의 메모리에만 유지돼요.</li>
            </ul>
            <Link
              className="kl-button secondary full"
              to="/workspace/login"
              onClick={() => setInfoOpen(false)}
            >
              로그인 화면도 살펴보기
              <ArrowRight size={16} />
            </Link>
          </div>
        </Modal>
      )}
      {selected && (
        <Modal
          title={selected.title}
          subtitle={selected.category + ' · 예시 혜택'}
          close={() => select(null)}
          drawer
        >
          <div className="kl-detail-hero">
            <BenefitIcon benefit={selected} size={27} />
            <StatusBadge status={selected.status} />
            <div className="kl-detail-amount">{selected.value}</div>
            <p>{selected.value_note}</p>
          </div>
          <div
            className="kl-detail-tabs"
            role="tablist"
            onKeyDown={handleTabKey}
            aria-label="혜택 상세"
          >
            {[
              { id: 'overview', label: '혜택 안내' },
              { id: 'conditions', label: '자격 조건' },
              { id: 'source', label: '규정 근거' },
            ].map((t) => (
              <button
                role="tab"
                aria-selected={detailTab === t.id}
                tabIndex={detailTab === t.id ? 0 : -1}
                key={t.id}
                onClick={() => setDetailTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="kl-detail-body" role="tabpanel">
            {detailTab === 'overview' ? (
              <>
                <h3>이런 혜택이에요</h3>
                <p className="kl-body-copy">{selected.description}</p>
                <div className="kl-reason-box">
                  <ShieldCheck size={18} />
                  <div>
                    <strong>나에게 안내한 이유</strong>
                    <p>{selected.reason}</p>
                  </div>
                </div>
                <dl className="kl-detail-facts">
                  <div>
                    <dt>혜택 규모</dt>
                    <dd>
                      {selected.value} <span>예시</span>
                    </dd>
                  </div>
                  <div>
                    <dt>신청 일정</dt>
                    <dd>
                      {selected.deadline
                        ? `${selected.deadline.replaceAll('-', '.')}까지 · 예시`
                        : selected.period}
                    </dd>
                  </div>
                  <div>
                    <dt>관련 규정</dt>
                    <dd>
                      <button onClick={() => setDetailTab('source')}>
                        가상 복지 규정 {selected.section}
                        <ChevronRight size={13} />
                      </button>
                    </dd>
                  </div>
                  <div>
                    <dt>신청 양식</dt>
                    <dd className="muted">회사 공식 양식 확인 필요</dd>
                  </div>
                </dl>
                <h3>신청 전, 이렇게 준비해요</h3>
                <ol className="kl-numbered-list">
                  {selected.checklist.map((c, i) => (
                    <li key={c}>
                      <span>{i + 1}</span>
                      {c}
                    </li>
                  ))}
                </ol>
              </>
            ) : detailTab === 'conditions' ? (
              <>
                <h3>내 조건과 하나씩 확인했어요</h3>
                <p className="kl-caption">동의해 제공한 예시 정보로만 비교한 결과예요.</p>
                <div className="kl-condition-list">
                  {selected.checks.map((c) => (
                    <div key={c.label} className={c.state}>
                      <span>
                        {c.state === 'pass' ? <ShieldCheck size={20} /> : <CircleHelp size={20} />}
                      </span>
                      <div>
                        <strong>{c.label}</strong>
                        <p>{c.reason}</p>
                      </div>
                      <small>
                        {
                          {
                            pass: '충족',
                            unknown: '확인 필요',
                            fail: '미충족',
                          }[c.state]
                        }
                      </small>
                    </div>
                  ))}
                </div>
                <button
                  className="kl-button secondary full"
                  onClick={() => {
                    select(null)
                    navigate('/workspace/profile')
                  }}
                >
                  내 추천 조건 수정하기
                  <Settings2 size={15} />
                </button>
              </>
            ) : (
              <>
                <h3>답변보다 먼저, 근거를 확인해요</h3>
                <SourceContent benefit={selected} />
              </>
            )}
            <div className="kl-inline-note">
              <ShieldCheck size={15} />
              <p>
                예시 규정 기준의 안내예요. 실제 혜택과 자격은 승인된 회사 규정에서 확인해야 합니다.
              </p>
            </div>
          </div>
          <div className="kl-drawer-actions">
            <button
              className="kl-button secondary"
              onClick={() => {
                const id = selected.id
                select(null)
                navigate('/workspace/assistant?benefit=' + id)
              }}
            >
              <MessageSquare size={16} />
              AI에게 물어보기
            </button>
            <button
              className="kl-button primary"
              onClick={() => {
                startPreparation(selected.id)
                select(null)
                navigate('/workspace/preparations')
              }}
            >
              {selected.status === 'eligible' ? '신청 준비 시작' : '확인할 항목 저장'}
              <ArrowRight size={16} />
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
function PreviewLogin() {
  const { reset } = useWorkspace()
  return (
    <div className="kl-login">
      <div className="kl-login-story">
        <Brand />
        <div>
          <span className="kl-eyebrow">YOUR EVERYDAY WORK COMPANION</span>
          <h1>
            찾는 시간을 줄이고,
            <br />
            나에게 필요한 일을
            <br />
            <em>더 가깝게.</em>
          </h1>
          <p>
            나를 위한 혜택부터, 회사 규정과 업무 준비까지.
            <br />
            K:LINK가 함께 연결해 드려요.
          </p>
          <div className="kl-login-feature">
            <Gift size={20} />
            나에게 맞는 복지·휴가·지원
          </div>
          <div className="kl-login-feature">
            <MessageSquare size={20} />
            근거와 함께 이해하는 업무 안내
          </div>
          <div className="kl-login-feature">
            <FileCheck2 size={20} />
            놓치는 항목 없는 신청 준비
          </div>
        </div>
        <small>K:LINK · WORK & LIFE</small>
      </div>
      <div className="kl-login-panel">
        <Link className="kl-mobile-login-brand" to="/workspace" aria-label="K:LINK 홈">
          <Brand />
        </Link>
        <div className="kl-login-card">
          <span className="kl-login-symbol">
            <Sparkles size={28} />
          </span>
          <h2>오늘도 반가워요</h2>
          <p>나의 업무와 혜택을 한곳에서 만나보세요.</p>
          <span className="kl-tag">로그인 화면 미리보기</span>
          <Link className="kl-button primary full" to="/workspace" onClick={reset}>
            가상 직원으로 둘러보기
            <ArrowRight size={17} />
          </Link>
          <div className="kl-login-note">
            <ShieldCheck size={16} />
            <p>
              회사 계정 입력을 받지 않는 디자인 시안입니다. 정식 사내 로그인은 연동 후 제공해요.
            </p>
          </div>
          <Link to="/workspace/profile" className="kl-text-link">
            추천 조건부터 살펴보기
            <ChevronRight size={14} />
          </Link>
        </div>
        <small>이 화면에서는 실제 개인정보나 비밀번호를 입력하지 않아요.</small>
      </div>
    </div>
  )
}
