import Taro from 'virtual:taro/api'
import { useAuthStore } from '../stores/auth.ts'

export const ONBOARDING_URL = '/subpackages/user/profile-edit/index?mode=onboarding'

let navigating = false

export function openOnboarding(): void {
  const state = useAuthStore.getState()
  if (!state.isNewUser || state.onboardingPrompted || navigating) return
  navigating = true
  useAuthStore.setState({ onboardingPrompted: true })
  void Taro.navigateTo({ url: ONBOARDING_URL })
    .catch(() => {
      useAuthStore.setState({ onboardingPrompted: false })
    })
    .finally(() => {
      navigating = false
    })
}

export function requireCompleteProfile(): boolean {
  if (useAuthStore.getState().profile?.profileCompleted) return true
  void Taro.showToast({ title: '请先完善资料', icon: 'none' })
  void Taro.navigateTo({ url: ONBOARDING_URL })
  return false
}
