import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { policies } from './catalog'
import { consented, INITIAL_PROFILE, BLANK_PROFILE, previewBenefit, PREVIEW_DATE } from './model'
import type { Preparation, PreviewBenefit, Profile, PreviewMessage } from './types'

interface WorkspaceState {
  profile: Profile
  benefits: PreviewBenefit[]
  saved: string[]
  preparations: Preparation[]
  messages: PreviewMessage[]
  setMessages: React.Dispatch<React.SetStateAction<PreviewMessage[]>>
  saveProfile: (p: Profile) => void
  revoke: () => void
  reset: () => void
  toggleSaved: (id: string) => void
  startPreparation: (id: string) => void
  toggleCheck: (id: string, index: number) => void
  removePreparation: (id: string) => void
  selectedId: string | null
  select: (id: string | null) => void
  toast: string
  announce: (message: string) => void
  clearToast: () => void
}
const WorkspaceContext = createContext<WorkspaceState | null>(null)
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile>(INITIAL_PROFILE)
  const [saved, setSaved] = useState<string[]>([])
  const [preparations, setPreparations] = useState<Preparation[]>([])
  const [messages, setMessages] = useState<PreviewMessage[]>([])
  const [selectedId, select] = useState<string | null>(null)
  const [toast, announce] = useState('')
  const clearToast = useCallback(() => announce(''), [])
  const benefits = useMemo(() => policies.map((p) => previewBenefit(p, profile)), [profile])
  const value: WorkspaceState = {
    profile,
    benefits,
    saved,
    preparations,
    messages,
    setMessages,
    selectedId,
    select,
    toast,
    announce,
    clearToast,
    saveProfile(p) {
      setProfile(consented(p))
      setPreparations((prev) => prev.map((d) => ({ ...d, checked: [] })))
      announce('추천 조건을 반영했어요. 준비 목록의 확인 항목도 새로 확인해 주세요.')
    },
    revoke() {
      setProfile(BLANK_PROFILE)
      setPreparations([])
      setMessages([])
      select(null)
      announce('동의를 철회하고 예시 조건과 준비 정보를 삭제했어요.')
    },
    reset() {
      setProfile(INITIAL_PROFILE)
      setSaved([])
      setPreparations([])
      setMessages([])
      select(null)
      announce('처음 예시 조건으로 돌아왔어요.')
    },
    toggleSaved(id) {
      setSaved((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
    },
    startPreparation(id) {
      setPreparations((prev) =>
        prev.some((d) => d.benefitId === id)
          ? prev
          : [...prev, { benefitId: id, checked: [], createdAt: PREVIEW_DATE }],
      )
      announce('신청 준비 목록에 담았어요. 실제 신청이 제출되지는 않아요.')
    },
    toggleCheck(id, index) {
      setPreparations((prev) =>
        prev.map((d) =>
          d.benefitId === id
            ? {
                ...d,
                checked: d.checked.includes(index)
                  ? d.checked.filter((x) => x !== index)
                  : [...d.checked, index],
              }
            : d,
        ),
      )
    },
    removePreparation(id) {
      setPreparations((prev) => prev.filter((d) => d.benefitId !== id))
      announce('준비 목록에서 삭제했어요.')
    },
  }
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}
export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('WorkspaceProvider is required')
  return ctx
}
