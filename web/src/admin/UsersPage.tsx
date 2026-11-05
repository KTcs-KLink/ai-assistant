import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Department, PermissionException } from '../api/types'
import { Badge, Button, Card, Checkbox, cx, PageHeader } from '../components/ui'
import { relativeTime } from '../lib/format'

type Tab = 'perms' | 'users' | 'admins'

export function UsersPage() {
  const [tab, setTab] = useState<Tab>('perms')
  const users = useQuery({ queryKey: ['admin', 'users'], queryFn: api.listUsers })
  const list = users.data ?? []
  const admins = list.filter((u) => u.role === 'admin')

  const tabs: { id: Tab; label: string }[] = [
    { id: 'perms', label: '부서별 권한' },
    { id: 'users', label: `사용자 목록 ${list.length || ''}` },
    { id: 'admins', label: `관리자 ${admins.length || ''}` },
  ]

  return (
    <>
      <PageHeader title="사용자 · 권한" />
      <div className="mx-7 flex gap-5 border-b border-line pt-5" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cx('-mb-px pb-3 text-sm', tab === t.id ? 'border-b-2 border-ink font-semibold' : 'text-faint hover:text-ink-2')}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'perms' && <PermissionsTab />}
      {tab !== 'perms' && (
        <div className="min-h-0 flex-1 overflow-auto px-7 pt-5 pb-6">
          <Card className="overflow-hidden">
            <div className="grid grid-cols-[minmax(0,1fr)_140px_minmax(0,1.4fr)_90px_110px] px-[18px] py-[11px] text-xs text-faint border-b border-line">
              <span>이름</span><span>부서</span><span>이메일</span><span>역할</span><span>최근 사용</span>
            </div>
            {(tab === 'admins' ? admins : list).map((u) => (
              <div key={u.id} className="grid grid-cols-[minmax(0,1fr)_140px_minmax(0,1.4fr)_90px_110px] items-center border-b border-row px-[18px] py-3 text-sm last:border-b-0">
                <span className="font-medium">{u.name}</span>
                <span className="text-ink-2">{u.dept}</span>
                <span className="truncate text-muted">{u.email}</span>
                {u.role === 'admin' ? <Badge tone="brand">관리자</Badge> : <span className="text-ink-2">사원</span>}
                <span className="text-muted">{relativeTime(u.lastActiveAt)}</span>
              </div>
            ))}
          </Card>
        </div>
      )}
    </>
  )
}

const MATRIX = 'grid grid-cols-[minmax(0,1.4fr)_70px_repeat(4,90px)] items-center px-[18px]'

