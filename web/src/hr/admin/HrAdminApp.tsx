import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  Link,
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BookCheck,
  Boxes,
  ChartNoAxesCombined,
  ChevronDown,
  CircleHelp,
  Database,
  FileClock,
  LayoutDashboard,
  LogOut,
  Menu,
  Palette,
  MessageSquareText,
  Settings2,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  ControlError,
  ROLE_NAMES,
  control,
  useControl,
  type OpsSession,
} from "../operations";
import { WorkspaceDialog } from "../HrWorkspaceShell";
import {
  AdminOverview,
  AdminSources,
  AdminJobs,
  AdminReviews,
} from "./DataPages";
import { AdminUsage, AdminSettings } from "./UsagePages";
import { AdminCases, AdminAudit } from "./OperationsPages";
import "./admin.css";
import "../operations.css";

const NAV = [
  {
    path: "",
    label: "운영 현황",
    icon: LayoutDashboard,
    permission: "health",
    group: "WORKSPACE",
  },
  {
    path: "/sources",
    label: "원문·데이터",
    icon: Database,
    permission: "sources",
    group: "DATA & AI",
  },
  {
    path: "/jobs",
    label: "수집·재적재 작업",
    icon: Boxes,
    permission: "jobs",
    group: "DATA & AI",
  },
  {
    path: "/reviews",
    label: "원문 검토",
    icon: BookCheck,
    permission: "reviews",
    group: "DATA & AI",
  },
  {
    path: "/usage",
    label: "토큰·비용",
    icon: ChartNoAxesCombined,
    permission: "usage",
    group: "DATA & AI",
  },
  {
    path: "/cases",
    label: "직원 문의",
    icon: MessageSquareText,
    permission: "cases",
    group: "OPERATIONS",
  },
  {
    path: "/settings",
    label: "예산·권한·연결",
    icon: Settings2,
    permission: "health",
    group: "OPERATIONS",
  },
  {
    path: "/audit",
    label: "변경 이력",
    icon: FileClock,
    permission: "audit",
    group: "OPERATIONS",
  },
];
const AdminContext = createContext<OpsSession | null>(null);
export function useAdmin() {
  const value = useContext(AdminContext);
  if (!value) throw new Error("관리자 접속이 필요합니다.");
  return value;
}
export function AdminGate({
  permission,
  children,
}: {
  permission: string;
  children: ReactNode;
}) {
  const session = useAdmin();
  return session.permissions.includes(permission) ? (
    children
  ) : (
    <div className="ops-locked">
      <ShieldCheck size={32} />
      <h1>이 역할에서 사용할 수 없는 기능입니다.</h1>
      <p>
        실제 조직 권한은 연결 전이며, 현재 선택한 체험 역할의 서버 권한을
        적용합니다.
      </p>
      <Link to="/hr/admin">
        운영 현황으로 돌아가기
        <ArrowRight size={15} />
      </Link>
    </div>
  );
}
export default function HrAdminApp() {
  const session = useControl<OpsSession>("/api/control/session?admin=true");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [role, setRole] = useState("owner");
  async function enter() {
    setBusy(true);
    setError("");
    try {
      await control("/api/control/session/demo", "POST", { role });
      session.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "체험을 시작하지 못했습니다.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (session.loading && !session.data)
    return (
      <div className="ops-boot" role="status">
        <Activity size={26} />
        관리자 접속을 확인하고 있습니다.
      </div>
    );
  if (!session.data || session.error)
    return (
      <div className="ops-entry">
        <Link className="ops-entry-back" to="/hr">
          <ArrowLeft size={16} />
          직원 화면으로
        </Link>
        <div className="ops-entry-panel">
          <div className="ops-brand">
            <i />
            K:LINK<span>ADMIN</span>
          </div>
          <span className="ops-eyebrow">OPERATIONS WORKSPACE</span>
          <h1>
            인사와 AI 운영을,
            <br />한 곳에서 관리하세요.
          </h1>
          <p>
            원문 수집부터 검토, 재적재와 사용량까지.
            <br />
            현재는 로컬 운영 체험으로 시작합니다.
          </p>
          <label>
            체험 역할
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {["owner", "data_admin", "hr_admin", "analyst"].map((value) => (
                <option key={value} value={value}>
                  {ROLE_NAMES[value]}
                </option>
              ))}
            </select>
          </label>
          <button
            className="ops-primary"
            disabled={busy}
            onClick={() => void enter()}
          >
            {busy ? "접속 준비 중…" : "관리자 체험 시작"}
            <ArrowRight size={16} />
          </button>
          {(error ||
            (session.error &&
              !(
                session.error instanceof ControlError &&
                session.error.status === 401
              ))) && (
            <p className="ops-error" role="alert">
              {error || session.error?.message}
            </p>
          )}
          <small>
            <ShieldCheck size={14} />
            회사 SSO·실제 관리자 인증은 연결 전입니다. 체험 진입은 조직 권한을
            부여하지 않습니다.
          </small>
        </div>
        <div className="ops-entry-note">
          한전 참고자료 · 운영 데이터 로컬 보관 · Supabase 적재 HOLD
        </div>
      </div>
    );
  return (
    <AdminContext.Provider value={session.data}>
      <Routes>
        <Route element={<AdminShell refreshSession={session.refresh} />}>
          <Route index element={<AdminOverview />} />
          <Route
            path="sources"
            element={
              <AdminGate permission="sources">
                <AdminSources />
              </AdminGate>
            }
          />
          <Route
            path="jobs"
            element={
              <AdminGate permission="jobs">
                <AdminJobs />
              </AdminGate>
            }
          />
          <Route
            path="reviews"
            element={
              <AdminGate permission="reviews">
                <AdminReviews />
              </AdminGate>
            }
          />
          <Route
            path="usage"
            element={
              <AdminGate permission="usage">
                <AdminUsage />
              </AdminGate>
            }
          />
          <Route
            path="cases"
            element={
              <AdminGate permission="cases">
                <AdminCases />
              </AdminGate>
            }
          />
          <Route path="settings" element={<AdminSettings />} />
          <Route
            path="audit"
            element={
              <AdminGate permission="audit">
                <AdminAudit />
              </AdminGate>
            }
          />
          <Route path="*" element={<Navigate replace to="/hr/admin" />} />
        </Route>
      </Routes>
    </AdminContext.Provider>
  );
}
function AdminShell({ refreshSession }: { refreshSession: () => void }) {
  const session = useAdmin(),
    location = useLocation();
  const [menu, setMenu] = useState(false),
    [roleOpen, setRoleOpen] = useState(false),
    [role, setRole] = useState(session.role),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const nav = NAV.filter((item) =>
      session.permissions.includes(item.permission),
    ),
    current =
      NAV.find(
        (item) =>
          location.pathname.replace(/\/$/, "") === "/hr/admin" + item.path,
      )?.label ?? "운영 현황";
  useEffect(() => {
    document.title = `K:LINK 관리자 · ${current}`;
    window.scrollTo(0, 0);
    setMenu(false);
  }, [location.pathname, current]);
  async function switchRole() {
    setBusy(true);
    setError("");
    try {
      await control("/api/control/session/demo", "POST", { role });
      setRoleOpen(false);
      refreshSession();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "역할을 변경하지 못했습니다.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    setBusy(true);
    try {
      await control("/api/control/session?admin=true", "DELETE");
      refreshSession();
    } finally {
      setBusy(false);
    }
  }
  let group = "";
  const links = nav.map((item) => {
    const heading = group !== item.group;
    group = item.group;
    return (
      <div key={item.path}>
        {heading && <p className="ops-nav-group">{item.group}</p>}
        <NavLink to={"/hr/admin" + item.path} end={!item.path}>
          <item.icon size={17} />
          <span>{item.label}</span>
          {item.path === "/usage" && <i className="ops-nav-live" />}
        </NavLink>
      </div>
    );
  });
  return (
    <div className={"ops-app" + (menu ? " menu-open" : "")}>
      <a className="p-skip-link" href="#ops-main">
        관리자 본문으로
      </a>
      {menu && (
        <button
          className="ops-nav-backdrop"
          aria-label="관리자 메뉴 닫기"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className="ops-sidebar">
        <Link to="/hr/admin" className="ops-brand">
          <i />
          K:LINK<span>ADMIN</span>
        </Link>
        <button
          className="ops-mobile-close"
          aria-label="관리자 메뉴 닫기"
          onClick={() => setMenu(false)}
        >
          <X size={20} />
        </button>
        <div className="ops-tenant">
          <span>K</span>
          <div>
            <strong>인사 · AI 운영</strong>
            <small>한전 참고자료 워크스페이스</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <nav aria-label="관리자 메뉴">{links}</nav>
        <div className="ops-sidebar-bottom">
          <Link to="/hr/design">
            <Palette size={15} />
            디자인 스튜디오
          </Link>
          <Link to="/hr">
            <ArrowLeft size={15} />
            직원 화면으로
          </Link>
          <div>
            <span className="ops-status-dot" />
            로컬 운영 체험<small>회사 SSO·운영 승인 연결 전</small>
          </div>
        </div>
      </aside>
      <div className="ops-body">
        <header className="ops-topbar">
          <button
            className="ops-menu-toggle"
            aria-label="관리자 메뉴 열기"
            onClick={() => setMenu(true)}
          >
            <Menu size={20} />
          </button>
          <div className="ops-breadcrumb">
            워크스페이스<span>/</span>
            <strong>{current}</strong>
          </div>
          <div>
            <span className="ops-top-environment">
              <i />
              LOCAL
            </span>
            <Link to="/hr/status" aria-label="회사 연결 상태">
              <CircleHelp size={18} />
            </Link>
            <button
              className="ops-role-control"
              onClick={() => {
                setRole(session.role);
                setRoleOpen(true);
              }}
            >
              <span>{session.role === "owner" ? "O" : "A"}</span>
              {ROLE_NAMES[session.role]}
              <ChevronDown size={13} />
            </button>
            <button
              aria-label="관리자 접속 종료"
              disabled={busy}
              onClick={() => void logout()}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <main id="ops-main">
          <Outlet />
        </main>
        <footer className="ops-footer">
          <span>K:LINK OPERATIONS</span>
          <span>로컬 운영 기록 · 조직 승인·실제 직원 인증은 별도 연결</span>
        </footer>
      </div>
      {roleOpen && (
        <WorkspaceDialog
          title="관리자 체험 역할"
          close={() => setRoleOpen(false)}
        >
          <div className="ops-role-dialog">
            <p>
              역할마다 서버에서 허용하는 기능이 다릅니다. 실제 조직 권한이나
              직원 정보 접근을 부여하지 않습니다.
            </p>
            {["owner", "data_admin", "hr_admin", "analyst"].map((value) => (
              <label key={value}>
                <input
                  type="radio"
                  name="ops-role"
                  value={value}
                  checked={role === value}
                  onChange={() => setRole(value)}
                />
                <span>
                  <strong>{ROLE_NAMES[value]}</strong>
                  <small>
                    {value === "owner"
                      ? "데이터·사용량·설정·인사 문의 전체"
                      : value === "data_admin"
                        ? "원문·수집 작업·검토 기록"
                        : value === "hr_admin"
                          ? "직원 문의·원문 검토"
                          : "토큰·비용 분석·변경 이력"}
                  </small>
                </span>
              </label>
            ))}
            {error && (
              <p role="alert" className="ops-error">
                {error}
              </p>
            )}
            <button
              className="ops-primary"
              disabled={busy}
              onClick={() => void switchRole()}
            >
              선택한 역할로 체험
              <ArrowRight size={15} />
            </button>
          </div>
        </WorkspaceDialog>
      )}
    </div>
  );
}
