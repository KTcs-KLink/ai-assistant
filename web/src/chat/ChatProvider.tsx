import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Attachment, Message, StreamEvent } from '../api/types'

interface StreamState {
  conversationId: string
  /** 생성 중인 답변 — 서버에 저장되기 전까지 화면에만 존재 */
  draft: Message
  /** meta 이벤트(검색 결과)를 받았는지 */
  started: boolean
}

interface ChatValue {
  stream: StreamState | null
  isStreaming: boolean
  send: (conversationId: string, text: string, attachments: Attachment[]) => Promise<void>
  regenerate: (conversationId: string, messageId: string) => Promise<void>
  stop: () => void
}

const ChatContext = createContext<ChatValue | null>(null)

export const messagesKey = (conversationId: string) => ['messages', conversationId] as const

export function ChatProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [stream, setStream] = useState<StreamState | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const run = useCallback(
    async (conversationId: string, events: (signal: AbortSignal) => AsyncGenerator<StreamEvent>) => {
      abortRef.current?.abort()
      const ctrl = new AbortController()
      abortRef.current = ctrl
      const draft: Message = { id: 'draft', role: 'assistant', content: '', citations: [], createdAt: new Date().toISOString() }
      setStream({ conversationId, draft, started: false })
      let networkError = false
      try {
        for await (const ev of events(ctrl.signal)) {
          if (ev.type === 'meta') {
            setStream((s) => s && { ...s, started: true, draft: { ...s.draft, searchNote: ev.searchNote, citations: ev.citations } })
          } else if (ev.type === 'delta') {
            setStream((s) => s && { ...s, started: true, draft: { ...s.draft, content: s.draft.content + ev.text } })
          } else if (ev.type === 'error') {
            setStream((s) => s && { ...s, draft: { ...s.draft, content: s.draft.content + `\n\n답변 생성 중 오류가 발생했습니다: ${ev.message}` } })
          }
        }
      } catch (e) {
        if (!ctrl.signal.aborted) {
          console.error('K:LINK API stream failed', e)
          networkError = true
        }
      } finally {
        if (abortRef.current === ctrl) abortRef.current = null
        // 저장된 결과로 다시 불러온 뒤 임시 답변을 지운다 (깜박임 방지)
        await Promise.all([
          qc.invalidateQueries({ queryKey: messagesKey(conversationId) }),
          qc.invalidateQueries({ queryKey: ['conversations'] }),
        ])
        if (networkError) {
          qc.setQueryData<Message[]>(messagesKey(conversationId), (prev) => [
            ...(prev ?? []),
            { id: `network-error-${Date.now()}`, role: 'assistant',
              content: '실시간 API에 연결하지 못했습니다. 서버 실행 상태와 네트워크 설정을 확인해 주세요.',
              citations: [], createdAt: new Date().toISOString() },
          ])
        }
        // 그사이 다른 답변 생성이 시작됐으면 그 상태는 건드리지 않는다
        if (!abortRef.current) setStream(null)
      }
    },
    [qc],
  )

  const send = useCallback<ChatValue['send']>(
    async (conversationId, text, attachments) => {
      const userMessage: Message = {
        id: `local-${Date.now()}`, role: 'user', content: text, citations: [], attachments, createdAt: new Date().toISOString(),
      }
      qc.setQueryData<Message[]>(messagesKey(conversationId), (prev) => [...(prev ?? []), userMessage])
      await run(conversationId, (signal) => api.sendMessage(conversationId, text, attachments, signal))
    },
    [qc, run],
  )

  const regenerate = useCallback<ChatValue['regenerate']>(
    async (conversationId, messageId) => {
      qc.setQueryData<Message[]>(messagesKey(conversationId), (prev) => prev?.filter((m) => m.id !== messageId))
      await run(conversationId, (signal) => api.regenerate(conversationId, messageId, signal))
    },
    [qc, run],
  )

  const stop = useCallback(() => abortRef.current?.abort(), [])

  return (
    <ChatContext.Provider value={{ stream, isStreaming: !!stream, send, regenerate, stop }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within ChatProvider')
  return ctx
}
