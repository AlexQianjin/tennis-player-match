import Taro from 'virtual:taro/api'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { messageFor } from '../services/errors.ts'
import { request } from '../services/request.ts'

export interface Profile {
  id: string
  nickname: string | null
  avatar: string | null
  ntrp: number | null
  gender: 'male' | 'female' | null
  age: number | null
  city: string | null
  style: string[]
  bio: string | null
  creditScore: number
  confirmCount: number
  cancelCount: number
  avgRating: number | null
  ratingCount: number
  profileCompleted: boolean
  missingFields: string[]
  ntrpUpdateTime: string | null
  ntrpNextEditableAt: string | null
  activeRequestId: string | null
}

export interface ProfileInput {
  nickname?: string
  avatar?: string
  ntrp?: number
  gender?: 'male' | 'female'
  age?: number
  city?: string
  style?: string[]
  bio?: string
}

interface LoginData {
  isNewUser: boolean
  userInfo: Profile
}

interface AuthState {
  profile: Profile | null
  isNewUser: boolean | null
  ready: boolean
  error: string | null
  onboardingPrompted: boolean
  bootstrap: () => Promise<void>
  refreshProfile: () => Promise<void>
  updateProfile: (input: ProfileInput) => Promise<Profile>
  clearLocal: () => void
}

const taroStorage = {
  getItem(name: string): string | null {
    try {
      const value = Taro.getStorageSync(name) as unknown
      if (typeof value === 'string') return value
      if (value == null || value === '') return null
      return JSON.stringify(value)
    } catch {
      return null
    }
  },
  setItem(name: string, value: string): void {
    try {
      Taro.setStorageSync(name, value)
    } catch {
      // Storage is unavailable outside the mini program runtime.
    }
  },
  removeItem(name: string): void {
    try {
      Taro.removeStorageSync(name)
    } catch {
      // Storage is unavailable outside the mini program runtime.
    }
  },
}

let pendingBootstrap: Promise<void> | null = null

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      profile: null,
      isNewUser: null,
      ready: false,
      error: null,
      onboardingPrompted: false,
      bootstrap() {
        if (!pendingBootstrap) {
          pendingBootstrap = (async () => {
            try {
              const data = await request<LoginData>({ url: '/auth/login', method: 'POST' })
              set({
                profile: data.userInfo,
                isNewUser: data.isNewUser,
                ready: true,
                error: null,
              })
            } catch (error) {
              set({ ready: true, error: messageFor(error) })
            }
          })().finally(() => {
            pendingBootstrap = null
          })
        }
        return pendingBootstrap
      },
      async refreshProfile() {
        const data = await request<Profile>({ url: '/user/profile' })
        set({ profile: data, isNewUser: !data.profileCompleted, ready: true, error: null })
      },
      async updateProfile(input) {
        const data = await request<Profile>({
          url: '/user/profile',
          method: 'POST',
          data: input,
        })
        set({ profile: data, isNewUser: !data.profileCompleted, ready: true, error: null })
        return data
      },
      clearLocal() {
        set({
          profile: null,
          isNewUser: null,
          ready: false,
          error: null,
          onboardingPrompted: false,
        })
      },
    }),
    {
      name: 'tennis-auth',
      storage: createJSONStorage(() => taroStorage),
      partialize: (state) => ({ profile: state.profile, isNewUser: state.isNewUser }),
    },
  ),
)
