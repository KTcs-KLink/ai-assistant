import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api, API_BASE_URL, USE_MOCK } from '../api/client'
import { Card, PageHeader } from '../components/ui'
import { relativeTime } from '../lib/format'
import { CollectionStatus, feedbackMeta } from './shared'

interface RuntimeStatus {
  indexedDocuments: number
  llmConfigured: boolean
  denseReady: boolean
  supabaseConnected: boolean
}

interface SearchDiagnostic {
  intent: string
  queries: string[]
  readyDocuments: number
  indexedChunks: number
  pendingOrFailedDocuments: number
  diagnosis: string
  matches: {
    chunkId: string
    document: string
    section: string
    page: number | null
    score: number
    excerpt: string
  }[]
}

const GRID = 'grid grid-cols-[minmax(0,1.4fr)_70px_110px_90px] items-center px-[18px]'

export function OverviewPage() {
  const [days, setDays] = useState(7)
  const [probe, setProbe] = useState('급여일이 언제야?')
  const probeSearch = useMutation<SearchDiagnostic, Error, string>({
    mutationFn: async (question) => {
      const res = await fetch(
        `${API_BASE_URL}/api/admin/retrieval-debug?question=${encodeURIComponent(question)}`,
        { credentials: 'include' },
      )
      if (!res.ok) throw new Error(`검색 진단 실패 (HTTP ${res.status})`)
      return res.json()
    },
  })
  const live = useQuery<RuntimeStatus>({
    queryKey: ['live-health'],
    enabled: !USE_MOCK,
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/health`)
      if (!response.ok) throw new Error('status unavailable')
      return response.json()
    },
    refetchInterval: 10_000,
    retry: false,
  })
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
        <Card className="flex flex-col gap-3 p-[18px]">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-semibold">K:LINK 실제 구현 상태</span>
            <span className="text-xs text-muted">{USE_MOCK ? '디자인 목 모드 · 표시 수치는 예시' : live.isError ? '서버 상태 확인 실패' : '실시간 서버 상태'}</span>
          </div>
          {USE_MOCK ? (
            <p className="text-sm text-muted">실제 문서 검색을 확인하려면 VITE_USE_MOCK=false로 설정하고 FastAPI 서버를 실행하세요.</p>
          ) : (
            <div className="grid grid-cols-4 gap-3 text-sm">
              <div><div className="text-xs text-muted">색인된 실제 문서</div><strong>{live.data?.indexedDocuments ?? '–'}건</strong></div>
              <div><div className="text-xs text-muted">Dense 검색</div><strong>{live.data ? (live.data.denseReady ? '사용 가능' : '설정 필요') : '확인 중'}</strong></div>
              <div><div className="text-xs text-muted">LLM 실시간 SSE</div><strong>{live.data ? (live.data.llmConfigured ? '키 설정됨' : 'API 키 필요') : '확인 중'}</strong></div>
              <div><div className="text-xs text-muted">Supabase pgvector</div><strong>{live.data?.supabaseConnected ? '연결됨' : '미연결'}</strong></div>
            </div>
          )}
          <p className="text-xs text-muted">시연용 단일 계정 · PDF 업로드와 자동 청킹/색인 · 근거 기반 답변. 사내 SSO·부서별 권한·문서 변경 감지는 별도 구현이 필요합니다.</p>
        </Card>
        {!USE_MOCK && (
          <Card className="flex flex-col gap-3 p-[18px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-semibold">검색 디버그 · 동일 의미 질문 검증</span>
              <span className="text-xs text-muted">실제 등록 문서 인덱스 기준 · 응답 원문 생성 없음</span>
            </div>
            <form className="flex gap-2" onSubmit={(e) => {
              e.preventDefault()
              if (probe.trim()) probeSearch.mutate(probe.trim())
            }}>
              <input value={probe} onChange={(e) => setProbe(e.target.value)}
                aria-label="검색 진단 질문" maxLength={300}
                placeholder="예: 월급날은 언제야?"
                className="min-w-0 flex-1 rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-brand" />
              <button disabled={probeSearch.isPending || !probe.trim()}
                className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                type="submit">
                {probeSearch.isPending ? '검색 중…' : '실제 검색 확인'}
              </button>
            </form>
            {probeSearch.isError && <p role="alert" className="text-sm text-err">{probeSearch.error.message}</p>}
            {probeSearch.data && (
              <div className="flex flex-col gap-2">
                <p className="text-xs text-ink-2">
                  <strong>{probeSearch.data.diagnosis}</strong> · 색인 {probeSearch.data.indexedChunks}청크 /
                  문서 {probeSearch.data.readyDocuments}건 · 처리 중·실패 {probeSearch.data.pendingOrFailedDocuments}건
                </p>
                <p className="text-xs text-muted">해석된 의도: {probeSearch.data.intent} · 검색 표현: {probeSearch.data.queries.join(' / ')}</p>
                {probeSearch.data.matches.map((m) => (
                  <div key={m.chunkId} className="rounded-lg border border-line p-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <strong>{m.document}</strong>
                      <span className="text-muted">{m.section}</span>
                      <span className="text-muted">코사인 유사도 최대값 {m.score.toFixed(3)}</span>
                    </div>
                    <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-ink-2">{m.excerpt}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
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
