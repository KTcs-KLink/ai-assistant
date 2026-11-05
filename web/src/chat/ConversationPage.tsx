import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Attachment, Feedback, Message } from '../api/types'
import { cx } from '../components/ui'
import { formatBytes } from '../lib/format'
import { messagesKey, useChat } from './ChatProvider'
import { Composer } from './Composer'
import { MessageContent } from './MessageContent'
import { SourcePanel } from './SourcePanel'

interface PanelState {
  open: boolean
  messageId: string | null
  citationId: string | null
}

// 첨부 파일은 쪽이 여러 개여도 파일 하나를 출처 1건으로 센다
const sourceCount = (m: Message) =>
  m.citations.every((c) => c.source === 'attachment') ? new Set(m.citations.map((c) => c.docName)).size : m.citations.length

const citedIdsOf = (m: Message) => new Set([...m.content.matchAll(/\[\[([^\]]+)\]\]/g)].map((x) => x[1]))

export function ConversationPage() {
  const { id = '' } = useParams()
  // 대화를 바꾸면 패널 등 화면 상태를 초기화
  return <Conversation key={id} id={id} />
}

function Conversation({ id }: { id: string }) {
  const { stream, isStreaming, send, regenerate, stop } = useChat()
  const { data: conversations } = useQuery({ queryKey: ['conversations'], queryFn: api.listConversations })
  const { data: saved = [], isLoading, isError } = useQuery({
    queryKey: messagesKey(id),
    queryFn: () => api.getMessages(id),
    staleTime: 30_000,
  })
  const [panel, setPanel] = useState<PanelState>({ open: false, messageId: null, citationId: null })
  const scroller = useRef<HTMLDivElement>(null)

  const streamingHere = stream?.conversationId === id ? stream : null
  const messages = streamingHere ? [...saved, streamingHere.draft] : saved
  const title = conversations?.find((c) => c.id === id)?.title ?? ''

  // 출처 패널 대상: 선택한 답변, 없으면 출처가 있는 마지막 답변
  const panelMessage = useMemo(
    () =>
      messages.find((m) => m.id === panel.messageId) ??
      [...messages].reverse().find((m) => m.role === 'assistant' && m.citations.length > 0),
    [messages, panel.messageId],
  )
  const hasAttachments = saved.some((m) => m.attachments?.length)

  useEffect(() => {
    const el = scroller.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages.length, streamingHere?.draft.content])

  const openCitation = (messageId: string, citationId: string) => setPanel({ open: true, messageId, citationId })

  const lastAssistantId = [...saved].reverse().find((m) => m.role === 'assistant')?.id

  return (
    <>
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 flex-none items-center justify-between gap-4 border-b border-line px-6">
          <h1 className="truncate text-[15px] font-semibold">{title}</h1>
          {panelMessage && (
            <button
              type="button"
              aria-pressed={panel.open}
              onClick={() => setPanel((p) => (p.open ? { ...p, open: false, citationId: null } : { ...p, open: true }))}
              className={cx(
                'flex-none rounded-md border px-3 py-1.5 text-[13px] font-medium',
                panel.open ? 'border-sel-line bg-sel text-brand-strong' : 'border-line bg-panel text-ink-2 hover:bg-side',
              )}
            >
              출처 {sourceCount(panelMessage)}
            </button>
          )}
        </header>

        <div ref={scroller} className="flex-1 overflow-y-auto px-10 py-7">
          <div className="mx-auto flex max-w-[860px] flex-col gap-6">
            {isLoading && <div className="text-sm text-faint">불러오는 중…</div>}
            {isError && <div className="text-sm text-err">대화를 불러오지 못했어요.</div>}
            {messages.map((m) =>
              m.role === 'user' ? (
                <UserMessage key={m.id} message={m} />
              ) : (
                <AssistantMessage
                  key={m.id}
                  conversationId={id}
                  message={m}
                  isDraft={m.id === 'draft'}
                  searching={m.id === 'draft' && !streamingHere?.started}
                  activeCitationId={panel.open && panelMessage?.id === m.id ? panel.citationId : null}
                  onCite={(cid) => openCitation(m.id, cid)}
                  onRegenerate={m.id === lastAssistantId && !isStreaming ? () => regenerate(id, m.id) : undefined}
                />
              ),
            )}
          </div>
        </div>

        <div className="px-10 pb-6">
          <div className="mx-auto max-w-[860px]">
            <Composer
              variant="dock"
              placeholder={hasAttachments ? '이 파일에 대해 더 물어보기' : '메시지를 입력하세요'}
              isStreaming={isStreaming}
              onStop={stop}
              onSend={(text, attachments) => send(id, text, attachments)}
            />
          </div>
        </div>
      </main>

      {panel.open && panelMessage && (
        <SourcePanel
          citations={panelMessage.citations}
          citedIds={citedIdsOf(panelMessage)}
          activeId={panel.citationId}
          onSelect={(cid) => openCitation(panelMessage.id, cid)}
          onClose={() => setPanel({ open: false, messageId: null, citationId: null })}
        />
      )}
    </>
  )
}

