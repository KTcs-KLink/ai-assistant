import type { ButtonHTMLAttributes, ReactNode } from 'react'

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')
export { cx }

/** 로고 자리표시 — 실제 K-LINK 로고로 교체 예정 */
export function Logo({ size = 26 }: { size?: number }) {
  return <div className="flex-none bg-brand" style={{ width: size, height: size, borderRadius: Math.round(size * 0.26) }} />
}

export function Avatar({ name }: { name: string }) {
  return (
    <div className="flex size-[30px] flex-none items-center justify-center rounded-full bg-line-strong text-xs font-semibold">
      {name.slice(0, 1)}
    </div>
  )
}

type Variant = 'primary' | 'outline'
export function Button({ variant = 'outline', className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...rest}
      className={cx(
        'rounded-md px-3 py-1.5 text-[13px] font-medium whitespace-nowrap transition-colors disabled:opacity-50',
        variant === 'primary'
          ? 'bg-brand text-white hover:bg-brand-strong'
          : 'border border-line bg-panel text-ink-2 hover:bg-side',
        className,
      )}
    />
  )
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cx('relative h-[22px] w-10 flex-none rounded-full transition-colors', checked ? 'bg-brand' : 'bg-line-strong')}
    >
      <span className={cx('absolute top-0.5 size-[18px] rounded-full bg-white transition-all', checked ? 'left-5' : 'left-0.5')} />
    </button>
  )
}

export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cx(
        'flex size-[18px] items-center justify-center justify-self-center rounded-[5px] text-xs text-white',
        checked ? 'bg-brand' : 'border-[1.5px] border-line-strong bg-panel hover:border-faint',
      )}
    >
      {checked && '✓'}
    </button>
  )
}

export type Tone = 'ok' | 'brand' | 'err' | 'neutral'
const toneClass: Record<Tone, string> = {
  ok: 'bg-ok-bg text-ok',
  brand: 'bg-sel text-brand-strong',
  err: 'bg-err-bg text-err',
  neutral: 'bg-row text-ink',
}
export function Badge({ tone, children, onClick }: { tone: Tone; children: ReactNode; onClick?: () => void }) {
  const cls = cx('justify-self-start rounded-[5px] px-2 py-[3px] text-xs whitespace-nowrap', toneClass[tone])
  return onClick ? (
    <button type="button" onClick={onClick} className={cx(cls, 'hover:brightness-95')}>{children}</button>
  ) : (
    <span className={cls}>{children}</span>
  )
}

/** pill 형태 필터 칩 — 선택 시 진한 배경 */
export function Chip({ active, children, onClick }: { active: boolean; children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx(
        'rounded-full px-3 py-1.5 text-[13px] whitespace-nowrap',
        active ? 'bg-ink text-white' : 'border border-line bg-panel hover:border-line-strong',
      )}
    >
      {children}
    </button>
  )
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx('rounded-xl border border-line bg-panel', className)}>{children}</div>
}

export function PageHeader({ title, children, className }: { title: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <header className={cx('flex h-14 flex-none items-center justify-between gap-4 border-b border-line px-7', className)}>
      <h1 className="truncate text-[15px] font-semibold">{title}</h1>
      {children}
    </header>
  )
}

export function MicIcon({ className }: { className?: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" className={className}>
      <rect x="5.5" y="1.5" width="5" height="8.5" rx="2.5" />
      <path d="M3 7.5a5 5 0 0 0 10 0M8 12.5v2" />
    </svg>
  )
}

export function Spinner() {
  return <div className="p-6 text-sm text-faint">불러오는 중…</div>
}
