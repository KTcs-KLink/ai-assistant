import { BookOpen, Check, ChevronRight, Copy, ShieldCheck } from "lucide-react";
import type { EvidenceSource, HrAnswer } from "./api";
import { ConditionCards } from "./ConditionCards";
import { RetrievedChunks } from "./RetrievalView";

export function answerForCopy(answer: HrAnswer) {
  const citedIds = new Set(
    answer.paragraphs.flatMap((paragraph) =>
      paragraph.citations.map((citation) => citation.source_id),
    ),
  );
  return [
    "K:LINK · 한전 원문 기반 참고 답변",
    answer.status === "answered" ? "원문 인용 답변" : "추가 확인 필요",
    answer.notice,
    ...answer.paragraphs.map((paragraph) => paragraph.text),
    ...(answer.source_conditions?.length
      ? [
          "함께 확인할 조건·예외 원문",
          ...answer.source_conditions.map(
            (condition) =>
              `${condition.title} · ${condition.section}\n${condition.quote}`,
          ),
        ]
      : []),
    ...(answer.missing_information.length ||
    answer.condition_review_required?.length
      ? [
          "추가 확인 항목",
          ...answer.missing_information,
          ...(answer.condition_review_required ?? []),
        ]
      : []),
    "출처",
    ...answer.sources
      .filter((source) => citedIds.has(source.id))
      .map(
        (source) =>
          `${source.title} · ${source.section}\n출처 ID: ${source.id} · 버전: ${source.version}`,
      ),
    "자동 검사는 의미 정확성·완전성이나 사람의 최종 승인을 보증하지 않습니다.",
  ].join("\n\n");
}

export function AssistantAnswer({
  answer,
  onSource,
  onCopy,
  copied,
}: {
  answer: HrAnswer;
  onSource: (source: EvidenceSource) => void;
  onCopy: () => void;
  copied: boolean;
}) {
  const clarification =
    answer.understanding?.status === "needs_clarification"
      ? answer.understanding.clarification
      : "";
  const missing = answer.missing_information.filter(
    (text) => text !== clarification,
  );
  const review = answer.condition_review_required ?? [];
  const sourceIndex = (id: string) =>
    answer.sources.findIndex((source) => source.id === id) + 1;
  return (
    <div className="sa-answer">
      <div className="sa-answer-status">
        <span
          className={
            "sa-state " + (answer.status === "answered" ? "answered" : "review")
          }
        >
          {clarification
            ? "질문 확인 필요"
            : answer.partial_verified_text
              ? "일부 답변 · 확인 필요"
              : answer.status === "answered"
                ? "원문 인용 답변"
                : "추가 확인 필요"}
        </span>
        <span>한국전력 참고자료</span>
      </div>
      {answer.understanding?.status === "ready" && (
        <p className="sa-understanding">
          질문을 이렇게 이해했어요:{" "}
          <strong>{answer.understanding.interpreted_as}</strong>
        </p>
      )}
      {clarification && (
        <section className="sa-review-note">
          <h3>질문을 더 확인할게요</h3>
          <p>{clarification}</p>
        </section>
      )}
      {answer.generated_text_withheld && (
        <p className="sa-review-note">
          검사를 통과하지 못한 생성 문장은 표시하지 않았습니다. 확인된 원문과
          추가 확인 항목을 살펴보세요.
        </p>
      )}
      {answer.partial_verified_text && (
        <p className="sa-review-note">
          확인되지 않은 설명을 제외한 일부 문단입니다. 추가 확인 항목도 함께
          살펴보세요.
        </p>
      )}
      <div className="sa-answer-body">
        {answer.paragraphs.map((paragraph, index) => (
          <section className="sa-answer-part" key={index}>
            <p>{paragraph.text}</p>
            <div className="sa-citations">
              {paragraph.citations.map((citation, citationIndex) => {
                const source = answer.sources.find(
                  (item) => item.id === citation.source_id,
                );
                return source ? (
                  <button
                    key={citation.source_id + ":" + citationIndex}
                    onClick={() => onSource(source)}
                    title={source.section}
                  >
                    <span>{sourceIndex(source.id)}</span>
                    <BookOpen size={12} />
                    {source.title}
                    <ChevronRight size={12} />
                  </button>
                ) : null;
              })}
            </div>
          </section>
        ))}
      </div>
      {!!missing.length && (
        <section className="sa-missing">
          <h3>추가로 확인해 주세요</h3>
          <ul>
            {missing.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
      )}
      {!!review.length && (
        <section className="sa-missing">
          <h3>조건 원문의 범위를 확인해 주세요</h3>
          <ul>
            {review.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
      )}
      {!!answer.source_conditions?.length && (
        <details className="sa-conditions">
          <summary>
            함께 확인할 조건·예외 원문{" "}
            <span>{answer.source_conditions.length}</span>
          </summary>
          <ConditionCards
            answer={{ ...answer, condition_review_required: [] }}
            openSource={onSource}
          />
        </details>
      )}
      <RetrievedChunks answer={answer} openSource={onSource} />
      <details className="sa-answer-scope">
        <summary>
          <ShieldCheck size={12} />
          검토·인용 범위
        </summary>
        <p>{answer.notice}</p>
        {answer.quote_method ===
          "APPLICATION_RECONSTRUCTED_ORIGINAL_SPANS_NO_GENERATED_QUOTES" && (
          <p>인용문은 선택된 원문 구간에서 그대로 복원했습니다.</p>
        )}
        {answer.answer_method === "SOURCE_EXTRACTED_FACTS" && (
          <p>지급일·예외를 원문에서 직접 확인한 안내입니다.</p>
        )}
        <p>
          인용·수치의 자동 검사는 의미 정확성·완전성이나 사람의 최종 승인을
          보증하지 않습니다.
        </p>
      </details>
      {answer.validation ===
        "FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION" && (
        <p className="sa-replay">보존 응답 재생 · 새 모델 호출 아님</p>
      )}
      <footer className="sa-answer-footer">
        <span>KTcs 적용·현행성·최종 승인 확인 필요</span>
        {!!answer.paragraphs.length && (
          <button onClick={onCopy} aria-label="답변과 출처 복사">
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "복사됨" : "답변 복사"}
          </button>
        )}
      </footer>
    </div>
  );
}
