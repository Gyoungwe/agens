import { Outlet, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { Sidebar } from './Sidebar'

export function AppLayout() {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="flex h-screen bg-background">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
