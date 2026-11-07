export type Status = 'eligible' | 'needs_review' | 'ineligible'
export interface Profile {
  employment_consent: boolean
  family_consent: boolean
  hire_date: string | null
  employment_type: 'regular' | 'fixed_term' | 'part_time' | null
  children_ages: number[] | null
  household_size: number | null
}
export interface Benefit {
  id: string
  title: string
  category: string
  icon: string
  description: string
  value: string
  value_note: string
  deadline: string | null
  period: string
  status: Status
  reasons: string[]
  checks: {
    label: string
    result: 'pass' | 'fail' | 'unknown'
    reason: string
  }[]
  source: {
    id: string
    title: string
    company: string
    version: string
    section: string
    quote: string
    sha256: string
  }
  production_verified: boolean
  application_enabled: boolean
  form_status: string
  as_of: string
  checklist: string[]
  saved: boolean
  prepared: boolean
}
export interface Session {
  mode: 'demo' | 'supabase'
  name: string
  production_eligibility_verified: boolean
}
export interface Recommendations {
  mode: string
  cards: Benefit[]
  counts: Record<Status, number>
}
export interface Evidence {
  id: string
  title: string
  section: string
  excerpt?: string
  text?: string
  sha256: string
  version: string
  company: string
  human_approved: boolean
}
export interface Config {
  demo_enabled: boolean
  supabase: { status: string; message: string }
  local_evidence_configured: boolean
}
const base = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
  'http://localhost:8000'
).replace(/\/$/, '')

export class BenefitsError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

export async function benefitRequest<T>(
  path: string,
  method = 'GET',
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${base}/api/benefits${path}`, {
    method,
    credentials: 'include',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new BenefitsError(
      response.status,
      typeof data?.detail === 'string'
        ? data.detail
        : '요청을 처리하지 못했어요. 다시 시도해 주세요.',
    )
  }
  return response.status === 204 ? (undefined as T) : response.json()
}
