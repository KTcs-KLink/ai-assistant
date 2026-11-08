import { useCallback, useEffect, useState } from "react";

export class ControlError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function control<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  if (!path.startsWith("/api/control/"))
    throw new Error("허용된 운영 기능 주소가 아닙니다.");
  const response = await fetch(path, {
    method,
    credentials: "include",
    cache: "no-store",
    signal,
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new ControlError(
      response.status,
      typeof data?.detail === "string"
        ? data.detail
        : "요청 내용을 확인하거나 운영 서비스 연결을 다시 확인해 주세요.",
    );
  if (!data || typeof data !== "object")
    throw new ControlError(0, "운영 서비스 응답을 확인하지 못했습니다.");
  return data as T;
}
export function useControl<T>(
  path: string,
  enabled = true,
  interval: number | ((data: T | null) => number) = 0,
) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState<Error | null>(null),
    [loading, setLoading] = useState(enabled),
    [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const abort = new AbortController();
    setLoading(true);
    setError(null);
    void control<T>(path, "GET", undefined, abort.signal)
      .then((value) => {
        if (!abort.signal.aborted) setData(value);
      })
      .catch((reason) => {
        if (!abort.signal.aborted)
          setError(
            reason instanceof Error
              ? reason
              : new Error("정보를 불러오지 못했습니다."),
          );
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [path, enabled, revision]);
  const period = typeof interval === "function" ? interval(data) : interval;
  useEffect(() => {
    if (!enabled || !period) return;
    const timer = setInterval(refresh, period);
    return () => clearInterval(timer);
  }, [enabled, period, refresh]);
  return { data, error, loading, refresh };
}
export interface OpsSession {
  role: string;
  actor: string;
  permissions: string[];
  mode: "LOCAL_DEMO";
  production_authorized: false;
  sso_connected: false;
}
export interface CaseRecord {
  id: string;
  title: string;
  category: string;
  body: string;
  state: string;
  reply: string;
  created_at: string;
  updated_at: string;
  revision: number;
}
export interface SourceDocument {
  id: string;
  title: string;
  format: string;
  answer_count: number;
  review_count: number;
  excluded_count: number;
  source_url: string | null;
  sha256: string;
  version: string;
  effective_status: string;
  human_approved: false;
  ktcs_applicable: false;
}
export interface SourceCatalog {
  items: SourceDocument[];
  total: number;
  answer_units: number;
  review_units: number;
  excluded_units: number;
  manifest_sha256: string;
  production_approved: false;
}
export interface JobRecord {
  id: string;
  kind: "verify" | "recollect" | "reindex";
  state: string;
  documents: string[];
  created_at: string;
  updated_at: string;
  progress: number;
  message: string;
  retry_of: string | null;
  report: {
    status: string;
    scope: string;
    active_service_changed: false;
    answer_units: number;
    review_units: number;
    new_embeddings: number;
    index_sha256?: string;
    error?: string;
    documents?: {
      id: string;
      title: string;
      downloaded_bytes?: number;
      same_as_preserved?: boolean;
      downloaded_sha256?: string;
    }[];
  } | null;
}
export interface Aggregate {
  requests: number;
  completed: number;
  failed: number;
  measured_requests: number;
  unknown_usage: number;
  unpriced_requests: number;
  provider_calls: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  known_cost_usd: string;
}
export interface UsageRequest {
  id: string;
  day: string;
  started_at: string;
  completed_at: string | null;
  status: number | null;
  latency_ms: number | null;
  answer_state: string | null;
  call_count: number | null;
  usage_complete: number;
  input_tokens: number | null;
  output_tokens: number | null;
  cached_tokens: number | null;
  cost_usd: string | null;
  model: string | null;
  validation: string | null;
}
export interface Policy {
  monthly_budget_usd: string;
  daily_request_limit: number;
  budget_action: "observe" | "block";
  maintenance: boolean;
  revision: number;
  updated_at: string | null;
  scope: string;
  currency: string;
}
export interface Rate {
  model: string;
  input: string;
  cached: string;
  write: string;
  output: string;
  reference: string;
  checked_at: string;
  tier: string;
  revision: number;
}
export interface Usage {
  period_days: number;
  totals: Aggregate;
  monthly: Aggregate;
  daily: (Aggregate & { day: string })[];
  requests: UsageRequest[];
  median_latency_ms: number | null;
  rates: Rate[];
  policy: Policy;
  started_at: string | null;
  currency: string;
  timezone: string;
  history_scope: string;
}
export interface Integration {
  id: string;
  name: string;
  state: string;
  detail: string;
}
export interface Settings {
  policy: Policy;
  rates: Rate[];
  permissions: Record<string, string[]>;
  integrations: Integration[];
}
export interface Overview {
  source_count: number;
  review_count: number;
  document_count: number;
  approved_count: number;
  ktcs_applicable: false;
  cases: { state: string; count: number }[];
  jobs: JobRecord[];
  usage: Usage | null;
  mode: string;
  production_ready: false;
}
export interface ReviewRecord {
  id: string;
  state: string;
  note: string;
  reviewer: string;
  updated_at: string;
  revision: number;
}
export interface AuditRecord {
  id: number;
  at: string;
  actor: string;
  action: string;
  target: string;
  detail: string;
}
export const CASE_STATES: Record<string, string> = {
  received: "접수",
  in_review: "확인 중",
  awaiting_info: "추가 확인",
  resolved: "처리 완료",
  cancelled: "취소",
};
export const JOB_KINDS: Record<string, string> = {
  verify: "정합성 검사",
  recollect: "원문 재수집",
  reindex: "스테이징 재적재",
};
export const JOB_STATES: Record<string, string> = {
  queued: "대기",
  running: "실행 중",
  succeeded: "완료",
  failed: "실패",
  cancelled: "중지",
  interrupted: "중단",
};
export const ROLE_NAMES: Record<string, string> = {
  owner: "운영 책임자",
  data_admin: "데이터 관리자",
  hr_admin: "인사 담당자",
  analyst: "분석 담당자",
  employee: "일반 직원",
};
export const count = (value: number | null | undefined) =>
  value == null ? "—" : value.toLocaleString("ko-KR");
export const money = (value: string | number | null | undefined) =>
  value == null
    ? "미집계"
    : "$" +
      Number(value).toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 6,
      });
export const dateTime = (value: string) =>
  new Date(value).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
