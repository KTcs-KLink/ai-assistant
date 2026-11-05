export type Role = 'user' | 'admin'

export interface User {
  id: string
  name: string
  dept: string
  role: Role
}

export interface Citation {
  id: string
  /** 본문에 표시되는 번호 — 사내 문서는 "1", 첨부 파일은 "p.4" */
  label: string
  docName: string
  /** 조항·쪽수 등 출처 위치 설명 (예: "제23조 연차휴가의 이월 · p.14") */
  section: string
  page?: number
  /** 강조할 인용문 */
  quote?: string
  /** 첨부 파일: 해당 쪽 원문 소제목 / 본문 (quote 가 포함된 문단) */
  heading?: string
  context?: string
  source: 'kb' | 'attachment'
}

export interface Attachment {
  id: string
  name: string
  size: number
  pages?: number
}

export type Feedback = 'up' | 'down' | null

export interface Message {
  id: string
  role: 'user' | 'assistant'
  /** 본문. **굵게**, 인용은 [[citationId]] 마커, 문단은 빈 줄로 구분 */
  content: string
  citations: Citation[]
  attachments?: Attachment[]
  /** "문서 3건에서 검색함" 같은 검색 요약 */
  searchNote?: string
  feedback?: Feedback
  createdAt: string
}

export interface Conversation {
  id: string
  title: string
  updatedAt: string
}

/** SSE 이벤트 (FastAPI StreamingResponse, `data: {json}\n\n`) */
export type StreamEvent =
  | { type: 'meta'; searchNote?: string; citations: Citation[] }
  | { type: 'delta'; text: string }
  | { type: 'done'; messageId: string }
  | { type: 'error'; message: string }

// ---------- 관리자 ----------

export interface Stats {
  questions: number
  activeUsers: number
  helpfulRate: number
}

export interface Collection {
  id: string
  name: string
  docCount: number
  lastSync: string | null
  status: 'ok' | 'indexing' | 'error'
  progress?: number
  errorCount?: number
}

export type DocStatus = 'ready' | 'processing' | 'error'

export interface KbDocument {
  id: string
  name: string
  collectionId: string
  access: string
  uploadedAt: string
  status: DocStatus
}

export interface Department {
  id: string
  name: string
  headcount: number
  /** collectionId → 열람 가능 여부 */
  perms: Record<string, boolean>
}

export interface PermissionException {
  id: string
  userName: string
  dept: string
  collectionId: string
  type: 'add' | 'remove'
  reason: string
  until?: string
}

export interface DirectoryUser {
  id: string
  name: string
  dept: string
  email: string
  role: Role
  lastActiveAt: string
}

export type FeedbackCause = '문서 누락' | '검색 실패' | '답변 오류' | '권한 없음'

export interface FeedbackItem {
  id: string
  question: string
  answer: string
  comment: string
  /** 답변의 출처 컬렉션 — 없으면 null ("출처 없음") */
  collectionName: string | null
  userName: string
  dept: string
  createdAt: string
  status: 'open' | 'done'
  causes: FeedbackCause[]
  memo: string
  conversationId?: string
}

export interface Settings {
  model: string
  refuseWithoutSource: boolean
  allowAttachments: boolean
  formats: string[]
  maxSizeMb: number
  chatRetentionDays: number
  attachmentRetentionDays: number
}
