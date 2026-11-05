import type { Collection, DocStatus } from '../api/types'
import { Badge } from '../components/ui'

export function CollectionStatus({ c }: { c: Collection }) {
  if (c.status === 'ok') return <Badge tone="ok">정상</Badge>
  if (c.status === 'indexing') return <Badge tone="brand">인덱싱 {c.progress ?? 0}%</Badge>
  return <Badge tone="err">오류 {c.errorCount ?? 0}건</Badge>
}

export function DocStatusBadge({ status, onRetry }: { status: DocStatus; onRetry?: () => void }) {
  if (status === 'ready') return <Badge tone="ok">검색 가능</Badge>
  if (status === 'processing') return <Badge tone="brand">처리 중</Badge>
  return <Badge tone="err" onClick={onRetry}>오류 · 재시도</Badge>
}

export const feedbackMeta = (f: { collectionName: string | null; dept: string }, when: string) =>
  `${f.collectionName ?? '출처 없음'} · ${f.dept} · ${when}`
