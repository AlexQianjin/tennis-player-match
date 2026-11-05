import { Text, View } from 'virtual:taro/components'
import Taro from 'virtual:taro/api'
import { useAuthStore } from '../stores/auth.ts'
import { ONBOARDING_URL } from '../services/onboarding.ts'

export function ProfileGate({ action }: { action: string }) {
  const ready = useAuthStore((state) => state.ready)
  const completed = useAuthStore((state) => state.profile?.profileCompleted === true)
  if (!ready || completed) return null
  return (
    <View
      className="mt-4 rounded-2xl bg-amber-50 px-4 py-3"
      onClick={() => {
        void Taro.navigateTo({ url: ONBOARDING_URL })
      }}
    >
      <Text className="block text-sm leading-6 text-amber-900">
        资料未完善，请先完善资料后再{action}
      </Text>
    </View>
  )
}
