import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { FileSearch, Search, ShieldAlert } from "lucide-react";
import { HR, HrError, request, type ReviewEvidenceResults } from "./api";
import { useHr } from "./HrContext";
import "./source-scope.css";

const holdReasonLabels: Record<string, string> = {
  EXISTING_ANSWER_GATE_HELD: "기존 답변 기준에서 추가 검토 대상으로 보류",
  HR_SCOPE_REVIEW_REQUIRED: "인사 업무 범위와 적용 대상 확인 필요",
  INCOMPLETE_ARTICLE_OR_FORM: "조문 또는 양식의 완전성 확인 필요",
  NEW_SOURCE_LAYOUT_OR_BOUNDARY_UNVERIFIED:
    "새 원문의 표 구조·조문 경계 확인 필요",
  LAYOUT_REVIEW_REQUIRED: "표·열 구조 확인 필요",
  ARTICLE_BODY_MISSING_OR_TOO_SHORT: "조문 본문 누락 또는 길이 확인 필요",
  PARAGRAPH_SEQUENCE_INCOMPLETE: "문단 순서·누락 확인 필요",
};
function holdReasonLabel(reason: string) {
  return (
    holdReasonLabels[reason] ??
    (/[가-힣]/.test(reason) ? reason : "추가 원문 검토 필요")
  );
}

export function SourceScopeNotice() {
  const { readiness } = useHr();
  const research = readiness?.research;
  if (research?.source_scope !== "expanded") return null;
  return (
    <section className="hr-source-scope" aria-label="원문 사용 범위">
      <div>
        <span>
          답변 참고용{" "}
          <strong>{research.source_count.toLocaleString("ko-KR")}조문</strong>
        </span>
        <Link to="/hr/library?tab=review">
          검토 전용{" "}
          <strong>
            {research.review_only_count?.toLocaleString("ko-KR") ?? "미확인"}
            구간
          </strong>
        </Link>
      </div>
      <p>
        파일·위치 대조와 업무 적용 승인은 다릅니다. 검토 발췌는 답변에 사용하지
        않으며, KTcs 적용·현행성·사람 승인은 별도 확인이 필요합니다.
      </p>
    </section>
  );
}

export function checkedReviewEvidence(value: ReviewEvidenceResults) {
  if (
    value.company !== "KEPCO" ||
    value.ktcs_applicable !== false ||
    value.human_approved !== false ||
    value.answer_eligible !== false ||
    value.used_for_generation !== false ||
    value.method !== "source_only_fts5_bm25" ||
    typeof value.notice !== "string" ||
    !Array.isArray(value.results) ||
    value.results.some(
      (item) =>
        !item ||
        item.company !== "KEPCO" ||
        item.ktcs_applicable !== false ||
        item.human_approved !== false ||
        item.answer_eligible !== false ||
        item.review_only !== true ||
        item.source_mapping_verified !== true ||
        item.excerpt_only !== true ||
        !Array.isArray(item.hold_reasons) ||
        item.hold_reasons.some((reason) => typeof reason !== "string") ||
        typeof item.id !== "string" ||
        typeof item.window_id !== "string" ||
        typeof item.title !== "string" ||
        typeof item.section !== "string" ||
        typeof item.text !== "string" ||
        !item.text.length ||
        !Array.isArray(item.source_range) ||
        item.source_range.length !== 2 ||
        !item.source_range.every(Number.isInteger) ||
        item.source_range[0] < 0 ||
        item.source_range[1] <= item.source_range[0],
    )
  )
    throw new HrError(
      0,
      "검토 발췌의 출처·범위·답변 미사용 상태를 확인하지 못해 표시하지 않았어요.",
    );
  return value;
}

