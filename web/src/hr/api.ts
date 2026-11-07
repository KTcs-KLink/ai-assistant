export type Decision = "eligible" | "needs_review" | "ineligible";
export interface EmployeeProfile {
  employment_consent: boolean;
  family_consent: boolean;
  hire_date: string | null;
  employment_type: "regular" | "fixed_term" | "part_time" | null;
  children_ages: number[] | null;
  household_size: number | null;
}
export interface HrSession {
  mode: "demo" | "supabase";
  name: string;
  production_eligibility_verified: boolean;
}
export interface Configuration {
  demo_enabled: boolean;
  local_evidence_configured: boolean;
  llm_configured: boolean;
  supabase: {
    status: string;
    auth_reachable?: boolean;
    database_reachable?: boolean;
    error_code?: string;
    message: string;
  };
}
export interface PolicySource {
  id: string;
  company: string;
  title: string;
  section: string;
  version: string;
  quote: string;
  sha256: string;
}
export interface HrBenefit {
  id: string;
  title: string;
  category: string;
  value: string;
  status: Decision;
  reasons: string[];
  checks: {
    id: string;
    label: string;
    state: "pass" | "unknown" | "fail";
    reason: string;
  }[];
  exceptions: string[];
  checklist: string[];
  source: PolicySource;
  policy_version: string;
  policy_sha256: string;
  as_of: string;
  deadline: string | null;
  form_id: string | null;
  synthetic: boolean;
  production_verified: boolean;
  application_enabled: boolean;
  policy_approval_verified: boolean;
}
export interface Catalog {
  company: string;
  synthetic: boolean;
  cards: HrBenefit[];
  counts: Record<Decision, number>;
  conditions_revision: string;
  production_eligibility_verified: boolean;
  configuration_required: boolean;
  actual_submission_enabled: boolean;
  profile_source: string;
  decision_scope: string;
}
export interface Preparation {
  id: string;
  benefit_id: string;
  title: string;
  policy_sha256: string;
  policy_version: string;
  conditions_revision: string;
  checklist: string[];
  checked: number[];
  stale: boolean;
  submitted: boolean;
  form_id: string | null;
}
export interface OfficialForm {
  id: string;
  title: string;
  preparation_items: string[];
  official_available: boolean;
  status: string;
  download_path: string | null;
  version: string | null;
  notice: string;
}
export interface Research {
  company: string;
  source_count: number;
  document_count: number;
  human_approved_count: number;
  ktcs_applicable: boolean;
  method: string;
}
export interface Readiness {
  production_ready: boolean;
  approved_policy_count: number;
  official_form_count: number;
  gates: { priority: number; ready: boolean; code: string; message: string }[];
  research: Research;
  actual_submission_enabled: boolean;
  note: string;
}
export interface Updates {
  enabled: boolean;
  updates: { benefit_id: string; kind: string; message: string }[];
  synthetic?: boolean;
  external_notifications_sent: boolean;
}
export interface EvidenceSource {
  id: string;
  title: string;
  section: string;
  text: string;
  sha256: string;
  source_file_sha256?: string;
  version: string;
  company: string;
  employee_scope: string;
  review_status: string;
  human_approved: boolean;
  effective_status: string;
  ktcs_applicable: boolean;
}
export interface EvidenceResults extends Research {
  results: EvidenceSource[];
}
export interface SourceCondition {
  source_id: string;
  title: string;
  section: string;
  quote: string;
  start: number;
  end: number;
  source_sha256: string;
  quote_sha256: string;
  kind: "ORIGINAL_SOURCE_PARAGRAPH_NOT_GENERATED";
  human_approved: boolean;
}
export interface RetrievedChunk {
  chunk_id: string;
  source_id: string;
  start: number;
  end: number;
  text: string;
  sha256: string;
  source_sha256: string;
  rank: number;
  similarity: number;
}
export interface RetrievalTrace {
  method: string;
  status?: string;
  embedding?: {
    model: string;
    revision: string;
    dimension: number;
    computed: boolean;
    cached: boolean;
    location: string;
    elapsed_ms: number;
  } | null;
  index?: { window_count: number; source_count: number; read_only: boolean };
  matches?: RetrievedChunk[];
  source_unit_ids?: string[];
  lexical_fallback?: boolean;
}
export interface RetrievalStatus {
  method: string;
  ready: boolean;
  query_embedding: boolean;
  model?: string;
  index?: { window_count: number; source_count: number; read_only: boolean };
  message?: string;
}
export interface HrAnswer {
  company: string;
  ktcs_applicable: boolean;
  human_approved: boolean;
  employee_data_sent: boolean;
  status: "answered" | "needs_review";
  paragraphs: {
    text: string;
    citations: { source_id: string; quote: string }[];
  }[];
  missing_information: string[];
  sources: EvidenceSource[];
  notice: string;
  validation?: string;
  generated_text_withheld?: boolean;
  source_conditions?: SourceCondition[];
  condition_coverage?: string;
  condition_review_required?: string[];
  partial_verified_text?: boolean;
  provider_calls?: { phase: string }[];
  semantic_review?: { independent: boolean; human_approved: boolean };
  retrieval?: RetrievalTrace;
}
export class HrError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export const ROOT = "/api/benefits";
export const HR = ROOT + "/hr";
export async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  if (!path.startsWith(ROOT + "/"))
    throw new HrError(0, "허용된 인사 기능 주소가 아닙니다.");
  try {
    const response = await fetch(path, {
      method,
      credentials: "include",
      cache: "no-store",
      headers:
        body === undefined
          ? { Accept: "application/json" }
          : { "Content-Type": "application/json", Accept: "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal ?? AbortSignal.timeout(20000),
    });
    if (response.status === 204) return undefined as T;
    const data = await response.json().catch(() => null);
    if (!response.ok)
      throw new HrError(
        response.status,
        typeof data?.detail === "string"
          ? data.detail
          : response.status === 422
            ? "입력한 조건의 형식과 범위를 확인해 주세요."
            : "인사 서비스에서 요청을 완료하지 못했어요. 연결 상태를 확인해 주세요.",
      );
    if (!data || typeof data !== "object")
      throw new HrError(0, "인사 서비스 응답을 확인하지 못했어요.");
    return data as T;
  } catch (error) {
    if (
      error instanceof HrError ||
      (error instanceof DOMException && error.name === "AbortError")
    )
      throw error;
    throw new HrError(
      0,
      "인사 서비스에 연결하지 못했어요. 연결을 확인한 뒤 다시 시도해 주세요.",
    );
  }
}
export function checkedCatalog(value: Catalog): Catalog {
  if (
    !Array.isArray(value.cards) ||
    typeof value.conditions_revision !== "string" ||
    !value.counts ||
    value.cards.some(
      (card) =>
        !["eligible", "needs_review", "ineligible"].includes(card.status) ||
        typeof card.id !== "string" ||
        typeof card.title !== "string" ||
        typeof card.value !== "string" ||
        !Array.isArray(card.reasons) ||
        !Array.isArray(card.checks) ||
        !Array.isArray(card.checklist) ||
        !card.source ||
        typeof card.source.quote !== "string" ||
        !/^[a-f0-9]{64}$/.test(card.policy_sha256),
    )
  ) {
    throw new HrError(
      0,
      "추천 응답의 필수 조건·출처·버전을 확인하지 못했어요. 다시 조회해 주세요.",
    );
  }
  return value;
}
export async function checkedAnswer(value: HrAnswer): Promise<HrAnswer> {
  if (
    !["answered", "needs_review"].includes(value.status) ||
    !Array.isArray(value.paragraphs) ||
    !Array.isArray(value.sources) ||
    !Array.isArray(value.missing_information)
  )
    throw new HrError(0, "답변 형식을 확인하지 못해 내용을 표시하지 않았어요.");
  const result: HrAnswer = {
    ...value,
    paragraphs: value.generated_text_withheld ? [] : value.paragraphs,
    source_conditions: value.source_conditions ?? [],
    condition_review_required: value.condition_review_required ?? [],
    partial_verified_text:
      !value.generated_text_withheld && !!value.partial_verified_text,
  };
  if (
    !Array.isArray(result.source_conditions) ||
    !Array.isArray(result.condition_review_required) ||
    result.condition_review_required.some((item) => typeof item !== "string")
  )
    throw new HrError(0, "조건 원문 응답을 확인하지 못했어요.");
  if (
    result.paragraphs.length &&
    ![
      "AUTOMATIC_ID_QUOTE_NUMBER_CHECKS_NOT_SEMANTIC_APPROVAL",
      "AUTOMATIC_SOURCE_COMPARISON_ID_QUOTE_NUMBER_CHECKS_NOT_HUMAN_APPROVAL",
      "FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION",
    ].includes(value.validation ?? "")
  )
    throw new HrError(
      0,
      "인용 검사 결과를 확인하지 못해 답변을 표시하지 않았어요.",
    );
  for (const paragraph of result.paragraphs) {
    if (
      typeof paragraph.text !== "string" ||
      !Array.isArray(paragraph.citations) ||
      !paragraph.citations.length
    )
      throw new HrError(0, "문장별 인용이 없는 답변을 표시하지 않았어요.");
    for (const citation of paragraph.citations) {
      const source = value.sources.find((s) => s.id === citation.source_id);
      if (
        !source ||
        typeof source.text !== "string" ||
        typeof citation.quote !== "string" ||
        citation.quote.length < 8 ||
        !source.text.includes(citation.quote)
      )
        throw new HrError(
          0,
          "인용과 원문이 일치하지 않아 답변을 표시하지 않았어요.",
        );
    }
  }
  if (
    result.source_conditions!.length &&
    result.condition_coverage !==
      "CITED_PARAGRAPHS_ONLY_NOT_ALL_REQUIRED_ARTICLES"
  )
    throw new HrError(
      0,
      "조건 원문의 확인 범위를 알 수 없어 답변을 표시하지 않았어요.",
    );
  const hashes = new Map<string, string>();
  const sha256 = async (text: string) =>
    Array.from(
      new Uint8Array(
        await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)),
      ),
    )
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  for (const condition of result.source_conditions!) {
    if (!condition || typeof condition !== "object")
      throw new HrError(0, "조건 원문 항목을 확인하지 못했어요.");
    const source = result.sources.find(
      (item) => item.id === condition.source_id,
    );
    const points =
      source && typeof source.text === "string" ? Array.from(source.text) : [];
    if (
      !source ||
      condition.kind !== "ORIGINAL_SOURCE_PARAGRAPH_NOT_GENERATED" ||
      condition.title !== source.title ||
      condition.section !== source.section ||
      condition.human_approved !== false ||
      typeof condition.quote !== "string" ||
      !condition.quote.length ||
      !Number.isInteger(condition.start) ||
      !Number.isInteger(condition.end) ||
      condition.start < 0 ||
      condition.end <= condition.start ||
      condition.end > points.length ||
      points.slice(condition.start, condition.end).join("") !==
        condition.quote ||
      source.sha256 !== condition.source_sha256
    )
      throw new HrError(
        0,
        "조건·예외 원문의 위치나 버전이 일치하지 않아 답변을 표시하지 않았어요.",
      );
    let hash = hashes.get(source.id);
    if (!hash) {
      hash = await sha256(source.text);
      hashes.set(source.id, hash);
    }
    if (
      hash !== condition.source_sha256 ||
      (await sha256(condition.quote)) !== condition.quote_sha256
    )
      throw new HrError(
        0,
        "조건·예외 원문 해시가 일치하지 않아 답변을 표시하지 않았어요.",
      );
  }
  const retrieval = result.retrieval;
  if (retrieval?.method === "local_bge_m3_dense") {
    const fail = () =>
      new HrError(
        0,
        "질문 임베딩과 실제 검색 청크의 연결을 확인하지 못해 답변을 표시하지 않았어요.",
      );
    if (!Array.isArray(retrieval.matches)) throw fail();
    if (retrieval.status === "OUT_OF_HR_SCOPE") {
      if (
        retrieval.matches.length ||
        retrieval.embedding ||
        result.sources.length ||
        result.paragraphs.length
      )
        throw fail();
    } else {
      const embedding = retrieval.embedding;
      if (
        retrieval.status !== "RETRIEVED" ||
        embedding?.model !== "BAAI/bge-m3" ||
        embedding.dimension !== 1024 ||
        embedding.revision !== "5617a9f61b028005a4858fdac845db406aefb181" ||
        embedding.computed !== true ||
        embedding.cached !== false ||
        embedding.location !== "LOCAL_SERVER" ||
        retrieval.lexical_fallback !== false ||
        retrieval.index?.read_only !== true ||
        !retrieval.matches.length ||
        retrieval.matches.length > 5 ||
        !Array.isArray(retrieval.source_unit_ids) ||
        retrieval.matches.length !== result.sources.length ||
        retrieval.matches.some(
          (chunk) => !chunk || typeof chunk !== "object",
        ) ||
        retrieval.source_unit_ids.length !== result.sources.length ||
        retrieval.source_unit_ids.some(
          (id, index) => id !== result.sources[index]?.id,
        ) ||
        new Set(retrieval.matches.map((c) => c.source_id)).size !==
          retrieval.matches.length
      )
        throw fail();
      for (const [index, chunk] of retrieval.matches.entries()) {
        const source = result.sources.find(
          (item) => item.id === chunk.source_id,
        );
        const points =
          source && typeof source.text === "string"
            ? Array.from(source.text)
            : [];
        if (
          !source ||
          chunk.rank !== index + 1 ||
          typeof chunk.chunk_id !== "string" ||
          !chunk.chunk_id.startsWith("W-") ||
          typeof chunk.text !== "string" ||
          !chunk.text.length ||
          !Number.isInteger(chunk.start) ||
          !Number.isInteger(chunk.end) ||
          chunk.start < 0 ||
          chunk.end <= chunk.start ||
          chunk.end > points.length ||
          points.slice(chunk.start, chunk.end).join("") !== chunk.text ||
          source.sha256 !== chunk.source_sha256 ||
          !Number.isFinite(chunk.similarity) ||
          Math.abs(chunk.similarity) > 1.001
        )
          throw fail();
        let hash = hashes.get(source.id);
        if (!hash) {
          hash = await sha256(source.text);
          hashes.set(source.id, hash);
        }
        if (
          hash !== chunk.source_sha256 ||
          (await sha256(chunk.text)) !== chunk.sha256
        )
          throw fail();
      }
    }
  }
  if (result.partial_verified_text || result.condition_review_required!.length)
    result.status = "needs_review";
  if (result.paragraphs.length && !result.source_conditions!.length) {
    result.status = "needs_review";
    result.condition_review_required = [
      ...result.condition_review_required!,
      "조건·예외 원문 카드가 없어 전체 원문을 직접 확인해야 해요.",
    ];
  }
  return result;
}
