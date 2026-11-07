import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  FileCheck2,
  Plus,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { Heading, Modal, Note } from "../portal/ui";
import { useHr } from "./HrContext";
import { HR, HrError, checkedAnswer, request } from "./api";
import type {
  EvidenceResults,
  EvidenceSource,
  HrAnswer,
  OfficialForm,
} from "./api";
import { Company, SourceView, Unavailable } from "./ui";
import { ConditionCards } from "./ConditionCards";
import { RetrievalConnection, RetrievedChunks } from "./RetrievalView";

async function currentSource(item: EvidenceSource, signal?: AbortSignal) {
  const result = await request<EvidenceSource>(
    HR + "/sources/" + encodeURIComponent(item.id),
    "GET",
    undefined,
    signal,
  );
  if (
    result.id !== item.id ||
    typeof result.text !== "string" ||
    result.sha256 !== item.sha256 ||
    result.version !== item.version
  )
    throw new HrError(
      409,
      "원문 버전이 변경됐어요. 최신 원문을 다시 검색해 주세요.",
    );
  return result;
}
export function HrLibrary() {
  const { forms, session, refresh } = useHr(),
    [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "forms" ? "forms" : "rules",
    query = params.get("q") ?? "";
  const [input, setInput] = useState(query),
    [results, setResults] = useState<EvidenceResults | null>(null),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [source, setSource] = useState<EvidenceSource | null>(null),
    [form, setForm] = useState<OfficialForm | null>(null),
    [opening, setOpening] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    setInput(query);
  }, [query]);
  useEffect(() => {
    setResults(null);
    setError("");
    if (tab !== "rules" || query.trim().length < 2) {
      setPending(false);
      return;
    }
    const controller = new AbortController();
    setPending(true);
    request<EvidenceResults>(
      HR + "/evidence?q=" + encodeURIComponent(query),
      "GET",
      undefined,
      AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]),
    )
      .then((data) => {
        if (!Array.isArray(data.results))
          throw new HrError(0, "원문 검색 응답을 확인하지 못했어요.");
        if (!controller.signal.aborted) setResults(data);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(
            reason instanceof Error ? reason.message : "원문을 찾지 못했어요.",
          );
          if (reason instanceof HrError && reason.status === 401)
            void refresh();
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setPending(false);
      });
    return () => controller.abort();
  }, [tab, query, retry, refresh]);
  function submit(event: FormEvent) {
    event.preventDefault();
    const next = new URLSearchParams(window.location.search);
    input.trim() ? next.set("q", input.trim()) : next.delete("q");
    setParams(next, { replace: true });
  }
  function changeTab(value: string) {
    const next = new URLSearchParams(window.location.search);
    next.set("tab", value);
    next.delete("q");
    setInput("");
    setParams(next, { replace: true });
  }
  async function openSource(item: EvidenceSource) {
    setOpening(item.id);
    setError("");
    try {
      setSource(await currentSource(item));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "원문을 조회하지 못했어요.",
      );
      if (reason instanceof HrError && reason.status === 401) void refresh();
    } finally {
      setOpening("");
    }
  }
  const filtered = forms?.filter((item) =>
    (item.title + item.preparation_items.join(" ")).includes(query),
  );
  return (
    <>
      <Heading
        label="REGULATIONS & FORMS"
        title="원문과 공식 양식의 상태를 확인해요."
      >
        한국전력 참고자료 검색과 실제 회사 양식의 연결 상태를 구분합니다.
      </Heading>
      <div className="p-filter-tabs">
        <button
          aria-pressed={tab === "rules"}
          onClick={() => changeTab("rules")}
        >
          참고 원문 검색
        </button>
        <button
          aria-pressed={tab === "forms"}
          onClick={() => changeTab("forms")}
        >
          회사 양식·준비
        </button>
      </div>
      <form className="hr-library-search" onSubmit={submit}>
        <label className="p-inline-search">
          <Search size={19} />
          <input
            aria-label="서버 규정·양식 검색어"
            maxLength={500}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={
              tab === "rules"
                ? "예: 병가, 휴가, 퇴직 · 2자 이상"
                : "예: 휴가신청서, 출장비 정산서"
            }
          />
        </label>
        <button className="p-button" type="submit">
          검색
        </button>
      </form>
      {tab === "rules" ? (
        <>
          <Note>
            검색 대상은 한국전력 공개 대체자료입니다. 실제 KTcs 현행 규정이
            아니며, 적용 대상·현행성·사람 승인 상태를 원문에서 확인해야 합니다.
          </Note>
          {error && (
            <div className="hr-errors" role="alert">
              <p>{error}</p>
              <button onClick={() => setRetry((value) => value + 1)}>
                다시 조회
              </button>
            </div>
          )}
          {pending ? (
            <p className="hr-pending" role="status">
              허용된 인사 원문을 검색하고 있어요…
            </p>
          ) : results ? (
            <>
              <div className="p-result-heading">
                <p>
                  검색 결과 <b>{results.results.length}</b>개
                </p>
                <span>한국전력 참고자료 · 원문 {results.source_count}구간</span>
              </div>
              <div className="p-document-list">
                {results.results.map((item) => (
                  <button
                    key={item.id}
                    className="p-document-row"
                    disabled={!!opening}
                    onClick={() => void openSource(item)}
                  >
                    <span className="p-document-icon">
                      <BookOpen size={21} />
                    </span>
                    <span>
                      <small>한국전력 참고자료 · {item.employee_scope}</small>
                      <strong>{item.title}</strong>
                      <p>{item.section}</p>
                    </span>
                    <span className="p-label">
                      {opening === item.id ? "조회 중" : "KTcs 적용 미확인"}
                    </span>
                    <ChevronRight size={17} />
                  </button>
                ))}
                {!results.results.length && (
                  <Unavailable title="허용된 참고 원문에서 결과를 찾지 못했어요" />
                )}
              </div>
            </>
          ) : (
            !error && (
              <div className="hr-search-start">
                <BookOpen size={34} />
                <h2>필요한 인사 업무를 검색해 보세요</h2>
                <p>검색 결과에서 원문 전체와 출처 정보를 확인할 수 있습니다.</p>
                <div>
                  {["병가", "휴가", "퇴직"].map((text) => (
                    <button
                      className="p-button p-secondary"
                      key={text}
                      onClick={() => {
                        const next = new URLSearchParams(
                          window.location.search,
                        );
                        next.set("q", text);
                        setParams(next, { replace: true });
                      }}
                    >
                      {text}
                      <ArrowRight size={14} />
                    </button>
                  ))}
                </div>
              </div>
            )
          )}
        </>
      ) : forms === null ? (
        <Unavailable
          title="공식 양식 상태를 조회하지 못했어요"
          retry={() => void refresh()}
        />
      ) : (
        <>
          <Note>
            공식 양식이 없는 항목은 준비 안내만 제공합니다. 양식을 새로 만들어
            공식 서식처럼 표시하지 않습니다.
          </Note>
          <div className="p-result-heading">
            <p>
              양식 안내 <b>{filtered?.length ?? 0}</b>개
            </p>
            <span>
              공식 파일 {forms.filter((item) => item.official_available).length}
              개 연결
            </span>
          </div>
          <div className="p-document-list">
            {filtered?.map((item) => (
              <button
                key={item.id}
                className="p-document-row"
                onClick={() => setForm(item)}
              >
                <span className="p-document-icon">
                  <FileCheck2 size={22} />
                </span>
                <span>
                  <small>
                    {item.official_available
                      ? "서버에서 검증한 회사 양식"
                      : "회사 공식 파일 미연결"}
                  </small>
                  <strong>{item.title}</strong>
                  <p>{item.notice}</p>
                </span>
                <span className="p-label">
                  {item.official_available
                    ? "직원 권한 확인 필요"
                    : "준비 안내만 제공"}
                </span>
                <ChevronRight size={17} />
              </button>
            ))}
            {!filtered?.length && (
              <Unavailable title="검색한 양식 안내가 없어요" />
            )}
          </div>
        </>
      )}
      {source && (
        <Modal
          drawer
          title="서버에서 조회한 참고 원문"
          close={() => setSource(null)}
        >
          <div className="p-modal-body">
            <SourceView source={source} />
          </div>
        </Modal>
      )}
      {form && (
        <Modal
          title={form.title}
          subtitle={
            form.official_available
              ? "서버의 공식 양식 검증 범위"
              : "공식 파일 미연결 · 준비 안내"
          }
          close={() => setForm(null)}
        >
          <div className="p-modal-body">
            <ol className="p-number-list">
              {form.preparation_items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
            <Note>{form.notice}</Note>
            {form.official_available &&
            session?.mode === "supabase" &&
            form.download_path &&
            /^\/api\/benefits\/hr\/forms\/[a-z0-9_-]+\/download$/.test(
              form.download_path,
            ) ? (
              <a className="p-button" href={form.download_path}>
                권한을 확인하고 공식 양식 내려받기
              </a>
            ) : (
              <button className="hr-submit-disabled" disabled>
                {form.official_available
                  ? "인가된 직원 계정에서만 다운로드 가능"
                  : "공식 양식 연결 전 · 다운로드 불가"}
              </button>
            )}
            <Link
              className="p-button p-secondary"
              to="/hr/preparations"
              onClick={() => setForm(null)}
            >
              나의 준비 목록
              <ArrowRight size={15} />
            </Link>
          </div>
        </Modal>
      )}
    </>
  );
}
interface Message {
  id: string;
  question: string;
  answer?: HrAnswer;
  error?: string;
}
export function HrAssistant() {
  const { refresh } = useHr(),
    [input, setInput] = useState(""),
    [messages, setMessages] = useState<Message[]>([]),
    [pending, setPending] = useState(false),
    [source, setSource] = useState<EvidenceSource | null>(null),
    [sourceError, setSourceError] = useState("");
  const controller = useRef<AbortController | null>(null),
    transcript = useRef<HTMLDivElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    const container = transcript.current;
    const latest = container?.querySelector<HTMLElement>(
      ".hr-conversation:last-of-type",
    );
    if (messages.length && container && latest)
      container.scrollTop +=
        latest.getBoundingClientRect().top -
        container.getBoundingClientRect().top;
  }, [messages, pending]);
  async function send(text: string) {
    const question = text.trim();
    if (pending || question.length < 2 || question.length > 500) return;
    const id = crypto.randomUUID(),
      current = new AbortController();
    controller.current = current;
    setPending(true);
    setSource(null);
    setSourceError("");
    setInput("");
    setMessages((previous) => [...previous, { id, question }]);
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
        previous.map((item) => (item.id === id ? { ...item, answer } : item)),
      );
      setSource(answer.sources[0] ?? null);
    } catch (reason) {
      if (!current.signal.aborted) {
        setMessages((previous) =>
          previous.map((item) =>
            item.id === id
              ? {
                  ...item,
                  error:
                    reason instanceof Error
                      ? reason.message
                      : "답변을 조회하지 못했어요.",
                }
              : item,
          ),
        );
        if (reason instanceof HrError && reason.status === 401) void refresh();
      }
    } finally {
      if (!current.signal.aborted) setPending(false);
    }
  }
  async function openSource(item: EvidenceSource) {
    setSourceError("");
    try {
      setSource(await currentSource(item));
    } catch (reason) {
      setSource(null);
      setSourceError(
        reason instanceof Error ? reason.message : "원문을 조회하지 못했어요.",
      );
      if (reason instanceof HrError && reason.status === 401) void refresh();
    }
  }
  function clear() {
    controller.current?.abort();
    controller.current = null;
    setPending(false);
    setMessages([]);
    setInput("");
    setSource(null);
    setSourceError("");
  }
  return (
    <>
      <Heading
        label="SOURCE-GROUNDED HR ASSISTANT"
        title="실제로 찾은 원문과 함께 물어보세요."
        action={
          <button className="p-button p-secondary" onClick={clear}>
            <Plus size={16} />새 대화
          </button>
        }
      >
        서버가 허용한 한국전력 인사 참고자료만 사용합니다. 질문에 실제
        개인정보를 입력하지 마세요.
      </Heading>
      <RetrievalConnection />
      <div className="p-assistant-layout hr-assistant">
        <section className="p-chat-panel" aria-label="연결된 인사 대화">
          <header>
            <span className="p-ai-symbol small">
              <Sparkles size={19} />
            </span>
            <strong>K:LINK 인사 업무 도우미</strong>
            <span className="p-label">실제 서버 요청</span>
          </header>
          <div ref={transcript} className="p-chat-messages" aria-live="polite">
            {!messages.length ? (
              <div className="p-chat-empty">
                <span className="p-chat-orbit">
                  <BookOpen size={34} />
                </span>
                <span className="p-kicker">READ THE EVIDENCE TOGETHER</span>
                <h2>어떤 인사 업무가 궁금하세요?</h2>
                <p>
                  원문·적용 대상·검토 한계를 함께 확인해요.
                  <br />
                  실제 KTcs 규정과 자격은 별도 확인이 필요합니다.
                </p>
                <div className="p-prompt-grid">
                  {[
                    "병가 때 진단서 제출 기준은 무엇인가요?",
                    "가족 돌봄 휴가의 조건은 무엇인가요?",
                  ].map((question) => (
                    <button key={question} onClick={() => void send(question)}>
                      {question}
                      <ArrowRight size={16} />
                    </button>
                  ))}
                </div>
                <Link className="p-text-link" to="/hr/library?q=병가">
                  질문 전에 원문부터 검색
                  <ChevronRight size={14} />
                </Link>
              </div>
            ) : (
              messages.map((message) => (
                <div className="hr-conversation" key={message.id}>
                  <article className="p-message user">
                    <span className="p-message-avatar">나</span>
                    <div>
                      <strong>일반 인사 질문</strong>
                      <p>{message.question}</p>
                    </div>
                  </article>
                  {message.answer ? (
                    <article className="p-message assistant">
                      <span className="p-message-avatar">
                        <Sparkles size={17} />
                      </span>
                      <div>
                        <strong>원문 기반 참고 안내 · 자동 검사</strong>
                        <div className="hr-answer-status">
                          <span
                            className={
                              "p-status " +
                              (message.answer.status === "answered"
                                ? "eligible"
                                : "needs_review")
                            }
                          >
                            {message.answer.understanding?.status ===
                            "needs_clarification"
                              ? "질문 확인 필요"
                              : message.answer.status === "answered"
                                ? "원문을 인용한 참고 답변"
                                : "추가 확인 필요"}
                          </span>
                          <Company company={message.answer.company} />
                        </div>
                        <Note>{message.answer.notice}</Note>
                        {message.answer.understanding?.status === "ready" && (
                          <p className="hr-question-understanding">
                            <strong>질문을 이렇게 이해했어요:</strong>{" "}
                            {message.answer.understanding.interpreted_as}
                          </p>
                        )}
                        {message.answer.understanding?.status ===
                          "needs_clarification" && (
                          <section className="hr-clarification">
                            <h3>질문을 더 확인할게요</h3>
                            <p>{message.answer.understanding.clarification}</p>
                          </section>
                        )}
                        {message.answer.quote_method ===
                          "APPLICATION_RECONSTRUCTED_ORIGINAL_SPANS_NO_GENERATED_QUOTES" &&
                          message.answer.paragraphs.length > 0 && (
                            <p className="hr-quote-method">
                              인용문은 선택된 원문 구간에서 그대로 복원했습니다.
                            </p>
                          )}
                        {message.answer.answer_method ===
                          "SOURCE_EXTRACTED_FACTS" &&
                          message.answer.paragraphs.length > 0 && (
                            <p className="hr-quote-method">
                              지급일·예외를 원문에서 직접 확인한 안내입니다.
                            </p>
                          )}
                        <RetrievedChunks
                          answer={message.answer}
                          openSource={(item) => void openSource(item)}
                        />
                        {message.answer.validation ===
                          "FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION" && (
                          <p className="hr-replay-label">
                            보존 응답 재생 · 새 모델 호출 아님
                          </p>
                        )}
                        {message.answer.partial_verified_text && (
                          <p className="hr-withheld">
                            인용 검사를 통과하지 못한 설명은 제외하고 남은
                            문단을 표시했습니다. 추가 확인이 필요한 항목도 함께
                            살펴보세요.
                          </p>
                        )}
                        {message.answer.generated_text_withheld && (
                          <p className="hr-withheld">
                            검사에 맞지 않거나 완성되지 않은 생성 문장은
                            표시하지 않았어요. 확인된 원문과 추가 확인 항목을
                            살펴보세요.
                          </p>
                        )}
                        {message.answer.paragraphs.map((paragraph, index) => (
                          <section className="hr-answer-part" key={index}>
                            <p>{paragraph.text}</p>
                            <div>
                              {paragraph.citations.map(
                                (citation, citationIndex) => {
                                  const cited = message.answer!.sources.find(
                                    (item) => item.id === citation.source_id,
                                  );
                                  return cited ? (
                                    <button
                                      key={citation.source_id + citationIndex}
                                      onClick={() => void openSource(cited)}
                                    >
                                      <BookOpen size={13} />
                                      {cited.title} · 인용 {citationIndex + 1}
                                      <ChevronRight size={13} />
                                    </button>
                                  ) : null;
                                },
                              )}
                            </div>
                          </section>
                        ))}
                        <ConditionCards
                          answer={message.answer}
                          openSource={(item) => void openSource(item)}
                        />
                        {!!message.answer.missing_information.filter(
                          (text) =>
                            text !==
                            (message.answer!.understanding?.status ===
                            "needs_clarification"
                              ? message.answer!.understanding.clarification
                              : undefined),
                        ).length && (
                          <div className="hr-missing">
                            <h3>추가로 확인해 주세요</h3>
                            <ul>
                              {message.answer.missing_information
                                .filter(
                                  (text) =>
                                    text !==
                                    (message.answer!.understanding?.status ===
                                    "needs_clarification"
                                      ? message.answer!.understanding
                                          .clarification
                                      : undefined),
                                )
                                .map((text, index) => (
                                  <li key={index}>{text}</li>
                                ))}
                            </ul>
                          </div>
                        )}
                        {!!message.answer.sources.length && (
                          <div className="hr-answer-sources">
                            <h3>조회된 원문</h3>
                            {message.answer.sources.map((item) => (
                              <button
                                key={item.id}
                                onClick={() => void openSource(item)}
                              >
                                <BookOpen size={15} />
                                <span>
                                  {item.title}
                                  <small>
                                    {item.employee_scope} · {item.section}
                                  </small>
                                </span>
                                <ChevronRight size={14} />
                              </button>
                            ))}
                          </div>
                        )}
                        <p className="hr-semantic-note">
                          인용·수치의 자동 검사는 의미 정확성·완전성이나 사람
                          승인을 보증하지 않습니다.
                        </p>
                      </div>
                    </article>
                  ) : message.error ? (
                    <div className="hr-errors" role="alert">
                      <strong>답변을 확인하지 못했어요</strong>
                      <p>{message.error}</p>
                      <p>확인되지 않은 답변을 대신 만들지 않습니다.</p>
                      <Link className="p-text-link" to="/hr/library?q=병가">
                        원문 직접 검색
                        <ArrowRight size={14} />
                      </Link>
                    </div>
                  ) : (
                    <p className="hr-pending" role="status">
                      질문의 뜻과 조건을 확인한 뒤 원문을 검색하고 답변을
                      대조하고 있어요. 몇 분이 걸릴 수 있으며, 이 자동 검토는
                      사람의 독립 승인이 아닙니다.
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
          <form
            className="p-chat-form"
            onSubmit={(event) => {
              event.preventDefault();
              void send(input);
            }}
          >
            <label htmlFor="hr-question" className="p-sr-only">
              서버 인사 질문
            </label>
            <textarea
              id="hr-question"
              value={input}
              maxLength={500}
              disabled={pending}
              onChange={(event) => setInput(event.target.value)}
              placeholder="일반 인사 질문만 입력해 주세요. 직원 정보·연락처·키는 입력하지 마세요."
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
                <ShieldCheck size={13} />
                입력한 질문만 전송 · {input.length}/500
              </span>
              <button
                className="p-button"
                aria-label="서버에 인사 질문 보내기"
                type="submit"
                disabled={pending || input.trim().length < 2}
              >
                {pending ? "확인 중…" : "질문 보내기"}
                <Send size={16} />
              </button>
            </div>
          </form>
        </section>
        <aside className="p-chat-evidence hr-evidence-panel">
          <header>
            <BookOpen size={18} />
            <h2>답변의 원문·출처</h2>
            {source && (
              <button
                className="p-icon-button"
                aria-label="원문 패널 닫기"
                onClick={() => setSource(null)}
              >
                <X size={16} />
              </button>
            )}
          </header>
          {sourceError && (
            <div className="hr-errors" role="alert">
              <p>{sourceError}</p>
            </div>
          )}
          {source ? (
            <SourceView source={source} />
          ) : (
            <div className="p-evidence-empty">
              <span>
                <BookOpen size={28} />
              </span>
              <h3>출처를 함께 살펴보세요</h3>
              <p>
                답변의 인용이나 조회된 원문을 선택하면
                <br />
                전체 문구와 출처 정보를 표시합니다.
              </p>
            </div>
          )}
          <Note>
            한국전력 참고자료이며 KTcs 적용·사람 승인·현행성은 확인이
            필요합니다.
          </Note>
        </aside>
      </div>
    </>
  );
}
