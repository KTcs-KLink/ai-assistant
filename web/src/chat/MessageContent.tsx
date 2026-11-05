import { Fragment, type ReactNode } from 'react'
import type { Citation } from '../api/types'
import { cx } from '../components/ui'

interface Props {
  content: string
  citations: Citation[]
  activeCitationId?: string | null
  onCite?: (citationId: string) => void
  /** 스트리밍 중이면 끝에 커서 표시 */
  caret?: boolean
}

/** **굵게** 와 [[인용]] 마커를 해석한다. 닫히지 않은 ** 는 끝까지 굵게 처리 (스트리밍 중) */
function renderInline(text: string, props: Props, keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = []
  let bold = false
  text.split(/(\*\*|\[\[[^\]]+\]\])/).forEach((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (part === '**') {
      bold = !bold
    } else if (part.startsWith('[[') && part.endsWith(']]')) {
      const cite = props.citations.find((c) => c.id === part.slice(2, -2))
      if (cite) out.push(<CitationSup key={key} citation={cite} active={props.activeCitationId === cite.id} onClick={props.onCite} />)
    } else if (part) {
      // 스트리밍 도중 잘린 마커("[[c")는 숨긴다
      const clean = part.replace(/\[\[[^\]]*$/, '')
      out.push(bold ? <b key={key} className="font-semibold">{clean}</b> : <Fragment key={key}>{clean}</Fragment>)
    }
  })
  return out
}

export function MessageContent(props: Props) {
  const paragraphs = props.content.split(/\n{2,}/)
  return (
    <div className="flex flex-col gap-[1.1em] text-[15px] leading-[1.75] text-pretty">
      {paragraphs.map((para, pi) => {
        const lines = para.split('\n')
        const last = pi === paragraphs.length - 1
        const caret = props.caret && last && <span className="ml-0.5 inline-block h-[1.1em] w-[2px] translate-y-[3px] bg-ink-2 [animation:klblink_1s_steps(1)_infinite]" />
        if (lines.length === 1)
          return <div key={pi}>{renderInline(para, props, `${pi}`)}{caret}</div>
        return (
          <div key={pi} className="flex flex-col gap-1.5">
            {lines.map((line, li) => (
              <div key={li}>
                {renderInline(line, props, `${pi}-${li}`)}
                {li === lines.length - 1 && caret}
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

export function CitationSup({ citation, active, onClick }: { citation: Citation; active: boolean; onClick?: (id: string) => void }) {
  return (
    <sup
      role="button"
      tabIndex={0}
      title={`${citation.docName} · ${citation.section}`}
      onClick={() => onClick?.(citation.id)}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onClick?.(citation.id)}
      className={cx(
        // 줄 간격이 벌어지지 않도록 baseline 기준으로 올린다
        'relative -top-[0.45em] ml-0.5 cursor-pointer rounded px-[5px] py-px align-baseline text-[11px] leading-none font-semibold',
        active ? 'bg-brand text-white' : 'bg-sel text-brand-strong hover:bg-hl',
      )}
    >
      {citation.label}
    </sup>
  )
}

/** "[강조]" 표기를 <mark> 로 바꾼다 */
export function QuoteText({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\[[^\]]+\])/).map((p, i) =>
        p.startsWith('[') && p.endsWith(']') ? <mark key={i}>{p.slice(1, -1)}</mark> : <Fragment key={i}>{p}</Fragment>,
      )}
    </>
  )
}

/** context 안의 quote 부분만 강조 */
export function HighlightIn({ text, quote }: { text: string; quote?: string }) {
  const i = quote ? text.indexOf(quote) : -1
  if (!quote || i < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, i)}
      <mark>{quote}</mark>
      {text.slice(i + quote.length)}
    </>
  )
}
