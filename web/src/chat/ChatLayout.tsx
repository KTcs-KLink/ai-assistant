import { useMemo, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Database, LogOut, Settings2 } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Avatar, cx, Logo } from '../components/ui'
import { historyGroup } from '../lib/format'
import { ChatProvider } from './ChatProvider'

const GROUP_ORDER = ['오늘', '어제', '지난 7일', '이전']

export function ChatLayout() {
  return (
    <ChatProvider>
      <div className="flex h-screen bg-canvas">
        <ChatSidebar />
        <Outlet />
      </div>
    </ChatProvider>
  )
}

function ChatSidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const { data: conversations = [] } = useQuery({ queryKey: ['conversations'], queryFn: api.listConversations })

  const groups = useMemo(() => {
    const filtered = conversations.filter((c) => c.title.toLowerCase().includes(q.trim().toLowerCase()))
    const map = new Map<string, typeof filtered>()
    for (const c of filtered) {
      const g = historyGroup(c.updatedAt)
      map.set(g, [...(map.get(g) ?? []), c])
    }
    return GROUP_ORDER.filter((g) => map.has(g)).map((g) => ({ label: g, items: map.get(g)! }))
  }, [conversations, q])

  return (
    <aside className="flex w-62 flex-none flex-col gap-4 border-r border-line bg-side px-3 py-4">
      <Link to="/" className="flex items-center gap-2.5 px-1.5 py-1">
        <Logo />
        <span className="text-[15px] font-semibold">K-LINK</span>
      </Link>
      <button
        type="button"
        onClick={() => navigate('/')}
        className="h-[38px] rounded-lg border border-line-strong bg-panel px-3 text-left text-sm font-medium hover:bg-canvas"
      >
        + 새 대화
      </button>
      <Link
        to="/original-data-demo"
        className="flex items-center gap-2 rounded-lg border border-sel-line bg-sel px-3 py-2 text-sm font-medium text-brand-strong hover:bg-sel-card"
      >
        <Database size={15} /> 우리 데이터 시연
      </Link>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="대화 검색"
        aria-label="대화 검색"
        className="h-[34px] rounded-lg bg-field px-3 text-[13px] outline-none placeholder:text-faint focus:ring-1 focus:ring-line-strong"
      />
      <nav className="-mx-1 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-1" aria-label="대화 기록">
        {groups.map((g, gi) => (
          <div key={g.label} className="flex flex-col gap-0.5">
            <div className={cx('px-2 pb-1 text-xs font-medium text-faint', gi === 0 ? 'pt-2' : 'pt-3')}>{g.label}</div>
            {g.items.map((c) => (
              <NavLink
                key={c.id}
                to={`/c/${c.id}`}
                className={({ isActive }) =>
                  cx('truncate rounded-md p-2 text-sm', isActive ? 'bg-sel font-medium text-ink' : 'text-ink-2 hover:bg-field')
                }
              >
                {c.title}
              </NavLink>
            ))}
          </div>
        ))}
        {groups.length === 0 && <div className="px-2 pt-2 text-[13px] text-faint">{q ? '검색 결과가 없어요' : '대화 기록이 없어요'}</div>}
      </nav>
      {user?.role === 'admin' && (
        <Link to="/admin" className="-mb-2 flex items-center gap-2 rounded-md px-2.5 py-2 text-sm text-ink-2 hover:bg-field">
          <Settings2 size={15} className="text-muted" />
          관리자
        </Link>
      )}
      {user && (
        <div className="flex items-center gap-2.5 border-t border-line px-1.5 py-2.5">
          <Avatar name={user.name} />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-[13px] font-medium">{user.name}</span>
            <span className="truncate text-xs text-faint">{user.dept}</span>
          </div>
          <button type="button" title="로그아웃" aria-label="로그아웃" onClick={logout} className="rounded-md p-1.5 text-faint hover:bg-field hover:text-ink">
            <LogOut size={15} />
          </button>
        </div>
      )}
    </aside>
  )
}
