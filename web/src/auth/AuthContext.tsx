import { createContext, useContext, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { User } from '../api/types'

interface AuthValue {
  user: User | null
  isLoading: boolean
  /** 아이디/비밀번호 로그인. 실패하면 ApiError 를 던진다 */
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['me'], queryFn: api.me, staleTime: Infinity, retry: false })
  const value: AuthValue = {
    user: data ?? null,
    isLoading,
    async login(username, password) {
      const user = await api.login(username, password)
      qc.setQueryData(['me'], user)
    },
    async logout() {
      await api.logout()
      qc.clear()
      window.location.assign('/login')
    },
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
