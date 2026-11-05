import { useEffect, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Settings } from '../api/types'
import { Button, Card, cx, PageHeader, Spinner, Toggle } from '../components/ui'

const FORMATS = ['PDF', 'DOCX', 'XLSX', 'PPTX']

export function SettingsPage() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['admin', 'settings'], queryFn: api.getSettings })
  const [draft, setDraft] = useState<Settings | null>(null)
  const [savedAt, setSavedAt] = useState(false)

  useEffect(() => {
    if (data) setDraft(data)
  }, [data])

  const save = useMutation({
    mutationFn: api.saveSettings,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'settings'] })
      setSavedAt(true)
      setTimeout(() => setSavedAt(false), 2000)
    },
  })

  const dirty = !!data && !!draft && JSON.stringify(data) !== JSON.stringify(draft)
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setDraft((d) => d && { ...d, [k]: v })

  return (
    <>
      <PageHeader title="설정">
        <div className="flex items-center gap-3">
          {savedAt && <span className="text-[13px] text-ok">저장했어요</span>}
          <Button variant="primary" className="px-3.5 py-[7px]" disabled={!dirty || save.isPending} onClick={() => draft && save.mutate(draft)}>
            변경사항 저장
          </Button>
        </div>
      </PageHeader>
      {!draft ? (
        <Spinner />
      ) : (
        <div className="grid flex-1 grid-cols-2 content-start gap-4 overflow-auto px-7 py-6">
          <Section title="AI 답변">
            <Row label="사용 모델" hint="사내 서버에 연결된 모델">
              <Select value={draft.model} onChange={(v) => set('model', v)} options={['K-LLM 2.1', 'K-LLM 2.0', 'K-LLM 2.1 Lite']} />
            </Row>
            <Row label="출처가 없으면 답변하지 않기" hint={'사내 문서에 근거가 없을 때 "찾지 못함"으로 안내'}>
              <Toggle label="출처가 없으면 답변하지 않기" checked={draft.refuseWithoutSource} onChange={(v) => set('refuseWithoutSource', v)} />
            </Row>
          </Section>

          <Section title="첨부 파일">
            <Row label="사원 파일 첨부 허용" hint="첨부 파일은 해당 대화에서만 쓰여요">
              <Toggle label="사원 파일 첨부 허용" checked={draft.allowAttachments} onChange={(v) => set('allowAttachments', v)} />
            </Row>
            <Row label="허용 형식">
              <div className="flex gap-1.5">
                {FORMATS.map((f) => {
                  const on = draft.formats.includes(f)
                  return (
                    <button
                      key={f}
                      type="button"
                      aria-pressed={on}
                      disabled={!draft.allowAttachments}
                      onClick={() => set('formats', on ? draft.formats.filter((x) => x !== f) : [...draft.formats, f])}
                      className={cx('rounded-[5px] px-2 py-1 text-xs disabled:opacity-50', on ? 'bg-row text-ink' : 'border border-dashed border-line-strong text-faint')}
                    >
                      {f}
                    </button>
                  )
                })}
              </div>
            </Row>
            <Row label="파일당 최대 크기">
              <Select value={draft.maxSizeMb} onChange={(v) => set('maxSizeMb', v)} options={[10, 20, 50, 100]} format={(v) => `${v} MB`} disabled={!draft.allowAttachments} />
            </Row>
          </Section>

          <Section title="데이터 보관">
            <Row label="대화 기록 보관 기간" hint="기간이 지나면 자동 삭제">
              <Select value={draft.chatRetentionDays} onChange={(v) => set('chatRetentionDays', v)} options={[30, 90, 180, 365]} format={(v) => `${v}일`} />
            </Row>
            <Row label="첨부 파일 보관 기간" hint="대화가 끝난 뒤 기준">
              <Select value={draft.attachmentRetentionDays} onChange={(v) => set('attachmentRetentionDays', v)} options={[1, 7, 30]} format={(v) => `${v}일`} />
            </Row>
          </Section>
        </div>
      )}
    </>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="flex flex-col">
      <div className="border-b border-line px-5 py-4 text-sm font-semibold">{title}</div>
      {/* 같은 줄 카드 높이를 맞추기 위해 각 행이 남는 높이를 나눠 가진다 */}
      <div className="flex flex-1 flex-col [&>*:not(:last-child)]:border-b [&>*:not(:last-child)]:border-row">{children}</div>
    </Card>
  )
}

function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-1 items-center justify-between gap-4 px-5 py-4">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm">{label}</span>
        {hint && <span className="text-xs text-faint">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function Select<T extends string | number>({ value, onChange, options, format = String, disabled }: {
  value: T
  onChange: (v: T) => void
  options: T[]
  format?: (v: T) => string
  disabled?: boolean
}) {
  return (
    <select
      value={String(value)}
      disabled={disabled}
      onChange={(e) => onChange(options.find((o) => String(o) === e.target.value)!)}
      className="rounded-lg border border-line-strong bg-panel px-3 py-[7px] text-[13px] whitespace-nowrap disabled:opacity-50"
    >
      {options.map((o) => <option key={String(o)} value={String(o)}>{format(o)}</option>)}
    </select>
  )
}