function UserMessage({ message }: { message: Message }) {
  return (
    <div className="flex max-w-[440px] flex-col items-end gap-2 self-end">
      {message.attachments?.map((a) => <FileCard key={a.id} file={a} />)}
      <div className="rounded-[14px] bg-bubble px-4 py-3 text-[15px] leading-[1.6] break-words whitespace-pre-wrap">{message.content}</div>
    </div>
  )
}

function FileCard({ file }: { file: Attachment }) {
  const ext = file.name.split('.').pop()?.toUpperCase().slice(0, 4) ?? 'FILE'
  return (
    <div className="flex items-center gap-2.5 rounded-[10px] border border-line bg-panel px-3 py-2.5">
      <div className="flex h-[38px] w-8 flex-none items-center justify-center rounded bg-sel text-[10px] font-semibold text-brand-strong">{ext}</div>
      <div className="flex min-w-0 flex-col">
        <span className="truncate text-[13px] font-medium">{file.name}</span>
        <span className="text-xs text-faint">{[file.pages && `${file.pages}쪽`, formatBytes(file.size)].filter(Boolean).join(' · ')}</span>
      </div>
    </div>
  )
}

interface AssistantProps {
  conversationId: string
  message: Message
  isDraft: boolean
  searching: boolean
  activeCitationId: string | null
  onCite: (citationId: string) => void
  onRegenerate?: () => void
}

function AssistantMessage({ conversationId, message, isDraft, searching, activeCitationId, onCite, onRegenerate }: AssistantProps) {
  const qc = useQueryClient()
  const [copied, setCopied] = useState(false)
  const [askComment, setAskComment] = useState(false)
  const [comment, setComment] = useState('')

  const setFeedback = async (value: Feedback, text?: string) => {
    qc.setQueryData<Message[]>(messagesKey(conversationId), (prev) => prev?.map((m) => (m.id === message.id ? { ...m, feedback: value } : m)))
    await api.setFeedback(conversationId, message.id, value, text)
  }

  const copy = async () => {
    await navigator.clipboard.writeText(message.content.replace(/\[\[[^\]]+\]\]|\*\*/g, ''))
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const action = (on = false) =>
    cx('rounded-md border px-2.5 py-1 text-xs', on ? 'border-sel-line bg-sel text-brand-strong' : 'border-line text-muted hover:bg-side')

  return (
    <div className="flex max-w-[600px] flex-col gap-3">
      {(message.searchNote || searching) && <div className="text-[13px] text-muted">{searching ? '사내 문서를 검색하는 중…' : message.searchNote}</div>}
      {message.content && (
        <MessageContent content={message.content} citations={message.citations} activeCitationId={activeCitationId} onCite={onCite} caret={isDraft} />
      )}
      {!isDraft && (
        <div className="flex flex-wrap gap-1.5">
          <button type="button" className={action()} onClick={copy}>{copied ? '복사됨' : '복사'}</button>
          {onRegenerate && <button type="button" className={action()} onClick={onRegenerate}>다시 생성</button>}
          <button
            type="button"
            className={action(message.feedback === 'up')}
            aria-pressed={message.feedback === 'up'}
            onClick={() => { setAskComment(false); void setFeedback(message.feedback === 'up' ? null : 'up') }}
          >
            도움이 됨
          </button>
          <button
            type="button"
            className={action(message.feedback === 'down' || askComment)}
            aria-pressed={message.feedback === 'down'}
            onClick={() => (message.feedback === 'down' ? setFeedback(null) : setAskComment((v) => !v))}
          >
            개선 필요
          </button>
        </div>
      )}
      {askComment && (
        <form
          className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3"
          onSubmit={(e) => {
            e.preventDefault()
            setAskComment(false)
            void setFeedback('down', comment.trim())
            setComment('')
          }}
        >
          <textarea
            autoFocus
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="어떤 점이 아쉬웠나요? (선택) 관리자가 확인 후 문서를 보완해요"
            className="resize-none text-sm leading-[1.6] outline-none placeholder:text-faint"
          />
          <div className="flex justify-end gap-1.5">
            <button type="button" className={action()} onClick={() => setAskComment(false)}>취소</button>
            <button type="submit" className="rounded-md bg-brand px-2.5 py-1 text-xs font-medium text-white hover:bg-brand-strong">보내기</button>
          </div>
        </form>
      )}
    </div>
  )
}
