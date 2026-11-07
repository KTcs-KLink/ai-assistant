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
  const { refresh } = useHr();
  const [status, setStatus] = useState<RetrievalStatus | null>(null),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setStatus(null);
    setError("");
    request<RetrievalStatus>(
      HR + "/retrieval/status",
      "GET",
      undefined,
      AbortSignal.any([controller.signal, AbortSignal.timeout(60000)]),
    )
      .then((value) => {
        if (!controller.signal.aborted) setStatus(value);
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
  return (
    <div
      className={"hr-retrieval-connection" + (ready ? " ready" : "")}
      role="status"
    >
      <Database size={19} />
      <div>
        <strong>
          {ready
            ? "로컬 원문 검색 연결"
            : status || error
              ? "원문 검색 연결 확인 필요"
              : "로컬 원문 검색을 확인하고 있어요"}
        </strong>
        <p>
          {ready
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
      </div>
      {(status || error) && !ready && (
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
