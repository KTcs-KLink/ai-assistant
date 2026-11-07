import { useEffect, useState, type FormEvent } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  ArrowRight,
  Bell,
  Bookmark,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileCheck2,
  Gift,
  Home,
  LogIn,
  MessageSquare,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { WorkspaceProvider, useWorkspace } from "../workspace/WorkspaceContext";
import { deadlineLabel } from "../workspace/model";
import { Badge, BenefitIcon, Logo, Modal, Note, Source } from "./ui";
import { Dashboard } from "./Dashboard";
import { Benefits, Library, Preparations, Profile } from "./Pages";
import { Assistant } from "./Assistant";
import "./portal.css";

const NAV = [
  { path: "", label: "홈", icon: Home },
  { path: "/benefits", label: "맞춤 혜택", icon: Gift },
  { path: "/assistant", label: "AI 업무 도우미", icon: Sparkles },
  { path: "/library", label: "규정·양식", icon: BookOpen },
  { path: "/preparations", label: "준비 목록", icon: FileCheck2 },
];
export function PortalApp() {
  return (
    <WorkspaceProvider>
      <Routes>
        <Route path="login" element={<Login />} />
        <Route element={<Shell />}>
          <Route index element={<Dashboard />} />
          <Route path="benefits" element={<Benefits />} />
          <Route path="assistant" element={<Assistant />} />
          <Route path="library" element={<Library />} />
          <Route path="preparations" element={<Preparations />} />
          <Route path="profile" element={<Profile />} />
          <Route path="*" element={<Navigate replace to="/workspace" />} />
        </Route>
      </Routes>
    </WorkspaceProvider>
  );
}
function Shell() {
  const location = useLocation(),
    navigate = useNavigate();
  const {
    benefits,
    select,
    selectedId,
    startPreparation,
    toggleSaved,
    saved,
    preparations,
    toast,
    clearToast,
  } = useWorkspace();
  const [overlay, setOverlay] = useState<"search" | "alerts" | "about" | null>(
    null,
  );
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("overview");
  const selected = benefits.find((benefit) => benefit.id === selectedId);
  useEffect(() => {
    document.title = "K:LINK 직원 포털 · 대안 시안";
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    setTab("overview");
  }, [selectedId]);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(clearToast, 5000);
      return () => clearTimeout(timer);
    }
  }, [toast, clearToast]);
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOverlay("search");
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  function search(event: FormEvent) {
    event.preventDefault();
    setOverlay(null);
    navigate("/workspace/library?q=" + encodeURIComponent(query));
  }
  return (
    <div className="p-app">
      <a className="p-skip" href="#portal-main">
        본문으로 건너뛰기
      </a>
      <header className="p-masthead">
        <div className="p-masthead-inner">
          <Link to="/workspace" aria-label="K:LINK 직원 포털 홈">
            <Logo />
          </Link>
          <span className="p-header-divider" />
          <span className="p-header-caption">나의 일과 생활을 연결하는 곳</span>
          <div className="p-header-tools">
            <button
              className="p-header-search"
              onClick={() => setOverlay("search")}
              aria-label="통합 검색 열기"
            >
              <Search size={17} />
              <span>무엇을 찾으세요?</span>
              <kbd>Ctrl K</kbd>
            </button>
            <button
              className="p-header-icon"
              onClick={() => setOverlay("alerts")}
              aria-label="알림 보기"
            >
              <Bell size={19} />
              <i />
            </button>
            <Link
              to="/workspace/profile"
              className="p-account"
              aria-label="내 정보·동의 관리"
            >
              <span className="p-avatar">K</span>
              <span>체험 직원</span>
              <ChevronDown size={14} />
            </Link>
          </div>
        </div>
      </header>
      <nav className="p-navigation" aria-label="직원 포털 메뉴">
        <div>
          {NAV.map(({ path, label, icon: Icon }) => (
            <NavLink key={path} to={"/workspace" + path} end={!path}>
              <Icon size={17} />
              <span>{label}</span>
              {path === "/preparations" && preparations.length > 0 && (
                <b>{preparations.length}</b>
              )}
            </NavLink>
          ))}
          <Link to="/workspace/profile" className="p-profile-link">
            <Settings2 size={16} />내 정보·동의
          </Link>
        </div>
      </nav>
      <div className="p-preview">
        <span>
          <span className="p-preview-dot" />
          DESIGN PREVIEW
        </span>
        <p>가상 직원·가상 규정으로 둘러보는 화면입니다.</p>
        <button onClick={() => setOverlay("about")}>
          미리보기 안내
          <CircleHelp size={13} />
        </button>
      </div>
      <main id="portal-main" className="p-main">
        <Outlet />
      </main>
      <footer className="p-footer">
        <span>
          <b>K:LINK</b> WORK & LIFE, CONNECTED.
        </span>
        <span>
          실제 자격·SSO·RAG·신청 미연결 · 현재 탭에서만 예시 상태 유지
        </span>
        <Link to="/workspace/login">
          <LogIn size={14} />
          로그인 미리보기
        </Link>
      </footer>
      <nav className="p-mobile-nav" aria-label="모바일 주요 메뉴">
        {NAV.map(({ path, label, icon: Icon }) => (
          <NavLink key={path} to={"/workspace" + path} end={!path}>
            <Icon size={20} />
            <span>
              {label
                .replace("맞춤 ", "")
                .replace("AI 업무 도우미", "AI 도우미")
                .replace("준비 목록", "준비")}
            </span>
          </NavLink>
        ))}
      </nav>
      {toast && (
        <div role="status" className="p-toast">
          <Check size={18} />
          <span>{toast}</span>
          <button onClick={clearToast} aria-label="알림 닫기">
            <X size={16} />
          </button>
        </div>
      )}
      {overlay === "search" && (
        <Modal title="필요한 업무를 찾아보세요" close={() => setOverlay(null)}>
          <div className="p-modal-body">
            <form className="p-search-form" onSubmit={search}>
              <Search size={20} />
              <input
                autoFocus
                maxLength={200}
                aria-label="통합 검색어"
                placeholder="혜택 이름, 규정, 양식"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <button className="p-button" type="submit">
                검색
              </button>
            </form>
            <h3>빠르게 찾기</h3>
            <div className="p-search-results">
              {benefits
                .filter((b) => !query || (b.title + b.category).includes(query))
                .map((b) => (
                  <button
                    key={b.id}
                    onClick={() => {
                      setOverlay(null);
                      select(b.id);
                    }}
                  >
                    <BenefitIcon benefit={b} />
                    <span>
                      <strong>{b.title}</strong>
                      <small>{b.category} · 가상 예시</small>
                    </span>
                    <ChevronRight size={17} />
                  </button>
                ))}
            </div>
            {query &&
              !benefits.some((b) => (b.title + b.category).includes(query)) && (
                <p className="p-subtle">
                  일치하는 혜택이 없습니다. 검색을 누르면 규정·양식도 확인할 수
                  있어요.
                </p>
              )}
          </div>
        </Modal>
      )}
      {overlay === "alerts" && (
        <Modal
          title="확인할 알림"
          subtitle="실제 회사 알림이 아닌 예시입니다."
          close={() => setOverlay(null)}
        >
          <div className="p-modal-body p-alert-list">
            <button
              onClick={() => {
                setOverlay(null);
                select("learning");
              }}
            >
              <span className="p-date-square">
                <b>20</b>11월
              </span>
              <span>
                <strong>배움 지원 예시 접수 마감</strong>
                <small>11월 20일까지 · 필요한 준비를 확인하세요.</small>
              </span>
              <ChevronRight size={16} />
            </button>
            <button
              onClick={() => {
                setOverlay(null);
                navigate("/workspace/profile");
              }}
            >
              <Settings2 size={26} />
              <span>
                <strong>내 추천 조건 확인</strong>
                <small>동의한 최소 조건으로만 혜택을 살펴보세요.</small>
              </span>
              <ChevronRight size={16} />
            </button>
          </div>
        </Modal>
      )}
      {overlay === "about" && (
        <Modal
          title="직원 포털을 미리 만나보세요"
          close={() => setOverlay(null)}
        >
          <div className="p-modal-body">
            <Note>
              이 시안은 가상 직원, 가상 규정, 고정 예시 답변으로 화면과 동작을
              검토하기 위한 데모입니다.
            </Note>
            <ul className="p-about-list">
              <li>금액·기간·추천 결과는 실제 KTcs 제도가 아닙니다.</li>
              <li>회사 SSO·Supabase·RAG·신청 시스템은 연결 전입니다.</li>
              <li>질문을 외부 AI로 보내지 않습니다.</li>
              <li>
                동의·저장·준비 목록은 메모리에만 유지되며 새로고침 시
                초기화됩니다.
              </li>
              <li>공식 양식 파일을 제공하거나 신청을 제출하지 않습니다.</li>
            </ul>
            <Link
              className="p-button p-secondary"
              to="/workspace/login"
              onClick={() => setOverlay(null)}
            >
              로그인 화면도 살펴보기
              <ArrowRight size={16} />
            </Link>
          </div>
        </Modal>
      )}
      {selected && (
        <Modal
          drawer
          title={selected.title}
          subtitle={selected.category + " · 가상 혜택 상세"}
          close={() => select(null)}
        >
          <div className="p-detail-summary">
            <Badge status={selected.status} />
            <strong>{selected.value}</strong>
            <p>{selected.value_note}</p>
            <span>{deadlineLabel(selected)} · 예시 기준일 2026.11.07</span>
          </div>
          <div className="p-detail-tabs" aria-label="혜택 상세 항목">
            {[
              { id: "overview", title: "혜택·준비" },
              { id: "conditions", title: "추천 이유" },
              { id: "source", title: "근거 규정" },
            ].map((item) => (
              <button
                key={item.id}
                aria-pressed={tab === item.id}
                onClick={() => setTab(item.id)}
              >
                {item.title}
              </button>
            ))}
          </div>
          <div className="p-modal-body p-detail-body">
            {tab === "overview" ? (
              <>
                <h3>혜택을 확인하고, 차근차근 준비해요</h3>
                <p>{selected.description}</p>
                <dl className="p-meta">
                  <div>
                    <dt>예시 기간</dt>
                    <dd>{selected.period}</dd>
                  </div>
                  <div>
                    <dt>판단 이유</dt>
                    <dd>{selected.reason}</dd>
                  </div>
                  <div>
                    <dt>양식 상태</dt>
                    <dd>공식 양식 미연결 · 회사 양식 확인 필요</dd>
                  </div>
                </dl>
                <h3>미리 확인할 항목</h3>
                <ol className="p-number-list">
                  {selected.checklist.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
                <Note>
                  준비 목록에 담는 동작입니다. 실제 신청·승인은 이루어지지
                  않습니다.
                </Note>
              </>
            ) : tab === "conditions" ? (
              <>
                <h3>이렇게 추천했어요</h3>
                <div className="p-conditions">
                  {selected.checks.map((check) => (
                    <div key={check.label} className={check.state}>
                      <span>
                        {check.state === "pass" ? (
                          <Check size={17} />
                        ) : (
                          <CircleHelp size={17} />
                        )}
                      </span>
                      <div>
                        <strong>{check.label}</strong>
                        <p>{check.reason}</p>
                      </div>
                      <b>
                        {
                          {
                            pass: "충족",
                            unknown: "확인 필요",
                            fail: "미충족",
                          }[check.state]
                        }
                      </b>
                    </div>
                  ))}
                </div>
                <Link
                  className="p-button p-secondary"
                  to="/workspace/profile"
                  onClick={() => select(null)}
                >
                  <Settings2 size={16} />
                  추천 조건 수정
                </Link>
              </>
            ) : (
              <Source benefit={selected} />
            )}
          </div>
          <div className="p-drawer-footer">
            <button
              className="p-icon-button"
              onClick={() => toggleSaved(selected.id)}
              aria-label={
                selected.title +
                (saved.includes(selected.id) ? " 저장 취소" : " 저장")
              }
              aria-pressed={saved.includes(selected.id)}
            >
              <Bookmark
                size={21}
                fill={saved.includes(selected.id) ? "currentColor" : "none"}
              />
            </button>
            <Link
              to={"/workspace/assistant?benefit=" + selected.id}
              className="p-button p-secondary"
              onClick={() => select(null)}
            >
              <MessageSquare size={16} />
              AI 질문
            </Link>
            <button
              className="p-button"
              onClick={() => {
                startPreparation(selected.id);
                select(null);
                navigate("/workspace/preparations");
              }}
            >
              {selected.status === "eligible"
                ? "신청 준비에 담기"
                : "확인 목록에 담기"}
              <ArrowRight size={16} />
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
function Login() {
  const { reset } = useWorkspace();
  return (
    <div className="p-login">
      <section className="p-login-story">
        <Link to="/workspace">
          <Logo />
        </Link>
        <div>
          <span className="p-kicker">A BETTER EVERYDAY AT WORK</span>
          <h1>
            일에 집중할 수 있도록.
            <br />
            나의 일상까지
            <br />
            <em>함께 연결합니다.</em>
          </h1>
          <p>
            나에게 맞는 혜택을 발견하고,
            <br />
            궁금한 규정을 이해하고, 필요한 준비까지.
          </p>
          <div className="p-login-path">
            <span>발견</span>
            <ArrowRight size={18} />
            <span>이해</span>
            <ArrowRight size={18} />
            <span>준비</span>
          </div>
        </div>
        <small>K:LINK · 직원 포털 대안 시안</small>
      </section>
      <section className="p-login-panel">
        <span className="p-label">로그인 미리보기</span>
        <h2>
          나의 하루에,
          <br />
          K:LINK를 더하세요.
        </h2>
        <p>가상 직원으로 모든 화면을 살펴볼 수 있어요.</p>
        <Link className="p-button" to="/workspace" onClick={reset}>
          가상 직원으로 시작
          <ArrowRight size={18} />
        </Link>
        <div className="p-sso-disabled">
          <ShieldCheck size={18} />
          <span>회사 계정 로그인은 연동 준비 중입니다.</span>
        </div>
        <Note>
          실제 계정·비밀번호를 입력하지 않습니다. SSO, Supabase, 실제 자격
          확인과 신청은 연결 전입니다.
        </Note>
        <Link className="p-text-link" to="/workspace/profile">
          내 정보·동의 화면 먼저 보기
          <ChevronRight size={16} />
        </Link>
      </section>
    </div>
  );
}
