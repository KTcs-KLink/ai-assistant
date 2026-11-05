import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Attachment } from '../api/types'
import { useChat } from './ChatProvider'
import { Composer } from './Composer'

// 추천 질문 — 고정 문구
const SUGGESTIONS = ['경조사 휴가는 며칠이야?', '법인카드 사용 한도와 정산 방법', '재택근무 신청 절차 알려줘', '첨부한 회의록 요약해줘']

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
      <h1 className="text-[28px] font-semibold">무엇을 도와드릴까요?</h1>
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
