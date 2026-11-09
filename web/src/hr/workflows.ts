import { ControlError, control, type OpsSession } from "./operations";

export const APPROVAL_STATES: Record<string, string> = {
  pending: "승인 대기",
  approved: "승인 완료",
  rejected: "보류·반려",
  needs_info: "보완 요청",
  cancelled: "취소",
  superseded: "후속 버전 있음",
};
export const ALERT_STATES: Record<string, string> = {
  open: "확인 필요",
  acknowledged: "확인 중",
  resolved: "조건 해소",
};
export const ALERT_CATEGORIES: Record<string, string> = {
  cost: "비용",
  quality: "답변 품질",
  source: "규정·자료",
  routing: "문의 배정",
};
export interface SourceOption {
  id: string;
  title: string;
  sha256: string;
  source_url: string | null;
}
export interface SourceVersion {
  id: string;
  document_id: string;
  title: string;
  baseline_sha: string;
  sha256: string;
  state: string;
  job_id: string;
  checked_at: string;
}
export interface Approval {
  id: string;
  requester: string;
  kind: "source_check" | "source_change";
  title: string;
  document_id: string;
  job_kind: string | null;
  reason: string;
  state: string;
  note: string;
  reviewer: string | null;
  job_id: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
  events: { at: string; actor: string; state: string; note: string }[];
  version: SourceVersion | null;
}
export interface Notification {
  id: string;
  title: string;
  detail: string;
  target: string;
  created_at: string;
  read_at: string | null;
}
export interface EmployeeInbox {
  approvals: Approval[];
  notifications: Notification[];
}
export interface AutomationConfig {
  revision: number;
  watch_enabled: boolean;
  watch_documents: string[];
  watch_interval_minutes: number;
  cost_warning_percent: number;
  slow_seconds: number;
  routing: { category: string; team: string; sla_hours: number }[];
}
export interface AutomationState {
  config: AutomationConfig;
  teams: string[];
  categories: string[];
  runtime: { next_due: number; last_job: string | null; last_error: string };
  checks: {
    document_id: string;
    title: string;
    baseline_sha: string;
    last_sha: string;
    checked_at: string;
    job_id: string;
    changed: number;
  }[];
  versions: SourceVersion[];
}
export interface Agent {
  id: string;
  name: string;
  team: string;
  active: number;
  capacity: number;
  open_cases: number;
  revision: number;
}
export interface Alert {
  id: string;
  category: string;
  severity: string;
  title: string;
  detail: string;
  target: string;
  state: string;
  created_at: string;
  updated_at: string;
  revision: number;
  occurrences: number;
}
export interface Feedback {
  id: string;
  request_id: string;
  reason: string;
  note: string;
  state: string;
  resolution: string;
  revision: number;
  created_at: string;
  status: number;
  answer_state: string;
  latency_ms: number;
}
export interface Alerts {
  items: Alert[];
  feedback: Feedback[];
  allowed_categories: string[];
}

export async function ensureEmployeeSession(signal?: AbortSignal) {
  try {
    return await control<OpsSession>(
      "/api/control/session",
      "GET",
      undefined,
      signal,
    );
  } catch (error) {
    if (
      !(error instanceof ControlError) ||
      error.status !== 401 ||
      signal?.aborted
    )
      throw error;
    return control<OpsSession>(
      "/api/control/session/demo",
      "POST",
      { role: "employee" },
      signal,
    );
  }
}
