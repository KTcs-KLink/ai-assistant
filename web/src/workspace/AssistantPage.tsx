import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Copy,
  FileCheck2,
  Gift,
  MessageSquare,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { useWorkspace } from './WorkspaceContext'
import { Brand, SourceContent } from './components'

export function AssistantPage() {
  const { benefits, messages, setMessages, select, announce } = useWorkspace()
  const [params, setParams] = useSearchParams()
  const [input, setInput] = useState(''),
    [pending, setPending] = useState(false),
    [sourceId, setSourceId] = useState<string | null>(null)
  const bottom = useRef<HTMLDivElement>(null),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const source = benefits.find((b) => b.id === sourceId)
  const selected = benefits.find((b) => b.id === params.get('benefit'))
  useEffect(() => {
    if (selected) setInput(`${selected.title}의 조건과 준비할 내용을 알려주세요.`)
  }, [selected])
  useEffect(() => {
    if (messages.length) bottom.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [messages.length])
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current)
    },
    [],
  )
  function send(text: string) {
    if (!text.trim() || pending) return
    const question = text.trim().slice(0, 1000)
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', content: question }])
    setInput('')
    setPending(true)
    const matched =
      selected ??
      benefits.find((b) => question.includes(b.title)) ??
      benefits.find((b) => question.includes('돌봄') && b.id === 'childcare') ??
      benefits.find((b) => question.includes('휴가') && b.id === 'family-leave') ??
      benefits.find((b) => /교육|자기계발|배움/.test(question) && b.id === 'learning')
    timer.current = setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        matched
          ? {
              id: crypto.randomUUID(),
              role: 'assistant',
              benefitId: matched.id,
              content: `예시 규정에서 확인한 내용을 안내해 드릴게요.\n\n${matched.quote.replace('[가상 규정] ', '')}\n\n신청을 준비하기 전에 다음 내용을 확인해 주세요.\n${matched.checklist.map((c, i) => `${i + 1}. ${c}`).join('\n')}\n\n실제 회사의 혜택과 자격은 승인된 규정에서 확인해야 해요.`,
            }
          : {
              id: crypto.randomUUID(),
              role: 'assistant',
              content:
                '지금은 대화 흐름을 살펴보는 디자인 미리보기예요. 이 질문에 답할 수 있는 회사 규정은 연결 전이라 정확한 답변을 드릴 수 없어요.\n\n아래 예시 질문으로 규정 근거를 확인하는 흐름을 체험하거나, 규정·양식에서 필요한 업무를 찾아보세요.',
            },
      ])
      setPending(false)
      timer.current = null
    }, 450)
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    send(input)
  }
  function newConversation() {
    if (timer.current) clearTimeout(timer.current)
    setPending(false)
    setMessages([])
    setSourceId(null)
    setInput('')
    setParams({})
  }
  return (
    <div className={`kl-assistant-page ${source ? 'with-source' : ''}`}>
      <section className="kl-chat-main">
        <div className="kl-chat-top">
          <div>
            <span className="kl-ai-dot" />
            <strong>AI 어시스턴트</strong>
            <span className="kl-tag">예시 응답</span>
          </div>
          <button className="kl-subtle-button" onClick={newConversation}>
            <Plus size={15} />새 대화
          </button>
        </div>
        <div className="kl-chat-scroll">
          {!messages.length ? (
            <div className="kl-chat-welcome">
              <span className="kl-chat-orb">
                <Sparkles size={35} strokeWidth={1.5} />
              </span>
              <span className="kl-eyebrow">YOUR WORK, CONNECTED</span>
              <h1>궁금한 업무가 있나요?</h1>
              <p>
                회사 규정부터 신청 준비까지,
                <br />
                근거를 함께 확인하며 이해해요.
              </p>
              <div className="kl-chat-prompts">
                {[
                  {
                    text: '자녀 돌봄 지원금 조건이 궁금해요',
                    caption: '나와 가족을 위한 혜택',
                    icon: Gift,
                  },
                  {
                    text: '가족 돌봄 휴가를 어떻게 준비하나요?',
                    caption: '휴가와 필요한 절차',
                    icon: FileCheck2,
                  },
                  {
                    text: '자기계발 지원은 어떤 제도인가요?',
                    caption: '배움과 성장의 기회',
                    icon: BookOpen,
                  },
                ].map(({ text, caption, icon: Icon }) => (
                  <button key={text} onClick={() => send(text)}>
                    <Icon size={20} />
                    <strong>{text}</strong>
                    <span>
                      {caption}
                      <ArrowRight size={14} />
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="kl-chat-messages">
              {messages.map((message) => (
                <div className={`kl-chat-message ${message.role}`} key={message.id}>
                  {message.role === 'assistant' && (
                    <span className="kl-message-avatar">
                      <Sparkles size={17} />
                    </span>
                  )}
                  <div className="kl-message-body">
                    {message.role === 'assistant' && (
                      <div className="kl-message-author">
                        K:LINK<span>예시 답변</span>
                      </div>
                    )}
                    <div className="kl-message-text">{message.content}</div>
                    {message.benefitId && (
                      <>
                        <button
                          className="kl-citation"
                          onClick={() => setSourceId(message.benefitId!)}
                        >
                          <BookOpen size={14} />
                          <span>1</span>가상 복지 규정 ·{' '}
                          {benefits.find((b) => b.id === message.benefitId)?.section}
                          <ChevronRight size={13} />
                        </button>
                        <button className="kl-chat-next" onClick={() => select(message.benefitId!)}>
                          혜택 조건과 준비 목록 확인
                          <ArrowRight size={15} />
                        </button>
                      </>
                    )}
                    {message.role === 'assistant' && (
                      <div className="kl-message-tools">
                        <button
                          className="kl-icon-button"
                          aria-label="답변 복사"
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(message.content)
                              announce('예시 답변을 복사했어요.')
                            } catch {
                              announce('복사할 내용을 직접 선택해 주세요.')
                            }
                          }}
                        >
                          <Copy size={14} />
                        </button>
                        <span>근거와 함께 확인해 주세요.</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {pending && (
                <div className="kl-answer-pending" role="status">
                  <Sparkles size={16} />
                  <span>예시 내용을 불러오고 있어요</span>
                  <i />
                  <i />
                  <i />
                </div>
              )}
              <div ref={bottom} />
            </div>
          )}
        </div>
        <form className="kl-chat-composer" onSubmit={submit}>
          <div>
            <textarea
              aria-label="AI에게 질문하기"
              placeholder="궁금한 업무를 물어보세요. 예: 가족 돌봄 휴가를 준비하려면?"
              rows={2}
              maxLength={1000}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault()
                  send(input)
                }
              }}
            />
            <div className="kl-composer-bottom">
              <span>
                <ShieldCheck size={12} />
                디자인 미리보기 · 실제 개인정보 입력 금지
              </span>
              <button aria-label="질문 보내기" type="submit" disabled={!input.trim() || pending}>
                <Send size={17} />
              </button>
            </div>
          </div>
          <p>현재는 예시 답변을 표시하며 외부 AI에 질문이나 직원 정보를 전송하지 않아요.</p>
        </form>
      </section>
      {source && (
        <aside className="kl-chat-source">
          <div>
            <h2>
              <BookOpen size={17} />
              답변의 근거
            </h2>
            <button
              className="kl-icon-button"
              aria-label="근거 패널 닫기"
              onClick={() => setSourceId(null)}
            >
              <X size={18} />
            </button>
          </div>
          <SourceContent benefit={source} />
          <button className="kl-button secondary full" onClick={() => select(source.id)}>
            혜택 상세 보기
            <ArrowRight size={15} />
          </button>
        </aside>
      )}
      <div className="kl-chat-mobile-links">
        <Link to="/workspace/library">
          <MessageSquare size={14} />
          규정·양식도 찾아볼 수 있어요
          <ChevronRight size={13} />
        </Link>
        <span>
          <Check size={12} />
          예시 응답
        </span>
        <span className="kl-sr-only">
          <Brand />
        </span>
      </div>
    </div>
  )
}
