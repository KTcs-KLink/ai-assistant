const pad = (n: number) => String(n).padStart(2, '0')

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

export function formatTimer(sec: number): string {
  return `${Math.floor(sec / 60)}:${pad(sec % 60)}`
}

function startOfDay(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
}

/** 오늘 / 어제 / 지난 7일 / 이전 */
export function historyGroup(iso: string, now = new Date()): string {
  const days = Math.round((startOfDay(now) - startOfDay(new Date(iso))) / 86_400_000)
  if (days <= 0) return '오늘'
  if (days === 1) return '어제'
  if (days < 7) return '지난 7일'
  return '이전'
}

/** "2시간 전" / "어제" / "10.23" */
export function relativeTime(iso: string, now = new Date()): string {
  const d = new Date(iso)
  const min = Math.floor((now.getTime() - d.getTime()) / 60_000)
  const group = historyGroup(iso, now)
  if (group === '오늘') {
    if (min < 1) return '방금'
    if (min < 60) return `${min}분 전`
    return `${Math.floor(min / 60)}시간 전`
  }
  if (group === '어제') return '어제'
  return `${d.getMonth() + 1}.${pad(d.getDate())}`
}

/** "10.26 11:42" */
export function shortDateTime(iso: string): string {
  const d = new Date(iso)
  return `${d.getMonth() + 1}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** "2026-01-05" → "2026.01.05" */
export function dotDate(ymd: string): string {
  return ymd.slice(0, 10).replaceAll('-', '.')
}
