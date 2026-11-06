import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { Button, Chip, PageHeader } from '../components/ui'
import { dotDate } from '../lib/format'
import { DocStatusBadge } from './shared'

const GRID = 'grid grid-cols-[minmax(0,2fr)_130px_150px_110px_100px] items-center gap-2 px-[18px]'

export function DocumentsPage() {
  const qc = useQueryClient()
  const [collection, setCollection] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [uploadTo, setUploadTo] = useState('hr')
  const [showUpload, setShowUpload] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const collections = useQuery({ queryKey: ['admin', 'collections'], queryFn: api.listCollections })
  // 처리 중인 문서가 있으면 상태가 바뀔 때까지 주기적으로 다시 불러온다
  const docs = useQuery({
    queryKey: ['admin', 'documents'],
    queryFn: api.listDocuments,
    refetchInterval: (query) => (query.state.data?.some((d) => d.status === 'processing') ? 2000 : false),
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin'] })
  const upload = useMutation({
    mutationFn: (files: File[]) => Promise.all(files.map((f) => api.uploadDocument(f, uploadTo))),
    onSuccess: () => { setShowUpload(false); void invalidate() },
  })
  const retry = useMutation({ mutationFn: api.retryDocument, onSuccess: invalidate })

  const colName = (id: string) => collections.data?.find((c) => c.id === id)?.name ?? id
  const total = collections.data?.reduce((n, c) => n + c.docCount, 0) ?? 0
  const rows = (docs.data ?? []).filter(
    (d) => (!collection || d.collectionId === collection) && d.name.toLowerCase().includes(q.trim().toLowerCase()),
  )

  return (
    <>
      <PageHeader title="문서 관리">
        <Button variant="primary" onClick={() => setShowUpload((v) => !v)}>+ 문서 업로드</Button>
      </PageHeader>

      {showUpload && (
        <div className="mx-7 mt-5 flex items-center gap-3 rounded-xl border border-sel-line bg-sel-card px-[18px] py-3.5 text-sm">
          <span className="font-medium">업로드할 컬렉션</span>
          <select value={uploadTo} onChange={(e) => setUploadTo(e.target.value)} className="rounded-lg border border-line-strong bg-panel px-3 py-1.5 text-[13px]">
            {collections.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <Button variant="primary" disabled={upload.isPending} onClick={() => fileInput.current?.click()}>
            {upload.isPending ? '올리는 중…' : '파일 선택'}
          </Button>
          <span className="text-xs text-muted">텍스트 PDF만 지원 · 업로드 후 Dense 색인 · 스캔본 OCR 미지원</span>
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            accept=".pdf"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? [])
              if (files.length) upload.mutate(files)
              e.target.value = ''
            }}
          />
          <button type="button" onClick={() => setShowUpload(false)} className="ml-auto text-lg text-muted" aria-label="닫기">×</button>
        </div>
      )}

      {upload.isError && <div role="alert" className="mx-7 mt-3 text-sm text-err">업로드 또는 색인 요청에 실패했습니다. PDF 파일 및 서버 연결을 확인해 주세요.</div>}
      {retry.isError && <div role="alert" className="mx-7 mt-3 text-sm text-err">색인 재시도 요청에 실패했습니다.</div>}
      <div className="flex items-center justify-between gap-4 px-7 pt-5">
        <div className="flex flex-wrap gap-1.5">
          <Chip active={!collection} onClick={() => setCollection(null)}>전체 {total}</Chip>
          {collections.data?.map((c) => (
            <Chip key={c.id} active={collection === c.id} onClick={() => setCollection(c.id)}>{c.name} {c.docCount}</Chip>
          ))}
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="파일명 검색"
          aria-label="파일명 검색"
          className="h-[34px] w-[220px] rounded-lg border border-line bg-panel px-3 text-[13px] outline-none placeholder:text-faint focus:border-line-strong"
        />
      </div>

      <div className="mx-7 mt-4 mb-6 flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-line bg-panel">
        <div className={`${GRID} border-b border-line py-[11px] text-xs text-faint`}>
          <span>파일명</span><span>컬렉션</span><span>열람 권한</span><span>등록일</span><span>상태</span>
        </div>
        <div className="overflow-y-auto">
          {rows.map((d) => (
            <div key={d.id} className={`${GRID} border-b border-row py-[13px] text-sm last:border-b-0`}>
              <span className="truncate">{d.name}</span>
              <span className="text-ink-2">{colName(d.collectionId)}</span>
              <span className="text-ink-2">{d.access}</span>
              <span className="text-muted">{dotDate(d.uploadedAt)}</span>
              <DocStatusBadge status={d.status} onRetry={() => retry.mutate(d.id)} />
            </div>
          ))}
          {docs.data && rows.length === 0 && <div className="px-[18px] py-8 text-center text-sm text-faint">조건에 맞는 문서가 없어요</div>}
        </div>
      </div>
    </>
  )
}
