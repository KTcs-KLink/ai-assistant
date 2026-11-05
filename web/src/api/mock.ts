// 백엔드 없이 화면을 돌려보기 위한 인메모리 목 API. 새로고침하면 초기화된다.
import { scriptAnswer } from './answers'
import { ApiError } from './errors'
import type {
  Attachment, Citation, Collection, Conversation, Department, DirectoryUser, FeedbackItem, KbDocument,
  Message, PermissionException, Settings, Stats, StreamEvent, User,
} from './types'

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))
const uid = () => Math.random().toString(36).slice(2, 10)
const ago = (min: number) => new Date(Date.now() - min * 60_000).toISOString()
const DAY = 24 * 60

// ---------- 인증 ----------

const SESSION_KEY = 'klink.mock.session'
// 목 모드 로그인 계정 (아이디 → 사용자). 비밀번호는 모두 MOCK_PASSWORD
const mockAccounts: Record<string, User> = {
  klink123: { id: 'u-kjh', name: '김지현', dept: '경영지원팀', role: 'admin' },
  klink: { id: 'u-psj', name: '박서준', dept: '영업1팀', role: 'user' },
}
const MOCK_PASSWORD = (import.meta.env.VITE_MOCK_PASSWORD as string | undefined) || 'klink1234'

const findMockUser = (id: string) => Object.values(mockAccounts).find((u) => u.id === id) ?? null

// ---------- 채팅 ----------

const conversations: Conversation[] = []
const messages = new Map<string, Message[]>()

function seedConversation(title: string, minutesAgo: number, question?: string, attachments?: Attachment[]) {
  const id = uid()
  conversations.push({ id, title, updatedAt: ago(minutesAgo) })
  const list: Message[] = []
  if (question) {
    const a = scriptAnswer(question, attachments)
    list.push(
      { id: uid(), role: 'user', content: question, citations: [], attachments, createdAt: ago(minutesAgo + 1) },
      { id: uid(), role: 'assistant', content: a.content, citations: a.citations, searchNote: a.searchNote, feedback: null, createdAt: ago(minutesAgo) },
    )
  }
  messages.set(id, list)
}

seedConversation('연차 이월 규정 문의', 12, '올해 남은 연차를 내년으로 이월할 수 있어? 며칠까지 가능한지 알려줘')
seedConversation('3분기 영업 보고서 요약', DAY + 30, '이거 핵심만 요약해줘. 전 분기 대비 달라진 점 위주로', [
  { id: 'f-3q', name: '2026_3Q_영업실적보고.pdf', size: 4.2 * 1024 * 1024, pages: 28 },
])
seedConversation('출장비 정산 절차', DAY + 200, '출장비 정산은 어떻게 해?')
seedConversation('신규 입사자 온보딩 체크리스트', 3 * DAY)
seedConversation('VPN 접속 오류 해결', 4 * DAY)
seedConversation('주간 회의록 초안 작성', 5 * DAY)

function touch(conversationId: string) {
  const c = conversations.find((x) => x.id === conversationId)
  if (c) c.updatedAt = new Date().toISOString()
}

function lastUserMessage(conversationId: string): Message | undefined {
  return [...(messages.get(conversationId) ?? [])].reverse().find((m) => m.role === 'user')
}

/** 답변 본문을 토큰 단위(인용 마커·굵게 표시는 한 번에)로 쪼갠다 */
function tokenize(text: string): string[] {
  const out: string[] = []
  for (const part of text.split(/(\[\[[^\]]+\]\]|\*\*)/)) {
    if (!part) continue
    if (part.startsWith('[[') || part === '**') out.push(part)
    else out.push(...part.match(/.{1,2}/gsu)!)
  }
  return out
}

async function* streamScripted(conversationId: string, question: string, attachments: Attachment[] | undefined, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  const answer = scriptAnswer(question, attachments)
  const msg: Message = {
    id: uid(), role: 'assistant', content: '', citations: answer.citations,
    searchNote: answer.searchNote, feedback: null, createdAt: new Date().toISOString(),
  }
  try {
    await wait(500)
    yield { type: 'meta', searchNote: answer.searchNote, citations: answer.citations }
    for (const tok of tokenize(answer.content)) {
      if (signal?.aborted) return
      await wait(tok.length > 2 ? 0 : 22)
      msg.content += tok
      yield { type: 'delta', text: tok }
    }
    yield { type: 'done', messageId: msg.id }
  } finally {
    // 중지해도 그때까지 받은 내용은 저장 (실제 백엔드와 같은 동작을 가정)
    if (msg.content) {
      messages.get(conversationId)?.push(msg)
      touch(conversationId)
    }
  }
}

