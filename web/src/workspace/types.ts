import type { Profile, Status } from '../benefits/api'
export type { Profile, Status }

export interface Policy {
  id: string
  title: string
  category: string
  icon: string
  description: string
  value: string
  value_note: string
  employment_types: string[]
  min_years: number
  child_min_age?: number
  child_max_age?: number
  household_min?: number
  unresolved?: boolean
  unresolved_reason?: string
  deadline: string | null
  period: string
  section: string
  quote: string
  checklist: string[]
}
export interface Check {
  label: string
  state: 'pass' | 'unknown' | 'fail'
  reason: string
}
export interface PreviewBenefit extends Policy {
  status: Status
  checks: Check[]
  reason: string
  daysLeft: number | null
}
export interface Preparation {
  benefitId: string
  checked: number[]
  createdAt: string
}
export interface PreviewMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  benefitId?: string
}
export interface FormReference {
  id: string
  title: string
  category: string
  description: string
  fields: string[]
}
