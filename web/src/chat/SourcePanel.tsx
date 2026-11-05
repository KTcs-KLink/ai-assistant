import type { Citation } from '../api/types'
import { cx } from '../components/ui'
import { HighlightIn, QuoteText } from './MessageContent'

interface Props {
  citations: Citation[]
  /** 본문에서 실제로 인용된 출처 id (나머지는 참고 문서로 회색 번호) */
  citedIds: Set<string>
  activeId: string | null
  onSelect: (id: string) => void
  onClose: () => void
}

export function SourcePanel(props: Props) {
  const attachment = props.citations.length > 0 && props.citations.every((c) => c.source === 'attachment')
  return attachment ? <AttachmentView {...props} /> : <KbView {...props} />
}

function PanelHeader({ title, onClose }: { title: string; onClose: () => void }) {
  return (
    <div className="flex h-14 flex-none items-center justify-between border-b border-line pr-3 pl-5">
      <span className="text-sm font-semibold">{title}</span>
      <button
        type="button"
        aria-label="출처 패널 닫기"
        onClick={onClose}
        className="size-8 rounded-md text-lg text-muted hover:bg-row"
      >
        ×
      </button>
    </div>
  )
}

function KbView({ citations, citedIds, activeId, onSelect, onClose }: Props) {
  return (
    <aside className="flex w-80 flex-none flex-col border-l border-line bg-panel" aria-label="출처">
      <PanelHeader title={`출처 ${citations.length}`} onClose={onClose} />
      <div className="flex flex-col gap-3 overflow-y-auto p-4">
        {citations.map((c) => {
          const active = c.id === activeId
          const cited = citedIds.has(c.id)
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => onSelect(c.id)}
              ref={(el) => { if (active) el?.scrollIntoView({ block: 'nearest' }) }}
              className={cx(
                'flex flex-col gap-2 rounded-[10px] border p-3.5 text-left transition-colors',
                active ? 'border-sel-line bg-sel-card' : 'border-line bg-panel hover:border-line-strong',
              )}
            >
              <div className="flex items-center gap-2">
                <span
                  className={cx(
                    'flex size-[18px] flex-none items-center justify-center rounded text-[11px] font-semibold',
                    cited ? 'bg-brand text-white' : 'bg-field text-ink-2',
                  )}
                >
                  {c.label}
                </span>
                <span className="truncate text-[13px] font-semibold">{c.docName}</span>
              </div>
              <div className="text-xs text-muted">{c.section}</div>
              {c.quote && (
                <div className="text-[13px] leading-[1.6] text-ink-2">
                  "<QuoteText text={c.quote} />"
                </div>
              )}
            </button>
          )
        })}
      </div>
    </aside>
  )
}

function AttachmentView({ citations, activeId, onSelect, onClose }: Props) {
  const idx = Math.max(0, citations.findIndex((c) => c.id === activeId))
  const c = citations[idx]
  const prev = citations[(idx - 1 + citations.length) % citations.length]
  const next = citations[(idx + 1) % citations.length]
  const navBtn = 'rounded-lg border border-line px-3 py-[7px] text-[13px] hover:bg-side'
  return (
    <aside className="flex w-[340px] flex-none flex-col border-l border-line bg-panel" aria-label="출처">
      <PanelHeader title={`출처 · ${c.label}`} onClose={onClose} />
      <div className="flex flex-col gap-3.5 overflow-y-auto p-5">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-semibold break-all">{c.docName}</span>
          <span className="text-xs text-faint">첨부 파일 · 이 대화에서만 사용</span>
        </div>
        <div className="flex flex-col gap-2.5 rounded-lg border border-line bg-canvas p-[18px] text-[13px] leading-[1.8] text-ink-2">
          {c.heading && <div className="font-semibold text-ink">{c.heading}</div>}
          <div>{c.context ? <HighlightIn text={c.context} quote={c.quote} /> : c.quote}</div>
        </div>
        {citations.length > 1 && (
          <div className="flex gap-2">
            <button type="button" className={navBtn} onClick={() => onSelect(prev.id)}>← {prev.label}</button>
            <button type="button" className={navBtn} onClick={() => onSelect(next.id)}>{next.label} →</button>
          </div>
        )}
      </div>
    </aside>
  )
}