// ---------- 관리자 ----------

const collections: Collection[] = [
  { id: 'hr', name: '인사/복리후생', docCount: 142, lastSync: '오늘 09:00', status: 'ok' },
  { id: 'rule', name: '사내 규정', docCount: 58, lastSync: '오늘 09:00', status: 'ok' },
  { id: 'sales', name: '영업/마케팅', docCount: 311, lastSync: null, status: 'indexing', progress: 64 },
  { id: 'it', name: 'IT 지원', docCount: 97, lastSync: '10.24 18:30', status: 'error', errorCount: 3 },
]

const documents: KbDocument[] = [
  { id: uid(), name: '인사규정_v4.2.pdf', collectionId: 'hr', access: '전 직원', uploadedAt: '2026-01-05', status: 'ready' },
  { id: uid(), name: '2026 복리후생 안내.docx', collectionId: 'hr', access: '전 직원', uploadedAt: '2026-01-12', status: 'ready' },
  { id: uid(), name: '2026_3Q_영업실적보고.pdf', collectionId: 'sales', access: '영업본부, 임원', uploadedAt: '2026-10-24', status: 'processing' },
  { id: uid(), name: '여비규정_2025개정.pdf', collectionId: 'rule', access: '전 직원', uploadedAt: '2025-12-18', status: 'ready' },
  { id: uid(), name: 'VPN_접속가이드.pptx', collectionId: 'it', access: '전 직원', uploadedAt: '2026-10-24', status: 'error' },
  { id: uid(), name: '임원 보수 규정.pdf', collectionId: 'rule', access: '임원, 인사팀', uploadedAt: '2026-03-02', status: 'ready' },
  { id: uid(), name: '법인카드 운영규정.pdf', collectionId: 'rule', access: '전 직원', uploadedAt: '2026-02-11', status: 'ready' },
  { id: uid(), name: '재택근무 운영지침.pdf', collectionId: 'hr', access: '전 직원', uploadedAt: '2026-04-01', status: 'ready' },
  { id: uid(), name: '사내망 계정 신청 안내.docx', collectionId: 'it', access: '전 직원', uploadedAt: '2026-06-17', status: 'ready' },
]

const departments: Department[] = [
  { id: 'd1', name: '경영지원팀', headcount: 18, perms: { hr: true, rule: true, sales: true, it: true } },
  { id: 'd2', name: '인사팀', headcount: 9, perms: { hr: true, rule: true, sales: false, it: true } },
  { id: 'd3', name: '영업1팀', headcount: 42, perms: { hr: true, rule: true, sales: true, it: false } },
  { id: 'd4', name: '개발팀', headcount: 57, perms: { hr: true, rule: true, sales: false, it: true } },
  { id: 'd5', name: '재무팀', headcount: 14, perms: { hr: true, rule: true, sales: false, it: false } },
]

const exceptions: PermissionException[] = [
  { id: uid(), userName: '박서준', dept: '영업1팀', collectionId: 'it', type: 'add', reason: '프로젝트 지원', until: '12.31' },
  { id: uid(), userName: '정유나', dept: '재무팀', collectionId: 'sales', type: 'add', reason: '3분기 결산' },
  { id: uid(), userName: '이하은', dept: '개발팀', collectionId: 'rule', type: 'remove', reason: '외부 파견' },
]

const directory: DirectoryUser[] = [
  { id: 'u-kjh', name: '김지현', dept: '경영지원팀', email: 'jihyun.kim@company.com', role: 'admin', lastActiveAt: ago(2) },
  { id: uid(), name: '박서준', dept: '영업1팀', email: 'seojun.park@company.com', role: 'user', lastActiveAt: ago(95) },
  { id: uid(), name: '정유나', dept: '재무팀', email: 'yuna.jung@company.com', role: 'user', lastActiveAt: ago(300) },
  { id: uid(), name: '이하은', dept: '개발팀', email: 'haeun.lee@company.com', role: 'user', lastActiveAt: ago(DAY + 40) },
  { id: uid(), name: '최민호', dept: '개발팀', email: 'minho.choi@company.com', role: 'admin', lastActiveAt: ago(30) },
  { id: uid(), name: '한소희', dept: '인사팀', email: 'sohee.han@company.com', role: 'admin', lastActiveAt: ago(DAY * 2) },
  { id: uid(), name: '오준혁', dept: '경영지원팀', email: 'junhyuk.oh@company.com', role: 'admin', lastActiveAt: ago(DAY * 3) },
  { id: uid(), name: '윤다은', dept: '영업1팀', email: 'daeun.yoon@company.com', role: 'user', lastActiveAt: ago(DAY * 6) },
]

