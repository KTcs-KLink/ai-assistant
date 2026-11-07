import { useEffect } from "react";
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
  BookOpen,
  CircleHelp,
  FileCheck2,
  Gift,
  Home,
  LogOut,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { Logo, Note } from "../portal/ui";
import { HrProvider, useHr } from "./HrContext";
import {
  HrDashboard,
  HrBenefits,
  HrPreparations,
  HrProfile,
  HrReadiness,
} from "./HrPages";
import { HrLibrary, HrAssistant } from "./HrKnowledge";
import { HrHome } from "./HrHome";
import { attempt } from "./ui";
import "../portal/portal.css";
import "./hr.css";

const NAV = [
  { path: "", label: "홈", short: "홈", icon: Home },
  { path: "/benefits", label: "맞춤 혜택", short: "혜택", icon: Gift },
  {
    path: "/assistant",
    label: "AI 업무 도우미",
    short: "AI 도우미",
    icon: Sparkles,
  },
  { path: "/library", label: "규정·양식", short: "규정·양식", icon: BookOpen },
  {
    path: "/preparations",
    label: "준비 목록",
    short: "준비",
    icon: FileCheck2,
  },
];
export function HrPortalApp() {
  return (
    <HrProvider>
      <Routes>
        <Route path="login" element={<HrLogin />} />
        <Route element={<HrGate />}>
          <Route element={<HrShell />}>
            <Route index element={<HrHome />} />
            <Route path="home-previous" element={<HrDashboard />} />
            <Route path="benefits" element={<HrBenefits />} />
            <Route path="assistant" element={<HrAssistant />} />
            <Route path="library" element={<HrLibrary />} />
            <Route path="preparations" element={<HrPreparations />} />
            <Route path="profile" element={<HrProfile />} />
            <Route path="status" element={<HrReadiness />} />
            <Route path="*" element={<Navigate replace to="/hr" />} />
          </Route>
        </Route>
      </Routes>
    </HrProvider>
  );
}
function HrGate() {
  const { state, errors, refresh } = useHr();
  if (state === "loading")
    return (
      <div className="p-app hr-loading" role="status">
        <ShieldCheck size={30} />
        인사 서비스와 접속 상태를 확인하고 있어요.
      </div>
    );
  if (state === "offline")
    return (
      <div className="p-app hr-loading">
        <ShieldCheck size={30} />
        <h1>인사 서비스 연결을 확인해 주세요</h1>
        <p>{errors[0]}</p>
        <button className="p-button" onClick={() => void refresh()}>
          연결 다시 확인
        </button>
        <a href="http://127.0.0.1:8824/workspace" className="p-text-link">
          보존된 디자인 시안 열기
          <ArrowRight size={15} />
        </a>
      </div>
    );
  if (state === "signedOut") return <Navigate replace to="/hr/login" />;
  return <Outlet />;
}
function HrShell() {
  const {
    session,
    plans,
    readiness,
    busy,
    logout,
    notice,
    announce,
    errors,
    refresh,
  } = useHr();
  const location = useLocation(),
    navigate = useNavigate();
  useEffect(() => {
    document.title = "K:LINK · 인사 기능 연결";
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    if (notice) {
      const timer = setTimeout(() => announce(""), 6500);
      return () => clearTimeout(timer);
    }
  }, [notice, announce]);
  return (
    <div className="p-app hr-app" aria-busy={busy}>
      <a href="#hr-main" className="p-skip">
        본문으로 건너뛰기
      </a>
      <header className="p-masthead">
        <div className="p-masthead-inner">
          <Link to="/hr" aria-label="K:LINK 인사 홈">
            <Logo />
          </Link>
          <span className="hr-connected">
            <span />
            인사 기능 연결
          </span>
          <div className="p-header-tools">
            <Link
              to="/hr/status"
              className="hr-header-status"
              aria-label="연결 상태"
            >
              <ShieldCheck size={17} />
              <span>연결 상태</span>
            </Link>
            <Link
              to="/hr/profile"
              className="p-account"
              aria-label="내 조건·동의 관리"
            >
              <span className="p-avatar">K</span>
              <span>
                {session?.mode === "demo" ? "가상 직원" : "로그인한 직원"}
              </span>
            </Link>
            <button
              className="p-header-icon"
              aria-label="접속 종료"
              disabled={busy}
              onClick={() =>
                void attempt(logout()).then((done) => {
                  if (done) navigate("/hr/login");
                })
              }
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </header>
      <nav className="p-navigation" aria-label="인사 포털 메뉴">
        <div>
          {NAV.map(({ path, label, icon: Icon }) => (
            <NavLink key={path} to={"/hr" + path} end={!path}>
              <Icon size={17} />
              <span>{label}</span>
              {path === "/preparations" && !!plans?.length && (
                <b>{plans.length}</b>
              )}
            </NavLink>
          ))}
          <NavLink className="p-profile-link" to="/hr/profile">
            <Settings2 size={16} />내 조건·동의
          </NavLink>
        </div>
      </nav>
      <div className="hr-boundary">
        <div>
          <span className="hr-live-dot" />
          <strong>
            {session?.mode === "demo"
              ? "서버 연결 · 예시 직원 체험"
              : "직원 세션 연결"}
          </strong>
        </div>
        <p>
          혜택은 {session?.mode === "demo" ? "가상 규정" : "제공된 조건"} 기준 ·
          원문은 한국전력 참고자료 · 회사 SSO·실제 신청은 연결 전
        </p>
        <Link to="/hr/status">
          상태 확인
          <CircleHelp size={14} />
        </Link>
      </div>
      <main className="p-main" id="hr-main">
        {errors.length > 0 && (
          <div role="alert" className="hr-errors">
            <strong>일부 정보를 조회하지 못했어요</strong>
            {errors.map((text) => (
              <p key={text}>{text}</p>
            ))}
            <button onClick={() => void refresh()}>
              <RefreshCw size={14} />
              다시 조회
            </button>
          </div>
        )}
        <Outlet />
      </main>
      <footer className="p-footer">
        <span>
          <b>K:LINK</b> 인사 기능 연결 화면
        </span>
        <span>
          승인된 회사 규정 {readiness?.approved_policy_count ?? "미확인"}건 ·
          공식 양식 {readiness?.official_form_count ?? "미확인"}건 · 실제 제출
          미연결
        </span>
        <a href="http://127.0.0.1:8824/workspace">
          보존된 시안
          <ArrowRight size={13} />
        </a>
      </footer>
      <nav className="p-mobile-nav" aria-label="인사 모바일 메뉴">
        {NAV.map(({ path, short, icon: Icon }) => (
          <NavLink key={path} to={"/hr" + path} end={!path}>
            <Icon size={20} />
            <span>{short}</span>
          </NavLink>
        ))}
      </nav>
      {notice && (
        <div className="p-toast" role="status">
          <ShieldCheck size={17} />
          <span>{notice}</span>
          <button aria-label="안내 닫기" onClick={() => announce("")}>
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
function HrLogin() {
  const { state, busy, startDemo, refresh, notice, errors } = useHr(),
    navigate = useNavigate();
  useEffect(() => {
    document.title = "K:LINK · 인사 기능 시작";
  }, []);
  if (state === "connected") return <Navigate replace to="/hr" />;
  return (
    <div className="p-login hr-login">
      <section className="p-login-story">
        <Logo />
        <div>
          <span className="p-kicker">YOUR WORK, CONNECTED</span>
          <h1>
            익숙한 새 화면에서.
            <br />
            인사 업무를
            <br />
            <em>이어서 시작하세요.</em>
          </h1>
          <p>
            조건에 맞는 추천부터 원문 확인,
            <br />
            준비 목록과 변경 안내까지 연결했습니다.
          </p>
          <div className="p-login-path">
            <span>추천</span>
            <ArrowRight size={18} />
            <span>근거</span>
            <ArrowRight size={18} />
            <span>준비</span>
          </div>
        </div>
        <a href="http://127.0.0.1:8824/workspace">보존된 디자인 시안 보기 →</a>
      </section>
      <section className="p-login-panel">
        <span className="p-label">인사 서비스 연결</span>
        <h2>
          기능은 연결하고,
          <br />
          회사 적용은 확인하면서.
        </h2>
        <p>
          서버의 가상 직원·예시 조건으로 시작합니다. 실제 직원 정보는 입력하지
          마세요.
        </p>
        <button
          className="p-button"
          disabled={busy || state === "loading" || state === "offline"}
          onClick={() =>
            void attempt(startDemo()).then((done) => {
              if (done) navigate("/hr");
            })
          }
        >
          {busy
            ? "예시 접속을 준비하고 있어요…"
            : "예시 직원으로 인사 기능 시작"}
          <ArrowRight size={17} />
        </button>
        <div className="p-sso-disabled">
          <ShieldCheck size={18} />
          <span>회사 계정·SSO 로그인은 연결 전입니다.</span>
        </div>
        <Note>
          예시 조건: 정규직 · 2019년 입사 · 만 5세·9세 자녀 · 4인 가구. 가상
          동의 조건을 서버에서 불러옵니다. 실제 혜택 지급·신청은 진행되지
          않아요.
        </Note>
        {state === "offline" && (
          <div className="hr-login-error" role="alert">
            <p>{errors[0] || "인사 서비스가 실행 중인지 확인해 주세요."}</p>
            <button className="p-text-link" onClick={() => void refresh()}>
              <RefreshCw size={15} />
              연결 다시 확인
            </button>
          </div>
        )}
        {state !== "offline" && notice && (
          <p className="hr-login-error" role="alert">
            {notice}
          </p>
        )}
        <div className="hr-login-status">
          <span>
            인사 서비스{" "}
            <b>
              {state === "loading"
                ? "확인 중"
                : state === "offline"
                  ? "연결 확인 필요"
                  : "연결됨"}
            </b>
          </span>
          <span>
            직원 계정 저장소 <b>적재 보류 · 연결 재검증 미실시</b>
          </span>
          <span>
            실제 회사 자격 <b>확정 전</b>
          </span>
        </div>
      </section>
    </div>
  );
}
