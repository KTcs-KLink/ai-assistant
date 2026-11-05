import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { Card, PageHeader } from '../components/ui'
import { relativeTime } from '../lib/format'
import { CollectionStatus, feedbackMeta } from './shared'

const GRID = 'grid grid-cols-[minmax(0,1.4fr)_70px_110px_90px] items-center px-[18px]'

export function OverviewPage() {
  const [days, setDays] = useState(7)
  const stats = useQuery({ queryKey: ['admin', 'stats', days], queryFn: () => api.getStats(days) })
  const collections = useQuery({ queryKey: ['admin', 'collections'], queryFn: api.listCollections })
  const feedback = useQuery({ queryKey: ['admin', 'feedback'], queryFn: api.listFeedback })
  const recent = (feedback.data ?? []).filter((f) => f.status === 'open').slice(0, 3)

  const s = stats.data
  const tiles = [
    { label: '질문 수', value: s?.questions.toLocaleString() },
    { label: '활성 사용자', value: s?.activeUsers.toLocaleString() },
    { label: '"도움이 됨" 비율', value: s && `${s.helpfulRate}%` },
  ]

  return (
    <>
      <PageHeader title="개요">
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          aria-label="기간"
          className="rounded-md border border-line bg-panel px-3 py-1.5 text-[13px] text-ink-2"
        >
          <option value={7}>최근 7일</option>
          <option value={30}>최근 30일</option>
        </select>
      </PageHeader>
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-auto px-7 py-6">
        <div className="grid grid-cols-3 gap-4">
          {tiles.map((t) => (
            <Card key={t.label} className="flex flex-col gap-1.5 p-[18px]">
              <span className="text-[13px] text-muted">{t.label}</span>
              <span className="text-[26px] font-semibold">{t.value ?? '–'}</span>
            </Card>
          ))}
        </div>
        <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] items-start gap-4">
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-[18px] py-4">
              <span className="text-sm font-semibold">문서 컬렉션</span>
              <Link to="/admin/documents" className="rounded-md bg-brand px-3 py-1.5 text-[13px] text-white hover:bg-brand-strong">+ 문서 추가</Link>
            </div>
            <div className={`${GRID} border-b border-row py-2.5 text-xs text-faint`}>
              <span>이름</span><span>문서</span><span>마지막 동기화</span><span>상태</span>
            </div>
            {collections.data?.map((c) => (
              <div key={c.id} className={`${GRID} border-b border-row py-3 text-sm last:border-b-0`}>
                <span>{c.name}</span>
                <span>{c.docCount}</span>
                <span className="text-muted">{c.lastSync ?? '진행 중'}</span>
                <CollectionStatus c={c} />
              </div>
            ))}
          </Card>
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-[18px] py-4">
              <span className="text-sm font-semibold">"개선 필요" 피드백</span>
              <Link to="/admin/feedback" className="text-[13px] text-muted hover:text-ink">전체 보기</Link>
            </div>
            {recent.map((f) => (
              <Link
                key={f.id}
                to={`/admin/feedback?id=${f.id}`}
                className="flex flex-col gap-1 border-b border-row px-[18px] py-3.5 last:border-b-0 hover:bg-canvas"
              >
                <span className="text-sm">{f.question}</span>
                <span className="text-xs text-faint">{feedbackMeta(f, relativeTime(f.createdAt))}</span>
              </Link>
            ))}
            {feedback.data && recent.length === 0 && <div className="px-[18px] py-6 text-sm text-faint">미처리 피드백이 없어요</div>}
          </Card>
        </div>
      </div>
    </>
  )
}