const feedback: FeedbackItem[] = [
  {
    id: uid(), question: '해외 출장 일비 기준이 뭐야? 미국 출장 기준으로', status: 'open',
    answer: '검색 가능한 사내 문서에서 해외 출장 일비 기준을 찾지 못했습니다. 인사팀 또는 재무팀에 문의해 주세요.',
    comment: '여비규정에 있는 걸로 아는데 못 찾네요', collectionName: null, userName: '박서준', dept: '영업1팀',
    createdAt: ago(120), causes: ['문서 누락'], memo: '',
  },
  {
    id: uid(), question: '사내 와이파이 비밀번호 변경 주기', status: 'open',
    answer: '사내 와이파이 비밀번호는 분기마다 변경됩니다. 변경된 비밀번호는 IT 공지 게시판에서 확인할 수 있습니다.',
    comment: '지금은 매월 바뀌는 걸로 알고 있어요', collectionName: 'IT 지원', userName: '이하은', dept: '개발팀',
    createdAt: ago(DAY + 60), causes: [], memo: '',
  },
  {
    id: uid(), question: '육아휴직 중 성과급 지급 여부', status: 'open',
    answer: '육아휴직 기간 중에는 성과급이 지급되지 않습니다.',
    comment: '휴직 전 근무 기간만큼은 나온다고 들었습니다', collectionName: '인사/복리후생', userName: '정유나', dept: '재무팀',
    createdAt: ago(2 * DAY + 100), causes: [], memo: '',
  },
  {
    id: uid(), question: '사내 동호회 지원금 신청', status: 'open',
    answer: '검색 가능한 사내 문서에서 동호회 지원금 관련 내용을 찾지 못했습니다.',
    comment: '', collectionName: null, userName: '윤다은', dept: '인사팀',
    createdAt: ago(3 * DAY), causes: [], memo: '',
  },
  {
    id: uid(), question: '명함 신청은 어디서 해?', status: 'done',
    answer: '명함은 총무팀에 메일로 신청합니다.', comment: '그룹웨어로 바뀌었어요', collectionName: '사내 규정',
    userName: '최민호', dept: '개발팀', createdAt: ago(6 * DAY), causes: ['답변 오류'], memo: '구버전 문서 삭제 완료',
  },
]

let settings: Settings = {
  model: 'K-LLM 2.1', refuseWithoutSource: true, allowAttachments: true,
  formats: ['PDF', 'DOCX', 'XLSX', 'PPTX'], maxSizeMb: 20, chatRetentionDays: 180, attachmentRetentionDays: 7,
}

function collectionOf(c: Citation | undefined): string | null {
  if (!c) return null
  if (c.source === 'attachment') return '첨부 파일'
  const doc = documents.find((d) => d.name === c.docName)
  return collections.find((x) => x.id === doc?.collectionId)?.name ?? c.docName
}

const clone = <T,>(v: T): T => structuredClone(v)

