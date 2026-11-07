import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  FileCheck2,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { Heading, Note, Source } from "./ui";

export function Assistant() {
  const { benefits, messages, setMessages, startPreparation } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const selected = benefits.find(
    (benefit) => benefit.id === params.get("benefit"),
  );
  const [input, setInput] = useState(
    selected ? `${selected.title}의 조건과 준비할 내용을 알려주세요.` : "",
  );
  const [sourceId, setSourceId] = useState<string | null>(null);
  const source = benefits.find((benefit) => benefit.id === sourceId);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (selected)
      setInput(`${selected.title}의 조건과 준비할 내용을 알려주세요.`);
  }, [selected?.title]);
  useEffect(() => {
    if (messages.length) bottom.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length]);
  // This is a deterministic local fixture, not a model call or a production answer.
  function send(question: string) {
    const text = question.trim().slice(0, 1000);
    if (!text) return;
    const match =
      benefits.find((benefit) => text.includes(benefit.title)) ??
      benefits.find(
        (benefit) => /휴가/.test(text) && benefit.id === "family-leave",
      ) ??
      benefits.find(
        (benefit) => /돌봄/.test(text) && benefit.id === "childcare",
      ) ??
      benefits.find(
        (benefit) =>
          /교육|배움|자기계발/.test(text) && benefit.id === "learning",
      );
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: text },
      {
        id: crypto.randomUUID(),
        role: "assistant",
        ...(match ? { benefitId: match.id } : {}),
        content: match
          ? `가상 규정에 따른 예시 안내입니다.\n\n${match.quote.replace("[가상 규정] ", "")}\n\n현재 가상 조건의 확인 결과\n${match.reason}\n\n준비하기 전에 확인하세요\n${match.checklist.map((item, index) => `${index + 1}. ${item}`).join("\n")}\n\n실제 KTcs의 제도·자격·금액은 승인된 회사 규정에서 별도로 확인해야 합니다.`
          : "이 질문에 답할 수 있는 회사 규정이 연결되지 않았습니다. 현재는 화면 흐름을 위한 고정 예시 답변만 제공해요.\n\n자녀 돌봄, 가족 돌봄 휴가, 자기계발 지원 등 아래 예시 질문을 선택해 근거 확인 흐름을 살펴보세요. 실제 업무 판단이나 신청은 진행하지 않습니다.",
      },
    ]);
    setInput("");
    setSourceId(match?.id ?? null);
    setParams({}, { replace: true });
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    send(input);
  }
  return (
    <>
      <Heading
        label="AI WORK COMPANION"
        title="궁금한 업무, 근거와 함께 이해해요."
        action={
          <button
            className="p-button p-secondary"
            onClick={() => {
              setMessages([]);
              setSourceId(null);
              setInput("");
              setParams({}, { replace: true });
            }}
          >
            <Plus size={16} />새 대화
          </button>
        }
      >
        현재는 고정 예시 답변입니다. 실제 RAG와 외부 AI는 연결되지 않았어요.
      </Heading>
      <div className="p-assistant-layout">
        <section className="p-chat-panel" aria-label="업무 도우미 대화">
          <header>
            <span className="p-ai-symbol small">
              <Sparkles size={19} />
            </span>
            <strong>K:LINK 업무 도우미</strong>
            <span className="p-label">예시 응답</span>
          </header>
          <div className="p-chat-messages" aria-live="polite">
            {messages.length === 0 ? (
              <div className="p-chat-empty">
                <span className="p-chat-orbit">
                  <Sparkles size={36} strokeWidth={1.3} />
                </span>
                <span className="p-kicker">LET'S MAKE WORK EASIER</span>
                <h2>어떤 일이 궁금하세요?</h2>
                <p>
                  복잡한 규정은 쉽게, 준비할 일은 분명하게.
                  <br />
                  예시 질문으로 시작해 보세요.
                </p>
                <div className="p-prompt-grid">
                  {[
                    "자녀 돌봄 지원금 조건이 궁금해요",
                    "가족 돌봄 휴가를 준비하고 싶어요",
                    "자기계발 지원은 어떻게 받나요?",
                  ].map((prompt) => (
                    <button key={prompt} onClick={() => send(prompt)}>
                      {prompt}
                      <ArrowRight size={16} />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <article
                  className={"p-message " + message.role}
                  key={message.id}
                >
                  <span className="p-message-avatar">
                    {message.role === "user" ? "나" : <Sparkles size={17} />}
                  </span>
                  <div>
                    <strong>
                      {message.role === "user"
                        ? "체험 직원"
                        : "K:LINK · 고정 예시 응답"}
                    </strong>
                    <p>{message.content}</p>
                    {message.benefitId && (
                      <div className="p-message-actions">
                        <button onClick={() => setSourceId(message.benefitId!)}>
                          <BookOpen size={14} />
                          [1] 가상 규정 근거
                          <ChevronRight size={13} />
                        </button>
                        <Link
                          to="/workspace/preparations"
                          onClick={() => startPreparation(message.benefitId!)}
                        >
                          <FileCheck2 size={14} />
                          준비에 담기
                          <ArrowRight size={13} />
                        </Link>
                      </div>
                    )}
                  </div>
                </article>
              ))
            )}
            <div ref={bottom} />
          </div>
          <form className="p-chat-form" onSubmit={submit}>
            <label className="p-sr-only" htmlFor="portal-question">
              업무 질문
            </label>
            <textarea
              id="portal-question"
              value={input}
              maxLength={1000}
              onChange={(event) => setInput(event.target.value)}
              placeholder="궁금한 업무를 적어주세요. 실제 개인정보는 입력하지 마세요."
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  send(input);
                }
              }}
            />
            <div>
              <span>
                <ShieldCheck size={13} />
                외부 전송 없음 · {input.length}/1,000
              </span>
              <button
                className="p-button"
                type="submit"
                disabled={!input.trim()}
                aria-label="질문 보내기"
              >
                보내기
                <Send size={16} />
              </button>
            </div>
          </form>
        </section>
        <aside className="p-chat-evidence">
          <header>
            <BookOpen size={18} />
            <h2>답변의 근거</h2>
          </header>
          {source ? (
            <Source benefit={source} />
          ) : (
            <div className="p-evidence-empty">
              <span>
                <BookOpen size={30} strokeWidth={1.4} />
              </span>
              <h3>출처를 함께 확인하세요</h3>
              <p>
                예시 답변의 인용을 선택하면
                <br />
                문구·버전·회사 범위를 보여드려요.
              </p>
              <dl>
                <div>
                  <dt>01</dt>
                  <dd>출처와 규정 위치 확인</dd>
                </div>
                <div>
                  <dt>02</dt>
                  <dd>조건·예외 직접 살펴보기</dd>
                </div>
                <div>
                  <dt>03</dt>
                  <dd>필요한 준비 목록에 담기</dd>
                </div>
              </dl>
            </div>
          )}
          <Note>
            자동 안내가 회사의 최종 자격 판단이나 승인을 대신하지 않습니다.
          </Note>
        </aside>
      </div>
    </>
  );
}
