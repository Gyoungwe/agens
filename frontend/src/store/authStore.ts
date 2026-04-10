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
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: null,
      isAuthenticated: false,

      login: async (username: string, password: string) => {
        const response = await authApi.login({ username, password })
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
          set({ isAuthenticated: false })
          return
        }
        try {
          await authApi.getCurrentUser()
          set({ isAuthenticated: true })
        } catch {
          localStorage.removeItem('token')
          set({ isAuthenticated: false })
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token, username: state.username }),
    }
  )
)