export const mockApi = {
  async me(): Promise<User | null> {
    await wait(150)
    const id = sessionStorage.getItem(SESSION_KEY)
    return id ? findMockUser(id) : null
  },
  async login(username: string, password: string): Promise<User> {
    await wait(400)
    const found = mockAccounts[username.trim().toLowerCase()]
    if (!found || password !== MOCK_PASSWORD) throw new ApiError(401, '아이디 또는 비밀번호가 올바르지 않아요.')
    sessionStorage.setItem(SESSION_KEY, found.id)
    return found
  },
  async logout() {
    sessionStorage.removeItem(SESSION_KEY)
  },

  async listConversations(): Promise<Conversation[]> {
    await wait(120)
    return clone([...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)))
  },
  async createConversation(title: string): Promise<Conversation> {
    await wait(80)
    const c = { id: uid(), title, updatedAt: new Date().toISOString() }
    conversations.push(c)
    messages.set(c.id, [])
    return clone(c)
  },
  async getMessages(conversationId: string): Promise<Message[]> {
    await wait(150)
    const list = messages.get(conversationId)
    if (!list) throw new Error('대화를 찾을 수 없습니다')
    return clone(list)
  },
  async uploadAttachment(file: File): Promise<Attachment> {
    await wait(400)
    const isPdf = /\.pdf$/i.test(file.name)
    return { id: uid(), name: file.name, size: file.size, pages: isPdf ? Math.max(1, Math.round(file.size / 150_000)) : undefined }
  },
  async *sendMessage(conversationId: string, text: string, attachments: Attachment[], signal?: AbortSignal) {
    messages.get(conversationId)?.push({
      id: uid(), role: 'user', content: text, citations: [], attachments, createdAt: new Date().toISOString(),
    })
    touch(conversationId)
    yield* streamScripted(conversationId, text, attachments, signal)
  },
  async *regenerate(conversationId: string, messageId: string, signal?: AbortSignal) {
    const list = messages.get(conversationId) ?? []
    const idx = list.findIndex((m) => m.id === messageId)
    if (idx >= 0) list.splice(idx, 1)
    const q = lastUserMessage(conversationId)
    yield* streamScripted(conversationId, q?.content ?? '', q?.attachments, signal)
  },
  async setFeedback(conversationId: string, messageId: string, value: Message['feedback'], comment?: string) {
    await wait(100)
    const list = messages.get(conversationId) ?? []
    const m = list.find((x) => x.id === messageId)
    if (!m) return
    m.feedback = value
    if (value === 'down') {
      const q = list[list.indexOf(m) - 1]
      const me = findMockUser(sessionStorage.getItem(SESSION_KEY) ?? '') ?? mockAccounts.klink123
      feedback.unshift({
        id: uid(), question: q?.content ?? '', answer: m.content.replace(/\[\[[^\]]+\]\]|\*\*/g, ''),
        comment: comment ?? '', collectionName: collectionOf(m.citations[0]),  userName: me.name,
        dept: me.dept, createdAt: new Date().toISOString(), status: 'open', causes: [], memo: '', conversationId,
      })
    }
  },

  // 관리자
  async getStats(days: number): Promise<Stats> {
    await wait(150)
    return days === 7 ? { questions: 4812, activeUsers: 386, helpfulRate: 87 } : { questions: 19_430, activeUsers: 402, helpfulRate: 85 }
  },
  async listCollections(): Promise<Collection[]> {
    await wait(120)
    return clone(collections)
  },
  async listDocuments(): Promise<KbDocument[]> {
    await wait(150)
    return clone(documents)
  },
  async uploadDocument(file: File, collectionId: string): Promise<KbDocument> {
    await wait(300)
    const doc: KbDocument = {
      id: uid(), name: file.name, collectionId, access: '전 직원',
      uploadedAt: new Date().toISOString().slice(0, 10), status: 'processing',
    }
    documents.unshift(doc)
    const col = collections.find((c) => c.id === collectionId)
    if (col) col.docCount++
    setTimeout(() => { doc.status = 'ready' }, 4000)
    return clone(doc)
  },
  async retryDocument(id: string) {
    await wait(200)
    const doc = documents.find((d) => d.id === id)
    if (!doc) return
    doc.status = 'processing'
    setTimeout(() => { doc.status = 'ready' }, 3000)
  },
  async listDepartments(): Promise<Department[]> {
    await wait(120)
    return clone(departments)
  },
  async setDepartmentPermission(deptId: string, collectionId: string, allowed: boolean) {
    await wait(80)
    const d = departments.find((x) => x.id === deptId)
    if (d) d.perms[collectionId] = allowed
  },
  async listExceptions(): Promise<PermissionException[]> {
    await wait(120)
    return clone(exceptions)
  },
  async addException(e: Omit<PermissionException, 'id'>) {
    await wait(120)
    exceptions.push({ ...e, id: uid() })
  },
  async removeException(id: string) {
    await wait(80)
    const i = exceptions.findIndex((x) => x.id === id)
    if (i >= 0) exceptions.splice(i, 1)
  },
  async listUsers(): Promise<DirectoryUser[]> {
    await wait(120)
    return clone(directory)
  },
  async listFeedback(): Promise<FeedbackItem[]> {
    await wait(150)
    return clone(feedback)
  },
  async updateFeedback(id: string, patch: Partial<Pick<FeedbackItem, 'causes' | 'memo' | 'status'>>) {
    await wait(120)
    const f = feedback.find((x) => x.id === id)
    if (f) Object.assign(f, patch)
  },
  async getSettings(): Promise<Settings> {
    await wait(120)
    return clone(settings)
  },
  async saveSettings(next: Settings) {
    await wait(300)
    settings = clone(next)
  },
}