// Review excerpts deliberately have no answer/source-selection callback.
export function ReviewEvidence({
  initialQuery = "",
}: {
  initialQuery?: string;
}) {
  const { readiness, refresh } = useHr();
  const [query, setQuery] = useState(initialQuery.slice(0, 100)),
    [data, setData] = useState<ReviewEvidenceResults | null>(null),
    [pending, setPending] = useState(false),
    [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const expanded = readiness?.research.source_scope === "expanded";
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    controller.current?.abort();
    setQuery(initialQuery.slice(0, 100));
    setData(null);
    setPending(false);
    setError("");
  }, [initialQuery]);
  async function search(event: FormEvent) {
    event.preventDefault();
    const text = query.trim();
    if (!expanded || text.length < 2 || text.length > 100) return;
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setPending(true);
    setError("");
    setData(null);
    try {
      const result = checkedReviewEvidence(
        await request<ReviewEvidenceResults>(
          HR + "/review-evidence?q=" + encodeURIComponent(text),
          "GET",
          undefined,
          current.signal,
        ),
      );
      if (!current.signal.aborted) setData(result);
    } catch (reason) {
      if (!current.signal.aborted) {
        setError(
          reason instanceof Error
            ? reason.message
            : "검토 발췌를 검색하지 못했어요.",
        );
        if (reason instanceof HrError && reason.status === 401) void refresh();
      }
    } finally {
      if (!current.signal.aborted) setPending(false);
    }
  }
  return (
    <section className="hr-review-evidence" aria-label="검토 전용 발췌 검색">
      <div className="hr-review-warning">
        <ShieldAlert size={17} />
        <div>
          <strong>검토 전용 · 답변 미사용</strong>
          <p>
            업무 범위·적용 대상·표 구조 등의 확인이 남은 발췌입니다. 파일·문자
            위치 대조만으로 규정 적용이나 자격을 확정할 수 없습니다.
          </p>
        </div>
      </div>
      <form onSubmit={search}>
        <label htmlFor="hr-review-query">검토 발췌 검색어</label>
        <div>
          <Search size={16} />
          <input
            id="hr-review-query"
            maxLength={100}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="검토할 문서명이나 단어"
            disabled={!expanded}
          />
          <button disabled={!expanded || pending || query.trim().length < 2}>
            검색
          </button>
        </div>
        <small>
          단어 검색 · 검토 대상{" "}
          {readiness?.research.review_only_count?.toLocaleString("ko-KR") ??
            "미확인"}
          구간
        </small>
      </form>
      {!expanded && (
        <p className="hr-review-error" role="alert">
          확장 자료의 검토 검색 연결을 확인해야 합니다.
        </p>
      )}
      {pending && <p role="status">검토용 발췌를 찾고 있어요.</p>}
      {error && (
        <p className="hr-review-error" role="alert">
          {error}
        </p>
      )}
      {data && (
        <>
          <p className="hr-review-result-count">
            검토 발췌 {data.results.length}건 · 답변 생성에 사용하지 않음
          </p>
          {data.results.map((item, index) => (
            <details className="hr-review-excerpt" key={item.window_id}>
              <summary>
                <span>{index + 1}</span>
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.section}</small>
                </div>
                <span className="hr-review-only">검토 전용</span>
              </summary>
              <div>
                <p className="hr-review-reason">
                  {item.needs_layout_review
                    ? "표·열 구조와 적용 범위를 확인해야 합니다."
                    : "업무 범위·적용 대상 등의 확인이 필요합니다."}
                </p>
                {!!item.hold_reasons.length && (
                  <ul className="hr-review-holds" aria-label="보류 사유">
                    {item.hold_reasons.map((reason, reasonIndex) => (
                      <li key={reasonIndex}>{holdReasonLabel(reason)}</li>
                    ))}
                  </ul>
                )}
                <blockquote>{item.text}</blockquote>
                <dl>
                  <div>
                    <dt>확인 범위</dt>
                    <dd>파일·문자 위치 대조 · 조직 승인 아님</dd>
                  </div>
                  <div>
                    <dt>답변 사용</dt>
                    <dd>불가 · 생성 근거로 미사용</dd>
                  </div>
                  <div>
                    <dt>발췌 위치</dt>
                    <dd>
                      {item.source_range[0]}–{item.source_range[1]} 문자 구간
                    </dd>
                  </div>
                  <div>
                    <dt>출처 ID</dt>
                    <dd>{item.id}</dd>
                  </div>
                  <div>
                    <dt>발췌 ID</dt>
                    <dd>{item.window_id}</dd>
                  </div>
                </dl>
              </div>
            </details>
          ))}
          {!data.results.length && (
            <p className="hr-review-empty">검색된 검토 발췌가 없습니다.</p>
          )}
          <p className="hr-review-notice">{data.notice}</p>
        </>
      )}
      {!data && !pending && !error && expanded && (
        <div className="hr-review-empty">
          <FileSearch size={27} />
          <p>추가 검토가 필요한 원문을 별도로 찾아보세요.</p>
        </div>
      )}
    </section>
  );
}