function PermissionsTab() {
  const qc = useQueryClient()
  const collections = useQuery({ queryKey: ['admin', 'collections'], queryFn: api.listCollections })
  const depts = useQuery({ queryKey: ['admin', 'departments'], queryFn: api.listDepartments })
  const exceptions = useQuery({ queryKey: ['admin', 'exceptions'], queryFn: api.listExceptions })
  const [adding, setAdding] = useState(false)

  const setPerm = useMutation({
    mutationFn: (v: { deptId: string; collectionId: string; allowed: boolean }) => api.setDepartmentPermission(v.deptId, v.collectionId, v.allowed),
    onMutate: (v) =>
      qc.setQueryData<Department[]>(['admin', 'departments'], (prev) =>
        prev?.map((d) => (d.id === v.deptId ? { ...d, perms: { ...d.perms, [v.collectionId]: v.allowed } } : d)),
      ),
    onSettled: () => qc.invalidateQueries({ queryKey: ['admin', 'departments'] }),
  })
  const removeEx = useMutation({ mutationFn: api.removeException, onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'exceptions'] }) })

  const cols = collections.data ?? []
  const colName = (id: string) => cols.find((c) => c.id === id)?.name ?? id

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_340px] items-start gap-4 px-7 pt-5 pb-6">
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-0.5 border-b border-line px-[18px] py-3.5">
          <span className="text-sm font-semibold">기본 권한 (부서 단위)</span>
          <span className="text-xs text-faint">부서에 속한 모든 사람에게 적용돼요</span>
        </div>
        <div className={`${MATRIX} border-b border-line py-[11px] text-center text-xs text-faint`}>
          <span className="text-left">부서</span>
          <span className="text-left">인원</span>
          {cols.map((c) => <span key={c.id}>{c.name}</span>)}
        </div>
        {depts.data?.map((d) => (
          <div key={d.id} className={`${MATRIX} border-b border-row py-3 text-sm last:border-b-0`}>
            <span>{d.name}</span>
            <span className="text-muted">{d.headcount}명</span>
            {cols.map((c) => (
              <Checkbox
                key={c.id}
                label={`${d.name} ${c.name}`}
                checked={!!d.perms[c.id]}
                onChange={(allowed) => setPerm.mutate({ deptId: d.id, collectionId: c.id, allowed })}
              />
            ))}
          </div>
        ))}
      </Card>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-[18px] py-3.5">
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-semibold">개인 예외</span>
            <span className="text-xs text-faint">부서 권한에 추가하거나 제외</span>
          </div>
          <Button onClick={() => setAdding((v) => !v)}>+ 추가</Button>
        </div>
        {adding && <ExceptionForm collections={cols} onDone={() => setAdding(false)} />}
        {exceptions.data?.map((e) => (
          <div key={e.id} className="group flex flex-col gap-1.5 border-b border-row px-[18px] py-[13px] last:border-b-0">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">
                {e.userName} <span className="text-[13px] font-normal text-faint">{e.dept}</span>
              </span>
              <Badge tone={e.type === 'add' ? 'ok' : 'err'}>{e.type === 'add' ? '+' : '−'} {colName(e.collectionId)}</Badge>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-faint">{[e.reason, e.until && `${e.until}까지`].filter(Boolean).join(' · ')}</span>
              <button
                type="button"
                onClick={() => removeEx.mutate(e.id)}
                className="text-xs text-faint opacity-0 group-hover:opacity-100 hover:text-err focus:opacity-100"
              >
                삭제
              </button>
            </div>
          </div>
        ))}
      </Card>
    </div>
  )
}

function ExceptionForm({ collections, onDone }: { collections: { id: string; name: string }[]; onDone: () => void }) {
  const qc = useQueryClient()
  const users = useQuery({ queryKey: ['admin', 'users'], queryFn: api.listUsers })
  const [form, setForm] = useState({ userId: '', collectionId: collections[0]?.id ?? '', type: 'add' as PermissionException['type'], reason: '', until: '' })
  const add = useMutation({
    mutationFn: () => {
      const u = users.data!.find((x) => x.id === form.userId)!
      return api.addException({
        userName: u.name, dept: u.dept, collectionId: form.collectionId, type: form.type,
        reason: form.reason.trim(), until: form.until.trim() || undefined,
      })
    },
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['admin', 'exceptions'] }); onDone() },
  })
  const field = 'h-8 rounded-md border border-line-strong bg-panel px-2 text-[13px] outline-none'
  return (
    <form
      className="flex flex-col gap-2 border-b border-line bg-canvas px-[18px] py-3.5"
      onSubmit={(e) => { e.preventDefault(); if (form.userId) add.mutate() }}
    >
      <select className={field} value={form.userId} onChange={(e) => setForm({ ...form, userId: e.target.value })} aria-label="사용자">
        <option value="">사용자 선택</option>
        {users.data?.map((u) => <option key={u.id} value={u.id}>{u.name} · {u.dept}</option>)}
      </select>
      <div className="flex gap-2">
        <select className={`${field} w-20`} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as 'add' | 'remove' })} aria-label="유형">
          <option value="add">+ 추가</option>
          <option value="remove">− 제외</option>
        </select>
        <select className={`${field} flex-1`} value={form.collectionId} onChange={(e) => setForm({ ...form, collectionId: e.target.value })} aria-label="컬렉션">
          {collections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      <div className="flex gap-2">
        <input className={`${field} flex-1`} placeholder="사유" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
        <input className={`${field} w-24`} placeholder="기간 (12.31)" value={form.until} onChange={(e) => setForm({ ...form, until: e.target.value })} />
      </div>
      <div className="flex justify-end gap-1.5">
        <Button type="button" onClick={onDone}>취소</Button>
        <Button type="submit" variant="primary" disabled={!form.userId || add.isPending}>저장</Button>
      </div>
    </form>
  )
}
