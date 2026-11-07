import { BookOpen, ChevronRight } from "lucide-react";
import type { EvidenceSource, HrAnswer } from "./api";
import { Company } from "./ui";

export function ConditionCards({
  answer,
  openSource,
}: {
  answer: HrAnswer;
  openSource: (source: EvidenceSource) => void;
}) {
  const cards = answer.source_conditions ?? [],
    reviews = answer.condition_review_required ?? [];
  return (
    <>
      {!!cards.length && (
        <section
          className="hr-source-conditions"
          aria-label="함께 확인할 조건·예외 원문"
        >
          <h3>
            <BookOpen size={17} />
            함께 확인할 조건·예외 원문
          </h3>
          <p className="hr-condition-scope">
            인용한 원문 항 전체를 그대로 보여드립니다. 다른 조문의 필수 조건까지
            모두 찾았거나 실제 회사 자격을 확인했다는 뜻은 아닙니다.
          </p>
          {cards.map((card, index) => {
            const source = answer.sources.find(
              (item) => item.id === card.source_id,
            );
            return (
              <article
                key={card.source_id + ":" + card.start + ":" + card.end}
                aria-label={"조건·예외 원문 " + (index + 1)}
              >
                <div className="hr-condition-origin">
                  <Company company={source?.company ?? answer.company} />
                  <span>원문 발췌 · 사람 승인 전</span>
                </div>
                <h4>{card.title}</h4>
                <p className="hr-condition-section">{card.section}</p>
                <blockquote className="hr-condition-quote">
                  {card.quote}
                </blockquote>
                {source && (
                  <button
                    className="p-text-link"
                    onClick={() => openSource(source)}
                  >
                    전체 원문·출처 확인
                    <ChevronRight size={14} />
                  </button>
                )}
              </article>
            );
          })}
        </section>
      )}
      {!!reviews.length && (
        <section className="hr-condition-review">
          <h3>조건 원문의 범위를 더 확인해 주세요</h3>
          <ul>
            {reviews.map((review, index) => (
              <li key={index}>{review}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
