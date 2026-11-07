import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  ArrowRight,
  Bell,
  BookOpen,
  ChevronRight,
  FileCheck2,
  Gift,
  LayoutDashboard,
  LogOut,
  Menu,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useHr } from "./HrContext";
import { attempt } from "./ui";
import "./workspace.css";

const WORK_NAV = [
  { path: "", label: "업무 현황", icon: LayoutDashboard },
  { path: "/assistant", label: "AI 업무 도우미", icon: Sparkles },
  { path: "/library", label: "규정·양식", icon: BookOpen },
  { path: "/preparations", label: "내 준비 업무", icon: FileCheck2 },
];

export function WorkspaceDialog({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null),
    titleId = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current,
      overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog?.showModal();
    return () => {
      dialog?.close();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      className="ws-dialog"
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <header>
        <h2 id={titleId}>{title}</h2>
        <button aria-label="닫기" onClick={close}>
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}

export function HrWorkspaceShell() {
  const {
    session,
    plans,
    catalog,
    readiness,
    updates,
    busy,
    reminders,
    logout,
    notice,
    announce,
    errors,
    refresh,
  } = useHr();
  const location = useLocation(),
    navigate = useNavigate();
  const [searchOpen, setSearchOpen] = useState(false),
    [menuOpen, setMenuOpen] = useState(false),
    [updatesOpen, setUpdatesOpen] = useState(false),
    [searchQuery, setSearchQuery] = useState(""),
    [searchMode, setSearchMode] = useState<"sources" | "question">("sources"),
    [refreshing, setRefreshing] = useState(false);
  const pageName =
    [
      ...WORK_NAV,
      { path: "/profile", label: "내 조건·동의" },
      { path: "/status", label: "연결·적용 상태" },
      { path: "/benefits", label: "맞춤 혜택" },
    ].find(
      (item) =>
        location.pathname === "/hr" + item.path ||
        location.pathname === "/hr" + item.path + "/",
    )?.label ?? "업무 공간";
  const searchLimit = searchMode === "sources" ? 100 : 500;
  useEffect(() => {
    document.title = `K:LINK · ${pageName}`;
    window.scrollTo(0, 0);
  }, [location.pathname, pageName]);
  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if (
        (event.ctrlKey || event.metaKey) &&
        !event.altKey &&
        !event.isComposing &&
        event.key.toLowerCase() === "k"
      ) {
        event.preventDefault();
        setMenuOpen(false);
        setUpdatesOpen(false);
        setSearchOpen(true);
      }
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => announce(""), 6500);
    return () => clearTimeout(timer);
  }, [notice, announce]);
  function closeSearch() {
    setSearchOpen(false);
    setSearchQuery("");
    setSearchMode("sources");
  }
  function search(event: FormEvent) {
    event.preventDefault();
    const text = searchQuery.trim();
    if (text.length < 2 || text.length > searchLimit) return;
    if (searchMode === "question")
      navigate("/hr/assistant", { state: { draftQuestion: text } });
    else navigate("/hr/library?tab=rules&q=" + encodeURIComponent(text));
    closeSearch();
  }
  async function reload() {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }
  const workLinks = WORK_NAV.map(({ path, label, icon: Icon }) => (
    <NavLink
      key={path}
      to={"/hr" + path}
      end={!path}
      onClick={() => setMenuOpen(false)}
    >
      <Icon size={18} />
      <span>{label}</span>
      {path === "/preparations" && !!plans?.length && <b>{plans.length}</b>}
    </NavLink>
  ));
  return (
    <div className="p-app hr-app hr-saas" aria-busy={busy || refreshing}>
      <a href="#hr-main" className="p-skip">
        본문으로 건너뛰기
      </a>
      <aside className="ws-sidebar">
        <Link className="ws-brand" to="/hr" aria-label="K:LINK 업무 홈">
          <span className="p-logomark" aria-hidden="true">
            <i />
            <i />
          </span>
          <strong>K:LINK</strong>
          <span>WORKSPACE</span>
        </Link>
        <div className="ws-workspace-name">
          <span>K</span>
          <div>
            <strong>인사 업무 공간</strong>
            <small>한국전력 참고자료</small>
          </div>
        </div>
        <span className="ws-nav-label">내 업무</span>
        <nav className="ws-nav" aria-label="인사 포털 메뉴">
          {workLinks}
        </nav>
        <span className="ws-nav-label">서비스</span>
        <nav className="ws-nav" aria-label="인사 서비스 메뉴">
          <NavLink to="/hr/benefits">
            <Gift size={18} />
            <span>맞춤 혜택</span>
            {catalog?.synthetic && <em>예시</em>}
          </NavLink>
          <NavLink to="/hr/profile">
            <Settings2 size={18} />
            <span>내 조건·동의</span>
          </NavLink>
        </nav>
        <div className="ws-sidebar-bottom">
          <Link to="/hr/status">
            <ShieldCheck size={17} />
            <span>연결·적용 상태</span>
            <ChevronRight size={14} />
          </Link>
          <div className="ws-workspace-note">
            <span className="ws-dot" />
            <span>
              KTcs 적용 미확인
              <small>
                {session?.mode === "demo"
                  ? "예시 직원으로 접속 중"
                  : "현재 계정의 연결 범위 확인"}
              </small>
            </span>
          </div>
        </div>
      </aside>
      <div className="ws-surface">
        <header className="ws-topbar">
          <button
            className="ws-mobile-toggle"
            aria-label="업무 메뉴 열기"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(true)}
          >
            <Menu size={21} />
          </button>
          <div className="ws-breadcrumb">
            <span>업무 공간</span>
            <ChevronRight size={13} />
            <strong>{pageName}</strong>
          </div>
          <button
            className="ws-global-search"
            aria-label="업무 검색 열기"
            onClick={() => setSearchOpen(true)}
          >
            <Search size={16} />
            <span>규정 검색 또는 AI 질문</span>
            <kbd>Ctrl K</kbd>
          </button>
          <div className="ws-topbar-actions">
            <button
              title="데이터 새로고침"
              aria-label="데이터 새로고침"
              disabled={busy || refreshing}
              onClick={() => void reload()}
            >
              <RefreshCw
                size={17}
                className={refreshing ? "ws-spinning" : ""}
              />
            </button>
            <button
              title="변경 안내 설정"
              aria-label="변경 안내 설정"
              onClick={() => setUpdatesOpen(true)}
            >
              <Bell size={18} />
            </button>
            <Link
              className="ws-user"
              to="/hr/profile"
              aria-label="내 조건·동의 관리"
            >
              <span>K</span>
              <strong>
                {session?.mode === "demo"
                  ? "예시 직원"
                  : session?.name || "내 계정"}
              </strong>
            </Link>
            <button
              aria-label="접속 종료"
              title="접속 종료"
              disabled={busy}
              onClick={() =>
                void attempt(logout()).then((done) => {
                  if (done) navigate("/hr/login");
                })
              }
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <main className="ws-main" id="hr-main">
          {errors.length > 0 && (
            <div role="alert" className="ws-error-banner">
              <div>
                <strong>일부 정보를 불러오지 못했어요</strong>
                {errors.map((error) => (
                  <p key={error}>{error}</p>
                ))}
              </div>
              <button disabled={refreshing} onClick={() => void reload()}>
                <RefreshCw size={14} />
                다시 조회
              </button>
            </div>
          )}
          <Outlet />
        </main>
        <footer className="ws-footer">
          <span>
            K:LINK <span>·</span> 인사 업무 공간
          </span>
          <Link to="/hr/status">
            한전 참고자료 · 회사 적용 확인 필요
            <ArrowRight size={13} />
          </Link>
        </footer>
      </div>
      {notice && (
        <div className="ws-toast" role="status">
          <ShieldCheck size={17} />
          <span>{notice}</span>
          <button aria-label="안내 닫기" onClick={() => announce("")}>
            <X size={17} />
          </button>
        </div>
      )}
      {menuOpen && (
        <WorkspaceDialog title="업무 메뉴" close={() => setMenuOpen(false)}>
          <nav className="ws-mobile-menu" aria-label="인사 모바일 메뉴">
            {workLinks}
            <Link to="/hr/benefits" onClick={() => setMenuOpen(false)}>
              <Gift size={18} />
              맞춤 혜택{catalog?.synthetic && <em>예시</em>}
            </Link>
            <Link to="/hr/profile" onClick={() => setMenuOpen(false)}>
              <Settings2 size={18} />내 조건·동의
            </Link>
            <Link to="/hr/status" onClick={() => setMenuOpen(false)}>
              <ShieldCheck size={18} />
              연결·적용 상태
            </Link>
          </nav>
        </WorkspaceDialog>
      )}
      {searchOpen && (
        <WorkspaceDialog title="업무 검색" close={closeSearch}>
          <form className="ws-search-form" onSubmit={search}>
            <div className="ws-search-modes">
              <button
                type="button"
                aria-pressed={searchMode === "sources"}
                onClick={() => setSearchMode("sources")}
              >
                <BookOpen size={16} />
                규정 원문 검색
              </button>
              <button
                type="button"
                aria-pressed={searchMode === "question"}
                onClick={() => setSearchMode("question")}
              >
                <Sparkles size={16} />
                AI 질문 작성
              </button>
            </div>
            <label htmlFor="ws-search-input">
              {searchMode === "sources"
                ? "찾을 규정이나 업무"
                : "궁금한 인사 질문"}
            </label>
            <div className="ws-search-input">
              <Search size={19} />
              <input
                id="ws-search-input"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                maxLength={searchLimit}
                placeholder={
                  searchMode === "sources"
                    ? "예: 휴가, 급여, 퇴직"
                    : "예: 병가 증빙은 언제 제출하나요?"
                }
                autoFocus
              />
            </div>
            <p>
              {searchMode === "sources"
                ? "연결된 한전 참고 규정에서 검색합니다."
                : "개인정보는 입력하지 마세요. AI 도우미에서 확인 후 전송합니다."}
            </p>
            <footer>
              <span>
                {searchQuery.length}/{searchLimit}
              </span>
              <button
                className="ws-primary"
                disabled={
                  searchQuery.trim().length < 2 ||
                  searchQuery.trim().length > searchLimit
                }
              >
                {searchMode === "sources" ? "원문 검색" : "질문 이어쓰기"}
                <ArrowRight size={15} />
              </button>
            </footer>
          </form>
        </WorkspaceDialog>
      )}
      {updatesOpen && (
        <WorkspaceDialog
          title="변경 안내 설정"
          close={() => setUpdatesOpen(false)}
        >
          <div className="ws-updates-settings">
            {updates ? (
              <>
                <label>
                  <input
                    type="checkbox"
                    checked={updates.enabled}
                    disabled={busy}
                    onChange={(event) =>
                      void attempt(reminders(event.target.checked))
                    }
                  />
                  <span>
                    <strong>이 화면에서 변경·마감 안내 받기</strong>
                    <small>
                      원할 때 켜고 끌 수 있어요. 메일·문자는 발송하지 않습니다.
                    </small>
                  </span>
                </label>
                {updates.enabled && (
                  <div className="ws-settings-updates">
                    {updates.updates.length ? (
                      updates.updates.map((item, index) => (
                        <Link
                          key={item.benefit_id + index}
                          to={
                            "/hr/benefits?benefit=" +
                            encodeURIComponent(item.benefit_id)
                          }
                          onClick={() => setUpdatesOpen(false)}
                        >
                          {updates.synthetic && (
                            <span className="ws-badge warning">예시 일정</span>
                          )}
                          <p>{item.message}</p>
                          <ChevronRight size={15} />
                        </Link>
                      ))
                    ) : (
                      <p>현재 표시할 변경 안내가 없습니다.</p>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p>변경 안내를 불러오지 못했어요.</p>
            )}
            <Link to="/hr/status" onClick={() => setUpdatesOpen(false)}>
              서비스 연결 범위 확인
              <ArrowRight size={14} />
            </Link>
            <small>
              회사 승인 규정 {readiness?.approved_policy_count ?? "미확인"}건 ·
              공식 양식 {readiness?.official_form_count ?? "미확인"}건
            </small>
          </div>
        </WorkspaceDialog>
      )}
    </div>
  );
}
