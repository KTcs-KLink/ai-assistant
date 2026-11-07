import { useEffect, useId, useRef, type ReactNode, type KeyboardEvent } from 'react'
import {
  ArrowRight,
  Award,
  Bookmark,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  Gift,
  GraduationCap,
  Heart,
  Home,
  Info,
  Leaf,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { useWorkspace } from './WorkspaceContext'
import { deadlineLabel, STATUS_LABEL } from './model'
import type { PreviewBenefit, Status } from './types'

export const BENEFIT_ICONS = {
  family: Heart,
  leave: Leaf,
  learning: BookOpen,
  award: Award,
  school: GraduationCap,
  home: Home,
}
// Arrow, Home and End keys activate the neighboring tab while retaining focus.
export function handleTabKey(event: KeyboardEvent<HTMLDivElement>) {
  const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
  const current = tabs.indexOf(document.activeElement as HTMLButtonElement)
  if (current < 0) return
  const next =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? tabs.length - 1
        : event.key === 'ArrowRight'
          ? (current + 1) % tabs.length
          : event.key === 'ArrowLeft'
            ? (current - 1 + tabs.length) % tabs.length
            : -1
  if (next < 0) return
  event.preventDefault()
  tabs[next].focus()
  tabs[next].click()
}
export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="kl-brand">
      <span className="kl-brand-mark">
        <Sparkles size={22} strokeWidth={1.7} />
      </span>
      {!compact && (
        <span>
          K:LINK<small>일과 일상을 더 가깝게</small>
        </span>
      )}
    </span>
  )
}
export function BenefitIcon({ benefit, size = 23 }: { benefit: PreviewBenefit; size?: number }) {
  const Icon = BENEFIT_ICONS[benefit.icon as keyof typeof BENEFIT_ICONS] ?? Gift
  return (
    <span className={`kl-benefit-icon ${benefit.icon}`}>
      <Icon size={size} strokeWidth={1.7} />
    </span>
  )
}
export function StatusBadge({ status, short = false }: { status: Status; short?: boolean }) {
  return (
    <span className={`kl-badge ${status}`}>
      {status === 'eligible' ? (
        <CheckCircle2 size={12} />
      ) : status === 'needs_review' ? (
        <Info size={12} />
      ) : (
        <span className="kl-dot" />
      )}
      {short
        ? {
            eligible: '조건 충족',
            needs_review: '추가 확인',
            ineligible: '해당 없음',
          }[status]
        : STATUS_LABEL[status]}
      <span className="kl-badge-example">예시</span>
    </span>
  )
}
export function Modal({
  title,
  subtitle,
  children,
  close,
  drawer = false,
  wide = false,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  close: () => void
  drawer?: boolean
  wide?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null),
    id = useId()
  useEffect(() => {
    const dialog = ref.current
    dialog?.showModal()
    return () => dialog?.close()
  }, [])
  return (
    <dialog
      ref={ref}
      className={`kl-dialog ${drawer ? 'drawer' : ''} ${wide ? 'wide' : ''}`}
      aria-labelledby={id}
      onCancel={(e) => {
        e.preventDefault()
        close()
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) close()
      }}
    >
      <div className="kl-dialog-surface">
        <header>
          <div>
            <h2 id={id}>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="kl-icon-button" aria-label="닫기" onClick={close}>
            <X size={20} />
          </button>
        </header>
        {children}
      </div>
    </dialog>
  )
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="kl-page-heading">
      <div>
        {eyebrow && <span className="kl-eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  )
}
export function EmptyState({
  title,
  description,
  children,
  icon: Icon = Search,
}: {
  title: string
  description: string
  children?: ReactNode
  icon?: typeof Search
}) {
  return (
    <div className="kl-empty">
      <span>
        <Icon size={27} strokeWidth={1.5} />
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {children}
    </div>
  )
}
export function BenefitCard({ benefit }: { benefit: PreviewBenefit }) {
  const { saved, toggleSaved, select, preparations } = useWorkspace()
  const bookmarked = saved.includes(benefit.id)
  return (
    <article className="kl-benefit-card" aria-labelledby={`title-${benefit.id}`}>
      <div className="kl-card-top">
        <BenefitIcon benefit={benefit} />
        <button
          className={`kl-icon-button ${bookmarked ? 'is-saved' : ''}`}
          aria-label={`${benefit.title} ${bookmarked ? '저장 취소' : '저장'}`}
          aria-pressed={bookmarked}
          onClick={() => toggleSaved(benefit.id)}
        >
          <Bookmark size={18} fill={bookmarked ? 'currentColor' : 'none'} />
        </button>
      </div>
      <div className="kl-card-category">{benefit.category}</div>
      <h3 id={`title-${benefit.id}`}>
        <button onClick={() => select(benefit.id)}>{benefit.title}</button>
      </h3>
      <p className="kl-card-description">{benefit.description}</p>
      <div className="kl-card-value">{benefit.value}</div>
      <p className="kl-card-value-note">{benefit.value_note}</p>
      <StatusBadge status={benefit.status} short />
      <p className="kl-card-reason">{benefit.reason}</p>
      <div className="kl-card-footer">
        <span>
          <Clock3 size={13} />
          {deadlineLabel(benefit)}
        </span>
        <button aria-label={`${benefit.title} 자세히 보기`} onClick={() => select(benefit.id)}>
          {preparations.some((d) => d.benefitId === benefit.id) ? '준비 중인 혜택' : '자세히 보기'}
          <ChevronRight size={15} />
        </button>
      </div>
    </article>
  )
}
export function SourceContent({ benefit }: { benefit: PreviewBenefit }) {
  return (
    <div className="kl-source-content">
      <div className="kl-source-stamp">
        <FileText size={18} />
        <div>
          <strong>화면 검증용 가상 복지 규정</strong>
          <span>{benefit.section} · demo-2026.11.07</span>
        </div>
        <span className="kl-tag">예시 규정</span>
      </div>
      <blockquote>{benefit.quote}</blockquote>
      <div className="kl-inline-note">
        <ShieldCheck size={16} />
        <p>
          회사에서 승인한 규정이 아닙니다. 실제 KTcs 적용 여부와 현행 규정은 별도 확인이 필요해요.
        </p>
      </div>
      <details className="kl-source-meta">
        <summary>
          출처 정보 자세히 보기 <ChevronRight size={14} />
        </summary>
        <dl>
          <div>
            <dt>출처 ID</dt>
            <dd>DEMO-{benefit.id}</dd>
          </div>
          <div>
            <dt>회사 범위</dt>
            <dd>가상 시연 자료 · KTcs 적용 미확인</dd>
          </div>
          <div>
            <dt>검토 상태</dt>
            <dd>실제 회사 승인 미완료</dd>
          </div>
        </dl>
      </details>
    </div>
  )
}
export function SectionTitle({
  title,
  count,
  children,
}: {
  title: string
  count?: number
  children?: ReactNode
}) {
  return (
    <div className="kl-section-title">
      <h2>
        {title}
        {count !== undefined && <span>{count}</span>}
      </h2>
      {children}
    </div>
  )
}
export function CheckRow({
  checked,
  title,
  description,
  onChange,
}: {
  checked: boolean
  title: string
  description?: string
  onChange: () => void
}) {
  return (
    <label className={`kl-check-row ${checked ? 'checked' : ''}`}>
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="kl-check-square">{checked && <Check size={13} />}</span>
      <span>
        <strong>{title}</strong>
        {description && <small>{description}</small>}
      </span>
    </label>
  )
}
export function ArrowLabel({ children }: { children: ReactNode }) {
  return (
    <span className="kl-arrow-label">
      {children}
      <ArrowRight size={15} />
    </span>
  )
}
