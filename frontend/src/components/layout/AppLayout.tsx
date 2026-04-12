import { Outlet } from 'react-router-dom'
import { useState } from 'react'
import { Menu, X } from 'lucide-react'
import { Sidebar } from './Sidebar'

export function AppLayout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <div className="hidden md:block">
        <Sidebar />
      </div>

      <button
        aria-label="Open navigation"
        onClick={() => setMobileNavOpen(true)}
        className="md:hidden fixed top-3 left-3 z-50 inline-flex items-center justify-center w-9 h-9 rounded-lg border border-border bg-card/90 backdrop-blur"
      >
        <Menu className="w-5 h-5" />
      </button>

      {mobileNavOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileNavOpen(false)} />
          <div className="absolute left-0 top-0 h-full">
            <div className="relative">
              <button
                aria-label="Close navigation"
                onClick={() => setMobileNavOpen(false)}
                className="absolute top-3 right-3 z-10 inline-flex items-center justify-center w-8 h-8 rounded-lg border border-border bg-card"
              >
                <X className="w-4 h-4" />
              </button>
              <Sidebar />
            </div>
          </div>
        </div>
      )}

      <main className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
