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
export function checkedAnswer(value: HrAnswer): HrAnswer {
  if (
    !["answered", "needs_review"].includes(value.status) ||
    !Array.isArray(value.paragraphs) ||
    !Array.isArray(value.sources) ||
    !Array.isArray(value.missing_information)
  )
    throw new HrError(0, "답변 형식을 확인하지 못해 내용을 표시하지 않았어요.");
  if (value.generated_text_withheld) return { ...value, paragraphs: [] };
  if (
    value.paragraphs.length &&
    value.validation !==
      "AUTOMATIC_ID_QUOTE_NUMBER_CHECKS_NOT_SEMANTIC_APPROVAL"
  )
    throw new HrError(
      0,
      "인용 검사 결과를 확인하지 못해 답변을 표시하지 않았어요.",
    );
  for (const paragraph of value.paragraphs) {
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
  return value;
}
