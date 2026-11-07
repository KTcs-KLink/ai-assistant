import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  ChevronDown,
  List,
  LoaderCircle,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import {
  HR,
  HrError,
  checkedAnswer,
  request,
  type EvidenceSource,
  type HrAnswer,
} from "./api";
import { useHr } from "./HrContext";
import { currentSource } from "./HrKnowledge";
import { RetrievalConnection } from "./RetrievalView";
import { WorkspaceDialog } from "./HrWorkspaceShell";
import { AssistantAnswer, answerForCopy } from "./AssistantAnswer";
import {
  AssistantEvidence,
  validateAssistantSource,
} from "./AssistantEvidence";
import "./assistant.css";

interface ChatMessage {
  id: string;
  question: string;
  answer?: HrAnswer;
  error?: string;
  interrupted?: boolean;
  started: number;
}
const PROMPTS = [
  { topic: "휴가·증빙", question: "병가 때 진단서는 언제 제출해야 하나요?" },
  { topic: "급여", question: "정기 급여 지급일은 언제인가요?" },
  { topic: "근무시간", question: "업무 사정으로 휴게시간을 바꿀 수 있나요?" },
  {
    topic: "휴가 절차",
    question: "휴가 신청과 허가는 어떤 절차로 진행하나요?",
  },
];
function Waiting({ started }: { started: number }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(
      () => setSeconds(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, [started]);
  return (
    <div className="sa-waiting">
      <LoaderCircle size={17} />
      <div>
        <strong role="status">질문과 근거 원문을 확인하고 있어요.</strong>
        <span aria-live="off">
          {seconds}초 경과 · 답변 확인까지 몇 분이 걸릴 수 있어요.
        </span>
      </div>
    </div>
  );
}
export function HrSaasAssistant() {
  const { refresh, readiness } = useHr();
  const location = useLocation(),
    navigate = useNavigate();
  const incoming =
    typeof location.state?.draftQuestion === "string"
      ? location.state.draftQuestion.trim()
      : "";
  const [input, setInput] = useState(() =>
      incoming.length >= 2 && incoming.length <= 500 ? incoming : "",
    ),
    [messages, setMessages] = useState<ChatMessage[]>([]),
    [pending, setPending] = useState(false),
    [activeId, setActiveId] = useState(""),
    [panelOpen, setPanelOpen] = useState(false),
    [compact, setCompact] = useState(
      () => window.matchMedia("(max-width: 1100px)").matches,
    ),
    [sourceMode, setSourceMode] = useState<"answer" | "search" | "review">(
      "search",
    ),
    [source, setSource] = useState<EvidenceSource | null>(null),
    [reviewQuery, setReviewQuery] = useState(""),
    [sourceLoading, setSourceLoading] = useState(false),
    [sourceError, setSourceError] = useState(""),
    [questionListOpen, setQuestionListOpen] = useState(false),
    [copiedId, setCopiedId] = useState(""),
    [copyError, setCopyError] = useState("");
  const controller = useRef<AbortController | null>(null),
    sourceController = useRef<AbortController | null>(null),
    transcript = useRef<HTMLDivElement>(null),
    composer = useRef<HTMLTextAreaElement>(null);
  const active = messages.find((message) => message.id === activeId);
  useEffect(() => {
    if (!incoming) return;
    if (incoming.length >= 2 && incoming.length <= 500) setInput(incoming);
    navigate(location.pathname + location.search, {
      replace: true,
      state: null,
    });
  }, [incoming, location.pathname, location.search, navigate]);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 1100px)");
    const changed = () => {
      setCompact(media.matches);
      setPanelOpen(false);
    };
    media.addEventListener("change", changed);
    return () => media.removeEventListener("change", changed);
  }, []);
  useEffect(
    () => () => {
      controller.current?.abort();
      sourceController.current?.abort();
    },
    [],
  );
  useEffect(() => {
    const container = transcript.current,
      latest = container?.lastElementChild;
    if (container && latest && messages.length)
      container.scrollTop +=
        latest.getBoundingClientRect().top -
        container.getBoundingClientRect().top -
        18;
  }, [messages, pending]);
  useEffect(() => {
    if (!copiedId) return;
    const timer = setTimeout(() => setCopiedId(""), 2500);
    return () => clearTimeout(timer);
  }, [copiedId]);
  function resetSource() {
    sourceController.current?.abort();
    sourceController.current = null;
    setSource(null);
    setSourceLoading(false);
    setSourceError("");
  }
  async function send(text: string) {
    const question = text.trim();
    if (controller.current || question.length < 2 || question.length > 500)
      return;
    const current = new AbortController(),
      id = crypto.randomUUID();
    controller.current = current;
    setPending(true);
    setInput("");
    setCopyError("");
    resetSource();
    setActiveId(id);
    setMessages((previous) => [
      ...previous,
      { id, question, started: Date.now() },
    ]);
    try {
      const answer = await checkedAnswer(
        await request<HrAnswer>(
          HR + "/answer",
          "POST",
          { question },
          AbortSignal.any([current.signal, AbortSignal.timeout(540000)]),
        ),
        question,
      );
      if (current.signal.aborted) return;
      setMessages((previous) =>
        previous.map((message) =>
          message.id === id ? { ...message, answer } : message,
        ),
      );
      setActiveId(id);
      setSourceMode("answer");
      if (
        answer.sources.length &&
        !window.matchMedia("(max-width: 1100px)").matches
      )
        setPanelOpen(true);
    } catch (reason) {
      if (!current.signal.aborted) {
        setMessages((previous) =>
          previous.map((message) =>
            message.id === id
              ? {
                  ...message,
                  error:
                    reason instanceof Error
                      ? reason.message
                      : "답변을 확인하지 못했어요.",
                }
              : message,
          ),
        );
        if (reason instanceof HrError && reason.status === 401) void refresh();
      }
    } finally {
      if (controller.current === current) {
        controller.current = null;
        setPending(false);
      }
    }
  }
  function stop() {
    controller.current?.abort();
    controller.current = null;
    setPending(false);
    setMessages((previous) =>
      previous.map((message) =>
        !message.answer && !message.error
          ? { ...message, interrupted: true }
          : message,
      ),
    );
  }
  function clear() {
    stop();
    resetSource();
    setMessages([]);
    setInput("");
    setActiveId("");
    setCopiedId("");
    setCopyError("");
    setPanelOpen(false);
    setSourceMode("search");
    composer.current?.focus();
  }
  async function openSource(item: EvidenceSource, messageId?: string) {
    resetSource();
    const current = new AbortController();
    sourceController.current = current;
    if (messageId) {
      setActiveId(messageId);
      setSourceMode("answer");
    }
    setPanelOpen(true);
    setSourceLoading(true);
    try {
      const result = await currentSource(
        item,
        AbortSignal.any([current.signal, AbortSignal.timeout(20000)]),
      );
      await validateAssistantSource(result);
      if (!current.signal.aborted) setSource(result);
    } catch (reason) {
      if (!current.signal.aborted) {
        setSourceError(
          reason instanceof Error
            ? reason.message
            : "원문을 조회하지 못했어요.",
        );
        if (reason instanceof HrError && reason.status === 401) void refresh();
      }
    } finally {
      if (!current.signal.aborted) setSourceLoading(false);
    }
  }
  async function copy(message: ChatMessage) {
    if (!message.answer) return;
    setCopyError("");
    try {
      await navigator.clipboard.writeText(answerForCopy(message.answer));
      setCopiedId(message.id);
    } catch {
      setCopyError(
        "답변을 복사하지 못했어요. 브라우저의 클립보드 권한을 확인해 주세요.",
      );
    }
  }
  function jump(id: string) {
    setQuestionListOpen(false);
    setActiveId(id);
    resetSource();
    setSourceMode("answer");
    const container = transcript.current,
      item = document.getElementById("sa-message-" + id);
    if (container && item)
      container.scrollTop +=
        item.getBoundingClientRect().top -
        container.getBoundingClientRect().top -
        18;
  }
  const evidence = (
    <AssistantEvidence
      sources={active?.answer?.sources ?? []}
      question={active?.question}
      reviewQuery={reviewQuery}
      mode={sourceMode}
      setMode={setSourceMode}
      selected={source}
      loading={sourceLoading}
      error={sourceError}
      onBack={resetSource}
      onSource={(item) => void openSource(item)}
    />
  );
  return (
    <div className="sa-assistant">
      <header className="sa-page-header">
        <div>
          <h1>AI 업무 도우미</h1>
          <p>질문하고, 답변의 근거까지 확인하세요.</p>
        </div>
        <div>
          <button
            className="sa-toolbar-button"
            onClick={() => setQuestionListOpen(true)}
            disabled={!messages.length}
            aria-label="현재 대화의 질문 목록"
          >
            <List size={16} />
            <span>질문 목록</span>
            {!!messages.length && <b>{messages.length}</b>}
          </button>
          <button
            className="sa-toolbar-button"
            aria-label="근거 자료"
            aria-pressed={panelOpen}
            onClick={() => setPanelOpen((value) => !value)}
          >
            {panelOpen ? (
              <PanelRightClose size={16} />
            ) : (
              <PanelRightOpen size={16} />
            )}
            <span>근거 자료</span>
            {!!active?.answer?.sources.length && (
              <b>{active.answer.sources.length}</b>
            )}
          </button>
          <button className="ws-primary" onClick={clear}>
            <Plus size={16} />새 대화
          </button>
        </div>
      </header>
      <div
        className={"sa-frame" + (panelOpen && !compact ? " with-evidence" : "")}
      >
        <section className="sa-chat" aria-label="인사 AI 대화">
          <div className="sa-chat-topline">
            <span>
              <span className="ws-dot connected" />
              답변용 한전 규정{" "}
              <b>{readiness?.research.source_count ?? "—"}조문</b>
              {readiness?.research.source_scope === "expanded" && (
                <button
                  className="sa-review-count"
                  onClick={() => {
                    setSourceMode("review");
                    resetSource();
                    setPanelOpen(true);
                  }}
                >
                  검토 전용{" "}
                  {readiness.research.review_only_count?.toLocaleString(
                    "ko-KR",
                  ) ?? "미확인"}
                  구간
                </button>
              )}
            </span>
            <details className="sa-connection-details">
              <summary>
                검색 범위
                <ChevronDown size={12} />
              </summary>
              <RetrievalConnection />
              <p>KTcs 적용·현행성·최종 승인은 별도 확인이 필요합니다.</p>
            </details>
          </div>
          <div
            ref={transcript}
            className="sa-transcript"
            aria-label="현재 대화"
          >
            {!messages.length ? (
              <div className="sa-empty">
                <span className="sa-assistant-symbol">
                  <Sparkles size={25} />
                </span>
                <h2>어떤 인사 업무를 도와드릴까요?</h2>
                <p>연결된 한전 참고 규정에서 근거를 찾아 안내합니다.</p>
                <div className="sa-prompts">
                  {PROMPTS.map((prompt) => (
                    <button
                      key={prompt.topic}
                      onClick={() => {
                        setInput(prompt.question);
                        composer.current?.focus();
                      }}
                    >
                      <span>{prompt.topic}</span>
                      <strong>{prompt.question}</strong>
                      <ArrowUpRight size={15} />
                    </button>
                  ))}
                </div>
                <button
                  className="sa-find-original"
                  onClick={() => {
                    setSourceMode("search");
                    resetSource();
                    setPanelOpen(true);
                  }}
                >
                  <Search size={14} />
                  답변 전에 원문부터 검색
                  <ArrowRight size={14} />
                </button>
              </div>
            ) : (
              messages.map((message) => (
                <article
                  className="sa-conversation"
                  id={"sa-message-" + message.id}
                  key={message.id}
                >
                  <div className="sa-user-message">
                    <span>나</span>
                    <p>{message.question}</p>
                  </div>
                  <div className="sa-assistant-message">
                    <div className="sa-message-heading">
                      <span className="sa-small-symbol">
                        <Sparkles size={15} />
                      </span>
                      <strong>K:LINK</strong>
                      {message.answer && <span>원문 기반 참고 안내</span>}
                    </div>
                    {message.answer ? (
                      <AssistantAnswer
                        answer={message.answer}
                        onSource={(item) => void openSource(item, message.id)}
                        onCopy={() => void copy(message)}
                        copied={copiedId === message.id}
                        onReview={(query) => {
                          setActiveId(message.id);
                          resetSource();
                          setReviewQuery(query);
                          setSourceMode("review");
                          setPanelOpen(true);
                        }}
                      />
                    ) : message.error ? (
                      <div className="sa-response-error" role="alert">
                        <strong>답변을 확인하지 못했어요</strong>
                        <p>{message.error}</p>
                        <button
                          onClick={() => {
                            setInput(message.question);
                            composer.current?.focus();
                          }}
                        >
                          질문 다시 작성
                          <ArrowRight size={14} />
                        </button>
                        <Link to="/hr/library?tab=rules">원문 직접 검색</Link>
                      </div>
                    ) : message.interrupted ? (
                      <p className="sa-interrupted">
                        응답 수신을 중지했습니다. 이미 시작한 요청은 계속 처리될
                        수 있어요.
                      </p>
                    ) : (
                      <Waiting started={message.started} />
                    )}
                  </div>
                </article>
              ))
            )}
          </div>
          <div className="sa-composer-area">
            {copyError && (
              <p className="sa-copy-error" role="alert">
                {copyError}
              </p>
            )}
            <form
              className="sa-composer"
              onSubmit={(event) => {
                event.preventDefault();
                void send(input);
              }}
            >
              <label htmlFor="hr-question" className="p-sr-only">
                인사 질문
              </label>
              <textarea
                id="hr-question"
                ref={composer}
                value={input}
                maxLength={500}
                disabled={pending}
                rows={2}
                onChange={(event) => setInput(event.target.value)}
                placeholder="궁금한 인사 업무를 입력하세요. 개인정보는 입력하지 마세요."
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey &&
                    !event.nativeEvent.isComposing
                  ) {
                    event.preventDefault();
                    void send(input);
                  }
                }}
              />
              <div>
                <span>
                  {input.length}/500{" "}
                  <span>· Enter 전송 / Shift+Enter 줄바꿈</span>
                </span>
                {pending ? (
                  <button type="button" className="sa-stop" onClick={stop}>
                    <Square size={12} />
                    응답 수신 중지
                  </button>
                ) : (
                  <button
                    type="submit"
                    className="sa-send"
                    disabled={input.trim().length < 2}
                    aria-label="인사 질문 전송"
                  >
                    <Send size={16} />
                    <span>전송</span>
                  </button>
                )}
              </div>
            </form>
            <p className="sa-composer-note">
              <ShieldCheck size={12} />
              KTcs 적용 미확인 · 대화는 이 탭의 현재 화면에서만 유지됩니다.
            </p>
          </div>
        </section>
        {panelOpen && !compact && (
          <aside className="sa-evidence-panel" aria-label="근거 자료 패널">
            <header>
              <h2>
                <BookOpen size={16} />
                근거 자료
              </h2>
              <button
                aria-label="근거 자료 닫기"
                onClick={() => setPanelOpen(false)}
              >
                <X size={16} />
              </button>
            </header>
            {evidence}
          </aside>
        )}
      </div>
      {panelOpen && compact && (
        <WorkspaceDialog title="근거 자료" close={() => setPanelOpen(false)}>
          {evidence}
        </WorkspaceDialog>
      )}
      {questionListOpen && (
        <WorkspaceDialog
          title="현재 대화의 질문"
          close={() => setQuestionListOpen(false)}
        >
          <div className="sa-question-list">
            <p>
              현재 화면의 질문만 표시합니다. 새로고침하면 대화가 초기화됩니다.
            </p>
            {messages.map((message, index) => (
              <button key={message.id} onClick={() => jump(message.id)}>
                <span>{index + 1}</span>
                <div>
                  <strong>{message.question}</strong>
                  <small>
                    {message.answer
                      ? message.answer.status === "answered"
                        ? "참고 답변"
                        : "확인 필요"
                      : message.error
                        ? "응답 확인 실패"
                        : message.interrupted
                          ? "수신 중지"
                          : "처리 중"}
                  </small>
                </div>
                <ArrowRight size={14} />
              </button>
            ))}
          </div>
        </WorkspaceDialog>
      )}
    </div>
  );
}
