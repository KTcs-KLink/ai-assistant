import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AdminLayout } from './admin/AdminLayout'
import { DocumentsPage } from './admin/DocumentsPage'
import { FeedbackPage } from './admin/FeedbackPage'
import { OverviewPage } from './admin/OverviewPage'
import { SettingsPage } from './admin/SettingsPage'
import { UsersPage } from './admin/UsersPage'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { ChatLayout } from './chat/ChatLayout'
import { ConversationPage } from './chat/ConversationPage'
import { NewChatPage } from './chat/NewChatPage'
import { OriginalDataDemoPage } from './chat/OriginalDataDemoPage'
import { LoginPage } from './LoginPage'
import { BenefitsPage } from './benefits/BenefitsPage'
const WorkspaceApp = lazy(() =>
  import('./portal/PortalApp').then((m) => ({ default: m.PortalApp })),
)

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
        <Route
          path="/workspace/*"
          element={
            <Suspense
              fallback={
                <div className="p-8 text-sm text-muted">K:LINK 화면을 준비하고 있어요…</div>
              }
            >
              <WorkspaceApp />
            </Suspense>
          }
        />
        <Route
          path="*"
          element={
            <AuthProvider>
              <LegacyRoutes />
            </AuthProvider>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

function LegacyRoutes() {
  return (
    <Routes>
      <Route path="/benefits" element={<BenefitsPage />} />
      <Route path="/login" element={<LoginPage />} />
      {/* 기존 로컬 실데이터 앱은 별도 인증 서버를 요구하지 않습니다. */}
      <Route
        path="/original-data-demo"
        element={
          <div className="flex h-screen bg-canvas">
            <OriginalDataDemoPage />
          </div>
        }
      />
      <Route
        element={
          <RequireAuth>
            <ChatLayout />
          </RequireAuth>
        }
      >
        <Route index element={<NewChatPage />} />
        <Route path="c/:id" element={<ConversationPage />} />
      </Route>
      <Route
        path="admin"
        element={
          <RequireAuth admin>
            <AdminLayout />
          </RequireAuth>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="feedback" element={<FeedbackPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
