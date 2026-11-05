// VITE_API_BASE_URL 이 있으면 FastAPI 백엔드를, 없으면 목 API를 쓴다.
// 엔드포인트 경로는 백엔드와 합의 전 가안이다.
import { ApiError } from './errors'
import { mockApi } from './mock'
import type {
  Attachment, Collection, Conversation, Department, DirectoryUser, FeedbackItem, KbDocument,
  Message, PermissionException, Settings, Stats, StreamEvent, User,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''
export const USE_MOCK = !BASE

export { ApiError }

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include', // 로그인 세션 쿠키
    ...init,
    headers: { ...(isForm || !init.body ? {} : { 'Content-Type': 'application/json' }), ...init.headers },
  })
  if (!res.ok) throw new ApiError(res.status, (await res.text()) || res.statusText)
  return res.status === 204 ? (undefined as T) : res.json()
}

const json = (body: unknown) => JSON.stringify(body)

/** SSE 스트림(`data: {...}\n\n`)을 StreamEvent 로 풀어낸다 */
async function* sse(path: string, body: unknown, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST', credentials: 'include', signal, body: json(body),
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
  })
  if (!res.ok || !res.body) throw new ApiError(res.status, res.statusText)
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += value
      let sep: number
      while ((sep = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, sep)
        buf = buf.slice(sep + 2)
        const data = chunk.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trimStart()).join('\n')
        if (data) yield JSON.parse(data) as StreamEvent
      }
    }
  } catch (e) {
    if ((e as Error).name !== 'AbortError') throw e
  } finally {
    reader.releaseLock()
  }
}

const httpApi: typeof mockApi = {
  async me() {
    try {
      return await request<User>('/api/auth/me')
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return null
      throw e
    }
  },
  async login(username, password) {
    try {
      return await request<User>('/api/auth/login', { method: 'POST', body: json({ username, password }) })
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) throw new ApiError(401, '아이디 또는 비밀번호가 올바르지 않아요.')
      throw e
    }
  },
  logout: () => request('/api/auth/logout', { method: 'POST' }),

  listConversations: () => request<Conversation[]>('/api/conversations'),
  createConversation: (title) => request<Conversation>('/api/conversations', { method: 'POST', body: json({ title }) }),
  getMessages: (id) => request<Message[]>(`/api/conversations/${id}/messages`),
  uploadAttachment(file) {
    const fd = new FormData()
    fd.append('file', file)
    return request<Attachment>('/api/attachments', { method: 'POST', body: fd })
  },
  sendMessage: (id, text, attachments, signal) =>
    sse(`/api/conversations/${id}/messages`, { content: text, attachment_ids: attachments.map((a) => a.id) }, signal),
  regenerate: (id, messageId, signal) => sse(`/api/conversations/${id}/messages/${messageId}/regenerate`, {}, signal),
  setFeedback: (id, messageId, value, comment) =>
    request(`/api/conversations/${id}/messages/${messageId}/feedback`, { method: 'PUT', body: json({ value, comment }) }),

  getStats: (days) => request<Stats>(`/api/admin/stats?days=${days}`),
  listCollections: () => request<Collection[]>('/api/admin/collections'),
  listDocuments: () => request<KbDocument[]>('/api/admin/documents'),
  uploadDocument(file, collectionId) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('collection_id', collectionId)
    return request<KbDocument>('/api/admin/documents', { method: 'POST', body: fd })
  },
  retryDocument: (id) => request(`/api/admin/documents/${id}/retry`, { method: 'POST' }),
  listDepartments: () => request<Department[]>('/api/admin/departments'),
  setDepartmentPermission: (deptId, collectionId, allowed) =>
    request(`/api/admin/departments/${deptId}/permissions/${collectionId}`, { method: 'PUT', body: json({ allowed }) }),
  listExceptions: () => request<PermissionException[]>('/api/admin/permission-exceptions'),
  addException: (e) => request('/api/admin/permission-exceptions', { method: 'POST', body: json(e) }),
  removeException: (id) => request(`/api/admin/permission-exceptions/${id}`, { method: 'DELETE' }),
  listUsers: () => request<DirectoryUser[]>('/api/admin/users'),
  listFeedback: () => request<FeedbackItem[]>('/api/admin/feedback'),
  updateFeedback: (id, patch) => request(`/api/admin/feedback/${id}`, { method: 'PATCH', body: json(patch) }),
  getSettings: () => request<Settings>('/api/admin/settings'),
  saveSettings: (s) => request('/api/admin/settings', { method: 'PUT', body: json(s) }),
}

export const api = USE_MOCK ? mockApi : httpApi
