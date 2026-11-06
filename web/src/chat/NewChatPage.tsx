import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api, USE_MOCK } from '../api/client'
import type { Attachment } from '../api/types'
import { useChat } from './ChatProvider'
import { Composer } from './Composer'

// 추천 질문 — 고정 문구
const SUGGESTIONS = ['휴가 신청 절차와 증빙 서류를 알려줘', '출장비 정산에 필요한 서류는?', '퇴직할 때 제출해야 하는 서류는?', '업로드한 규정에서 관련 조항을 찾아줘']

export function NewChatPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { send } = useChat()

  const start = async (text: string, attachments: Attachment[] = []) => {
    const title = text.length > 24 ? `${text.slice(0, 24)}…` : text
    const conv = await api.createConversation(title)
    await qc.invalidateQueries({ queryKey: ['conversations'] })
    void send(conv.id, text, attachments)
    navigate(`/c/${conv.id}`)
  }

  return (
    <main className="flex min-w-0 flex-1 flex-col items-center justify-center gap-7 p-10">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-[28px] font-semibold">무엇을 도와드릴까요?</h1>
        <p className="max-w-[600px] text-sm text-muted">등록된 문서에서 근거를 찾아 실시간으로 답합니다. 문서에 없는 내용은 임의로 만들지 않습니다.</p>
        <p role="status" className="text-xs text-muted">{USE_MOCK ? '디자인 시연 모드 · 예시 답변 (실제 RAG 아님)' : '실제 RAG API 모드 · 검색 근거와 출처 표시'}</p>
      </div>
      <div className="w-full max-w-[680px]">
        <Composer variant="hero" placeholder="사내 규정, 업무 절차, 첨부한 파일에 대해 물어보세요" onSend={start} />
      </div>
      <div className="grid w-full max-w-[680px] grid-cols-2 gap-2.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => start(s)}
            className="rounded-[10px] border border-line bg-panel px-3.5 py-3 text-left text-sm text-ink-2 transition-colors hover:border-line-strong"
          >
            {s}
          </button>
        ))}
      </div>
    </main>
  )
}
