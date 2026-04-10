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
  LoginPage,
} from '@/pages'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()

  useEffect(() => {
    if (!isAuthenticated) {
      const token = localStorage.getItem('token')
      if (!token) {
        window.location.href = '/login'
      }
    }
  }, [isAuthenticated])

  if (!isAuthenticated) {
    const token = localStorage.getItem('token')
    if (!token) {
      return <Navigate to="/login" replace />
    }
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
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
