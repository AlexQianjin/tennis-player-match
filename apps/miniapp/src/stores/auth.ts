import { create } from 'zustand'
import { request } from '../services/request.ts'

export interface ProfileSnapshot {
  id: string
  nickname: string | null
  city: string | null
  profileCompleted: boolean
  creditScore: number
}

interface LoginData {
  isNewUser: boolean
  userInfo: ProfileSnapshot
}

interface AuthState {
  profile: ProfileSnapshot | null
  isNewUser: boolean | null
  ready: boolean
  bootstrap: () => Promise<void>
  clearLocal: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  profile: null,
  isNewUser: null,
  ready: false,
  async bootstrap() {
    try {
      const data = await request<LoginData>({ url: '/auth/login', method: 'POST' })
      set({ profile: data.userInfo, isNewUser: data.isNewUser, ready: true })
    } catch {
      set({ ready: true })
    }
  },
  clearLocal() {
    set({ profile: null, isNewUser: null, ready: false })
  },
}))
