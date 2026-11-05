import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AdminLayout } from './admin/AdminLayout'
import { DocumentsPage } from './admin/DocumentsPage'
import { FeedbackPage } from './admin/FeedbackPage'
import { OverviewPage } from './admin/OverviewPage'
import { SettingsPage } from './admin/SettingsPage'
import { UsersPage } from './admin/UsersPage'
import { useAuth } from './auth/AuthContext'
import { ChatLayout } from './chat/ChatLayout'
import { ConversationPage } from './chat/ConversationPage'
import { NewChatPage } from './chat/NewChatPage'
import { LoginPage } from './LoginPage'

function RequireAuth({ admin, children }: { admin?: boolean; children: ReactNode }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  // 관리자 메뉴는 관리자 역할에만
  if (admin && user.role !== 'admin') return <Navigate to="/" replace />
  return children
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth><ChatLayout /></RequireAuth>}>
          <Route index element={<NewChatPage />} />
          <Route path="c/:id" element={<ConversationPage />} />
        </Route>
        <Route path="admin" element={<RequireAuth admin><AdminLayout /></RequireAuth>}>
          <Route index element={<OverviewPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="feedback" element={<FeedbackPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
