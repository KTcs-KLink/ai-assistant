import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { FeedbackCause, FeedbackItem } from '../api/types'
import { Button, cx } from '../components/ui'
import { relativeTime, shortDateTime } from '../lib/format'
import { feedbackMeta } from './shared'

const CAUSES: FeedbackCause[] = ['문서 누락', '검색 실패', '답변 오류', '권한 없음']

export function FeedbackPage() {
  const [params, setParams] = useSearchParams()
  const [status, setStatus] = useState<FeedbackItem['status']>('open')
  const { data = [] } = useQuery({ queryKey: ['admin', 'feedback'], queryFn: api.listFeedback })

  const list = data.filter((f) => f.status === status)
  const selectedId = params.get('id')
  const selected = data.find((f) => f.id === selectedId) ?? list[0]

  // 링크로 들어온 항목이 처리됨이면 해당 탭으로
  useEffect(() => {
    const f = data.find((x) => x.id === selectedId)
    if (f) setStatus(f.status)
  }, [data, selectedId])

  const counts = { open: data.filter((f) => f.status === 'open').length, done: data.filter((f) => f.status === 'done').length }

  return (
    <div className="grid min-h-0 flex-1 grid-cols-[380px_minmax(0,1fr)]">
      <div className="flex min-h-0 flex-col border-r border-line">
        <div className="flex h-14 flex-none items-center gap-3.5 border-b border-line px-5">
          <h1 className="text-[15px] font-semibold">답변 피드백</h1>
          {(['open', 'done'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => { setStatus(s); setParams({}) }}
              className={cx('text-[13px]', status === s ? 'font-medium text-brand-strong' : 'text-faint hover:text-ink-2')}
            >
              {s === 'open' ? '미처리' : '처리됨'} {counts[s]}
            </button>
          ))}
        </div>
        <div className="overflow-y-auto">
          {list.map((f) => {
            const on = f.id === selected?.id
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setParams({ id: f.id })}
                className={cx(
                  'flex w-full flex-col gap-1 border-b border-l-3 border-b-row px-5 py-3.5 text-left',
                  on ? 'border-l-brand bg-panel' : 'border-l-transparent hover:bg-side',
                )}
              >
                <span className={cx('text-sm', on && 'font-medium')}>{f.question}</span>
                <span className="text-xs text-faint">{feedbackMeta(f, relativeTime(f.createdAt))}</span>
              </button>
            )
          })}
          {list.length === 0 && <div className="px-5 py-8 text-sm text-faint">{status === 'open' ? '미처리 피드백이 없어요' : '처리된 피드백이 없어요'}</div>}
        </div>
      </div>
      {selected ? <FeedbackDetail key={selected.id} item={selected} /> : <div className="bg-panel" />}
    </div>
  )
}

function FeedbackDetail({ item }: { item: FeedbackItem }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [causes, setCauses] = useState(item.causes)
  const [memo, setMemo] = useState(item.memo)

  const save = useMutation({
    mutationFn: (patch: Partial<FeedbackItem>) => api.updateFeedback(item.id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'feedback'] }),
  })

  const toggleCause = (c: FeedbackCause) => {
    const next = causes.includes(c) ? causes.filter((x) => x !== c) : [...causes, c]
    setCauses(next)
    save.mutate({ causes: next })
  }

  const label = 'text-xs font-medium text-faint'
  return (
    <div className="flex min-h-0 flex-col bg-panel">
      <div className="flex h-14 flex-none items-center justify-between border-b border-line px-6">
        <span className="text-[13px] text-muted">{item.userName} · {item.dept} · {shortDateTime(item.createdAt)}</span>
        <div className="flex gap-2">
          <Button disabled={!item.conversationId} title={item.conversationId ? undefined : '원문이 보관 기간을 지났거나 접근할 수 없어요'} onClick={() => navigate(`/c/${item.conversationId}`)}>
            대화 원문 보기
          </Button>
          {item.status === 'open' ? (
            <Button variant="primary" disabled={save.isPending} onClick={() => save.mutate({ status: 'done', causes, memo })}>처리 완료</Button>
          ) : (
            <Button onClick={() => save.mutate({ status: 'open' })}>미처리로 되돌리기</Button>
          )}
        </div>
      </div>
      <div className="flex flex-col gap-5 overflow-y-auto p-6">
        <section className="flex flex-col gap-1.5">
          <span className={label}>질문</span>
          <span className="text-[15px] leading-[1.6]">{item.question}</span>
        </section>
        <section className="flex flex-col gap-1.5">
          <span className={label}>답변</span>
          <div className="rounded-lg border border-line bg-canvas p-3.5 text-sm leading-[1.7] text-ink-2">{item.answer}</div>
        </section>
        <section className="flex flex-col gap-1.5">
          <span className={label}>사원 의견</span>
          <span className={cx('text-sm leading-[1.6]', !item.comment && 'text-faint')}>{item.comment || '남긴 의견이 없어요'}</span>
        </section>
        <section className="flex flex-col gap-2 border-t border-line pt-[18px]">
          <span className={label}>원인 추정</span>
          <div className="flex flex-wrap gap-2">
            {CAUSES.map((c) => {
              const on = causes.includes(c)
              return (
                <button
                  key={c}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleCause(c)}
                  className={cx('rounded-full border px-3 py-1.5 text-[13px]', on ? 'border-sel-line bg-sel text-brand-strong' : 'border-line hover:border-line-strong')}
                >
                  {c}
                </button>
              )
            })}
          </div>
        </section>
        <section className="flex flex-col gap-1.5">
          <label htmlFor="memo" className={label}>관리자 메모</label>
          <textarea
            id="memo"
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            onBlur={() => memo !== item.memo && save.mutate({ memo })}
            placeholder="예: 해외여비 별표가 업로드 누락됨. 문서 관리에서 추가 예정"
            className="min-h-16 resize-y rounded-lg border border-line-strong p-3 text-sm outline-none placeholder:text-faint focus:border-faint"
          />
        </section>
      </div>
    </div>
  )
}
