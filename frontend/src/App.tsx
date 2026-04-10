import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { useAuthStore } from '@/store'
import {
  AppLayout,
  ChatPage,
  DashboardPage,
  SkillsPage,
  KnowledgePage,
  ApprovalsPage,
  SessionsPage,
  AgentChatPage,
  AgentSettingsPage,
  ProvidersPage,
  LoginPage,
} from '@/pages'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, _hasHydrated } = useAuthStore()

  useEffect(() => {
    if (!_hasHydrated) return
    if (!isAuthenticated) {
      window.location.href = '/login'
    }
  }, [isAuthenticated, _hasHydrated])

  if (!_hasHydrated) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<ChatPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="approvals" element={<ApprovalsPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="agent-chat" element={<AgentChatPage />} />
        <Route path="agent-settings" element={<AgentSettingsPage />} />
        <Route path="providers" element={<ProvidersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
