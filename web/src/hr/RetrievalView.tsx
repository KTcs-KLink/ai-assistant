import { useEffect, useState } from "react";
import { BookOpen, Database, RefreshCw } from "lucide-react";
import {
  HR,
  HrError,
  request,
  type EvidenceSource,
  type HrAnswer,
  type RetrievalStatus,
} from "./api";
import { useHr } from "./HrContext";

export function RetrievalConnection() {
  const { refresh, readiness } = useHr();
  const [status, setStatus] = useState<RetrievalStatus | null>(null),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setStatus(null);
    setError("");
    request<{
      app: string;
      quality_version?: string;
      retrieval_mode?: string;
      answer_retrieval?: string;
    }>(
      HR + "/capabilities",
      "GET",
      undefined,
      AbortSignal.any([controller.signal, AbortSignal.timeout(60000)]),
    )
      .then(async (value) => {
        if (value.app !== "KLINK_HR_DOMAIN")
          throw new HrError(0, "지정된 인사 검색 서비스가 아닙니다.");
        const status =
          value.quality_version === "hr-quality-closeout-20261107" &&
          value.retrieval_mode === "hybrid"
            ? {
                method: "hr_bge_m3_hybrid",
                configured: true,
                ready: false,
                query_embedding: false,
              }
            : value.answer_retrieval === "local_bge_m3_dense"
              ? await request<RetrievalStatus>(
                  HR + "/retrieval/status",
                  "GET",
                  undefined,
                  AbortSignal.any([
                    controller.signal,
                    AbortSignal.timeout(60000),
                  ]),
                )
              : {
                  method: "unknown",
                  ready: false,
                  query_embedding: false,
                  message: "지원하는 한전 검색 경로를 확인하지 못했어요.",
                };
        if (!controller.signal.aborted) setStatus(status);
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "원문 검색 연결을 확인하지 못했어요.",
        );
        if (reason instanceof HrError && reason.status === 401) void refresh();
      });
    return () => controller.abort();
  }, [retry, refresh]);
  const ready =
    status?.ready &&
    status.method === "local_bge_m3_dense" &&
    status.query_embedding;
  const configured = status?.configured && status.method === "hr_bge_m3_hybrid";
  return (
    <div
      className={
        "hr-retrieval-connection" +
        (ready ? " ready" : configured ? " configured" : "")
      }
      role="status"
    >
      <Database size={19} />
      <div>
        <strong>
          {configured
            ? "한전 전용 BGE 결합 검색"
            : ready
              ? "로컬 원문 검색 연결"
              : status || error
                ? "원문 검색 연결 확인 필요"
                : "로컬 원문 검색을 확인하고 있어요"}
        </strong>
        <p>
          {configured
            ? "질문 임베딩·단어 검색 → 실제 조문 → AI 답변"
            : ready
              ? "질문 임베딩 → 실제 청크 검색 → AI 답변"
              : error ||
                status?.message ||
                "임베딩 모델과 로컬 색인을 확인합니다."}
        </p>
        {ready && (
          <small>
            한국전력 원문 {status.index?.source_count}개 · 검색 청크{" "}
            {status.index?.window_count}개 · {status.model} · KTcs 적용 미확인
          </small>
        )}
        {configured && (
          <small>
            서버에 설정된 검색 경로 · 한국전력 원문{" "}
            {readiness?.research.source_count ?? "확인 중"}개 · KTcs 적용 미확인
          </small>
        )}
      </div>
      {(status || error) && !ready && !configured && (
        <button
          className="p-text-link"
          onClick={() => setRetry((value) => value + 1)}
        >
          <RefreshCw size={14} />
          다시 확인
        </button>
      )}
    </div>
  );
}

export function RetrievedChunks({
  answer,
  openSource,
}: {
  answer: HrAnswer;
  openSource: (source: EvidenceSource) => void;
}) {
  const retrieval = answer.retrieval;
  if (retrieval?.method === "hr_bge_m3_hybrid" && answer.sources.length) {
    return (
      <details className="hr-retrieval-trace">
        <summary>
          <Database size={15} />
          한전 BGE·단어 결합 검색 · 조회 원문 {answer.sources.length}개
        </summary>
        <p>
          임베딩 검색 후 연결된 실제 조문 원문입니다. 답변에 사용한 인용과
          조건·예외는 아래에서 함께 확인할 수 있어요.
        </p>
        {answer.sources.map((source, index) => (
          <article key={source.id}>
            <h3>
              {index + 1}. {source.title}
            </h3>
            <p>{source.section}</p>
            <blockquote>{source.text}</blockquote>
            <button className="p-text-link" onClick={() => openSource(source)}>
              <BookOpen size={13} />
              원문·출처 확인
            </button>
          </article>
        ))}
      </details>
    );
  }
  if (
    retrieval?.method !== "local_bge_m3_dense" ||
    retrieval.status !== "RETRIEVED" ||
    !retrieval.matches?.length
  )
    return null;
  return (
    <details className="hr-retrieval-trace">
      <summary>
        <Database size={15} />
        질문 임베딩 완료 · 실제 청크 {retrieval.matches.length}개 검색
      </summary>
      <p>
        질문은 로컬 {retrieval.embedding?.model}로 임베딩했습니다. 검색한 청크와
        해당 원문 항 전체를 함께 묶어 답변 근거로 준비했습니다. 유사도는 답변의
        정확도 점수가 아닙니다.
      </p>
      {retrieval.matches.map((chunk) => {
        const source = answer.sources.find(
          (item) => item.id === chunk.source_id,
        );
        return (
          <article key={chunk.chunk_id}>
            <h3>
              {chunk.rank}. {source?.title}
            </h3>
            <p>{source?.section}</p>
            <blockquote>{chunk.text}</blockquote>
            <small>
              청크 {chunk.chunk_id} · 유사도 {chunk.similarity.toFixed(3)}
            </small>
            {source && (
              <button
                className="p-text-link"
                onClick={() => openSource(source)}
              >
                <BookOpen size={13} />
                전체 원문·출처 확인
              </button>
            )}
          </article>
        );
      })}
    </details>
  );
}
