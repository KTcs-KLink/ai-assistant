import { Link, NavLink, Outlet } from 'react-router-dom'
import { cx, Logo } from '../components/ui'

const MENU = [
  { to: '/admin', label: '개요', end: true },
  { to: '/admin/documents', label: '문서 관리' },
  { to: '/admin/feedback', label: '답변 피드백' },
  { to: '/admin/users', label: '사용자 · 권한' },
  { to: '/admin/settings', label: '설정' },
]

export function AdminLayout() {
  return (
    <div className="flex h-screen bg-canvas">
      <aside className="flex w-62 flex-none flex-col gap-4 border-r border-line bg-side px-3 py-4">
        <div className="flex items-center gap-2.5 px-1.5 py-1">
          <Logo />
          <span className="text-[15px] font-semibold">K-LINK 관리자</span>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5">
          {MENU.map((m) => (
            <NavLink
              key={m.to}
              to={m.to}
              end={m.end}
              className={({ isActive }) =>
                cx('rounded-md px-2.5 py-[9px] text-sm', isActive ? 'bg-sel font-medium text-ink' : 'text-ink-2 hover:bg-field')
              }
            >
              {m.label}
            </NavLink>
          ))}
        </nav>
        <Link to="/" className="border-t border-line px-2.5 py-[9px] text-sm text-muted hover:text-ink">
          ← 채팅으로 돌아가기
        </Link>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  )
}
