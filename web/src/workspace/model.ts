import type { Policy, Profile, PreviewBenefit, Check } from './types'

// Frozen fictional scenario for design review. Never a company eligibility decision.
export const PREVIEW_DATE = '2026-11-07'
export const INITIAL_PROFILE: Profile = {
  employment_consent: true,
  family_consent: true,
  hire_date: '2019-03-11',
  employment_type: 'regular',
  children_ages: [5, 9],
  household_size: 4,
}
export const BLANK_PROFILE: Profile = {
  employment_consent: false,
  family_consent: false,
  hire_date: null,
  employment_type: null,
  children_ages: null,
  household_size: null,
}
export const STATUS_LABEL = {
  eligible: '조건에 맞아요',
  needs_review: '추가 확인이 필요해요',
  ineligible: '현재 조건에 해당 없어요',
}
export const EMPLOYMENT_LABEL = {
  regular: '정규직',
  fixed_term: '기간제',
  part_time: '시간제',
}

export function consented(profile: Profile): Profile {
  return {
    ...profile,
    hire_date: profile.employment_consent ? profile.hire_date : null,
    employment_type: profile.employment_consent ? profile.employment_type : null,
    children_ages: profile.family_consent ? profile.children_ages : null,
    household_size: profile.family_consent ? profile.household_size : null,
  }
}
export function tenureYears(hired: string | null): number | null {
  if (!hired) return null
  const [y, m, d] = hired.split('-').map(Number)
  if (!y || !m || !d || hired > PREVIEW_DATE) return null
  return 2026 - y - (11 < m || (11 === m && 7 < d) ? 1 : 0)
}
export function previewBenefit(policy: Policy, input: Profile): PreviewBenefit {
  const p = consented(input)
  const checks: Check[] = []
  const check = (label: string, state: Check['state'], reason: string) =>
    checks.push({ label, state, reason })
  if (!p.employment_type)
    check('고용형태', 'unknown', '근무 정보 활용 동의와 고용형태를 확인해 주세요.')
  else
    check(
      '고용형태',
      policy.employment_types.includes(p.employment_type) ? 'pass' : 'fail',
      `${EMPLOYMENT_LABEL[p.employment_type]} · ${policy.employment_types.includes(p.employment_type) ? '예시 고용 조건에 맞아요.' : '예시 지원 대상에 포함되지 않아요.'}`,
    )
  const years = tenureYears(p.hire_date)
  if (policy.min_years)
    check(
      '근속기간',
      years === null ? 'unknown' : years >= policy.min_years ? 'pass' : 'fail',
      years === null
        ? '입사일 확인이 필요해요.'
        : `만 ${years}년 근속 · ${policy.min_years}년 이상 조건이에요.`,
    )
  if (policy.child_max_age !== undefined) {
    const low = policy.child_min_age ?? 0,
      high = policy.child_max_age
    const matching = p.children_ages?.filter((a) => low <= a && a <= high)
    check(
      '자녀 연령',
      p.children_ages === null ? 'unknown' : matching?.length ? 'pass' : 'fail',
      p.children_ages === null
        ? '가족 정보 동의와 자녀 나이 확인이 필요해요.'
        : matching?.length
          ? `만 ${Math.min(...matching)}세 자녀가 예시 연령 조건에 맞아요.`
          : `만 ${low}~${high}세 자녀 조건에 해당하지 않아요.`,
    )
  }
  if (policy.household_min)
    check(
      '가구 구성',
      p.household_size === null
        ? 'unknown'
        : p.household_size >= policy.household_min
          ? 'pass'
          : 'fail',
      p.household_size === null
        ? '가구원 수 확인이 필요해요.'
        : `가구원 ${p.household_size}명 · ${policy.household_min}명 이상 조건이에요.`,
    )
  if (policy.unresolved)
    check(
      '추가 조건',
      'unknown',
      policy.unresolved_reason ?? '소득·주택·중복 지원 조건을 담당 부서에 확인해야 해요.',
    )
  const daysLeft = policy.deadline
    ? Math.round((Date.parse(policy.deadline) - Date.parse(PREVIEW_DATE)) / 86400000)
    : null
  if (daysLeft !== null && daysLeft < 0) check('접수기간', 'fail', '예시 신청 기간이 지났어요.')
  const status = checks.some((c) => c.state === 'fail')
    ? 'ineligible'
    : checks.some((c) => c.state === 'unknown')
      ? 'needs_review'
      : 'eligible'
  const priority = ['자녀 연령', '가구 구성', '근속기간', '고용형태']
  const reason =
    checks.find((c) => c.state === 'fail')?.reason ??
    checks.find((c) => c.state === 'unknown')?.reason ??
    [...checks].sort((a, b) => priority.indexOf(a.label) - priority.indexOf(b.label))[0]?.reason ??
    '예시 조건을 확인해 주세요.'
  return { ...policy, status, checks, reason, daysLeft }
}
export function deadlineLabel(policy: PreviewBenefit) {
  return policy.daysLeft === null
    ? policy.period
    : policy.daysLeft < 0
      ? '기간 종료'
      : policy.daysLeft === 0
        ? '오늘 마감 · 예시'
        : `D-${policy.daysLeft} · ${policy.deadline?.slice(5).replace('-', '.')}까지`
}
