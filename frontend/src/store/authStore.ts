import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '@/api'

interface AuthState {
  token: string | null
  username: string | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
  _hasHydrated: boolean
  setHasHydrated: (v: boolean) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      username: null,
      isAuthenticated: false,
      _hasHydrated: false,

      login: async (username: string, password: string) => {
        const response = await authApi.login({ username, password })
        localStorage.setItem('token', response.data.access_token)
        set({
          token: response.data.access_token,
          username,
          isAuthenticated: true,
        })
      },

      logout: () => {
        localStorage.removeItem('token')
        set({ token: null, username: null, isAuthenticated: false })
        window.location.href = '/login'
      },

      checkAuth: async () => {
        const token = localStorage.getItem('token')
        if (!token) {
          set({ token: null, isAuthenticated: false })
          return
        }
        try {
          await authApi.getCurrentUser()
          set({ token, isAuthenticated: true })
        } catch {
          localStorage.removeItem('token')
          set({ token: null, isAuthenticated: false })
        }
      },

      setHasHydrated: (v: boolean) => {
        set({ _hasHydrated: v })
        if (v) {
          const token = get().token
          if (token) {
            localStorage.setItem('token', token)
          } else {
            localStorage.removeItem('token')
          }
          set({ isAuthenticated: !!token })
        }
      },
    }),
    {
      name: 'auth-storage',
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true)
      },
      partialize: (state) => ({
        token: state.token,
        username: state.username,
        isAuthenticated: !!state.token,
      }),
    }
  )
)
