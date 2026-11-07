import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  BookOpen,
  ChevronRight,
  LoaderCircle,
  Search,
} from "lucide-react";
import {
  HR,
  HrError,
  request,
  type EvidenceResults,
  type EvidenceSource,
} from "./api";
import { useHr } from "./HrContext";
import { SourceView } from "./ui";

export async function validateAssistantSource(source: EvidenceSource) {
  if (
    !source ||
    source.company !== "KEPCO" ||
    source.ktcs_applicable !== false ||
    typeof source.id !== "string" ||
    typeof source.title !== "string" ||
    typeof source.section !== "string" ||
    typeof source.version !== "string" ||
    typeof source.text !== "string" ||
    !/^[a-f0-9]{64}$/.test(source.sha256)
  )
    throw new HrError(0, "한전 원문의 출처와 적용 범위를 확인하지 못했어요.");
  const hash = Array.from(
    new Uint8Array(
      await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(source.text),
      ),
    ),
  )
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  if (hash !== source.sha256)
    throw new HrError(0, "원문 내용과 버전이 일치하지 않아 표시하지 않았어요.");
}

export function AssistantEvidence({
  sources,
  question,
  mode,
  setMode,
  selected,
  loading,
  error,
  onBack,
  onSource,
}: {
  sources: EvidenceSource[];
  question?: string;
  mode: "answer" | "search";
  setMode: (value: "answer" | "search") => void;
  selected: EvidenceSource | null;
  loading: boolean;
  error: string;
  onBack: () => void;
  onSource: (source: EvidenceSource) => void;
}) {
  const { refresh } = useHr();
  const [query, setQuery] = useState(""),
    [results, setResults] = useState<EvidenceResults | null>(null),
    [searching, setSearching] = useState(false),
    [searchError, setSearchError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function search(event: FormEvent) {
    event.preventDefault();
    const text = query.trim();
    if (text.length < 2 || text.length > 100) return;
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setSearching(true);
    setSearchError("");
    setResults(null);
    onBack();
    try {
      const data = await request<EvidenceResults>(
        HR + "/evidence?q=" + encodeURIComponent(text),
        "GET",
        undefined,
        current.signal,
      );
      if (
        data.company !== "KEPCO" ||
        data.ktcs_applicable !== false ||
        !Array.isArray(data.results)
      )
        throw new HrError(0, "허용된 한전 원문 검색 결과가 아닙니다.");
      await Promise.all(data.results.map(validateAssistantSource));
      if (!current.signal.aborted) setResults(data);
    } catch (reason) {
      if (!current.signal.aborted) {
        setSearchError(
          reason instanceof Error
            ? reason.message
            : "원문을 검색하지 못했어요.",
        );
        if (reason instanceof HrError && reason.status === 401) void refresh();
      }
    } finally {
      if (!current.signal.aborted) setSearching(false);
    }
  }
  const items = mode === "answer" ? sources : (results?.results ?? []);
  return (
    <div className="sa-evidence">
      {selected || loading ? (
        <div className="sa-source-detail">
          <button className="sa-source-back" onClick={onBack}>
            <ArrowLeft size={14} />
            목록으로
          </button>
          {loading ? (
            <p className="sa-evidence-loading" role="status">
              <LoaderCircle size={17} />
              원문을 불러오고 있어요.
            </p>
          ) : (
            selected && <SourceView source={selected} />
          )}
        </div>
      ) : (
        <>
          <div className="sa-evidence-tabs">
            <button
              aria-pressed={mode === "answer"}
              onClick={() => {
                onBack();
                setMode("answer");
              }}
            >
              답변 근거 <span>{sources.length}</span>
            </button>
            <button
              aria-pressed={mode === "search"}
              onClick={() => {
                onBack();
                setMode("search");
              }}
            >
              원문 검색
            </button>
          </div>
          {mode === "search" ? (
            <form className="sa-source-search" onSubmit={search}>
              <label className="p-sr-only" htmlFor="sa-source-query">
                원문 검색어
              </label>
              <div>
                <Search size={15} />
                <input
                  id="sa-source-query"
                  value={query}
                  maxLength={100}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="예: 병가, 급여, 휴가"
                />
                <button disabled={query.trim().length < 2 || searching}>
                  검색
                </button>
              </div>
              <p>연결된 한전 참고 규정을 검색합니다.</p>
            </form>
          ) : (
            question && (
              <p className="sa-source-context">
                <strong>이 질문의 근거</strong>
                {question}
              </p>
            )
          )}
          {searching && mode === "search" && (
            <p className="sa-evidence-loading" role="status">
              <LoaderCircle size={17} />
              원문 검색 중
            </p>
          )}
          {searchError && mode === "search" && (
            <p className="sa-evidence-error" role="alert">
              {searchError}
            </p>
          )}
          <div className="sa-source-list">
            {items.map((source, index) => (
              <button key={source.id} onClick={() => onSource(source)}>
                <span>{index + 1}</span>
                <div>
                  <strong>{source.title}</strong>
                  <p>{source.section}</p>
                  <small>{source.employee_scope} · KTcs 적용 미확인</small>
                </div>
                <ChevronRight size={14} />
              </button>
            ))}
          </div>
          {!items.length && !searching && (
            <div className="sa-evidence-empty">
              <BookOpen size={26} />
              <h3>
                {mode === "answer"
                  ? "선택한 답변의 근거가 여기에 표시됩니다."
                  : results
                    ? "검색된 원문이 없습니다."
                    : "규정을 먼저 확인해 보세요."}
              </h3>
              <p>
                {mode === "answer"
                  ? "답변의 인용 번호를 누르면 전체 원문을 열 수 있어요."
                  : "업무명이나 규정의 단어를 두 글자 이상 입력하세요."}
              </p>
            </div>
          )}
        </>
      )}
      {error && (
        <p className="sa-evidence-error" role="alert">
          {error}
        </p>
      )}
      <p className="sa-source-disclaimer">
        한국전력 공개 참고자료입니다. KTcs 적용·현행성·사람 승인은 별도 확인이
        필요합니다.
      </p>
    </div>
  );
}
