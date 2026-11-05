import { Text, View } from 'virtual:taro/components'
import Taro from 'virtual:taro/api'
import { useDidShow } from 'virtual:taro/api'
import { ProfileGate } from '../../components/profile-gate.tsx'
import { openOnboarding, requireCompleteProfile } from '../../services/onboarding.ts'
import { useAuthStore } from '../../stores/auth.ts'

export default function IndexPage() {
  const profile = useAuthStore((state) => state.profile)
  const ready = useAuthStore((state) => state.ready)

  useDidShow(() => {
    void (async () => {
      if (!useAuthStore.getState().ready) {
        await useAuthStore.getState().bootstrap()
      }
      openOnboarding()
    })()
  })

  const city = profile?.city || '武汉'

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">网球约球</Text>
      <Text className="mt-2 block text-sm text-slate-500">当前城市 {city}</Text>
      <ProfileGate action="查看推荐" />
      {ready && profile?.profileCompleted ? (
        <Text className="mt-4 block text-sm leading-6 text-slate-600">
          资料已完善。推荐列表会在后续版本接上，届时会按你的 NTRP 和城市筛选。
        </Text>
      ) : null}
      <View
        className="mt-6 rounded-2xl bg-emerald-700 px-4 py-3"
        onClick={() => {
          if (!requireCompleteProfile()) return
          void Taro.showToast({ title: '推荐即将开放', icon: 'none' })
        }}
      >
        <Text className="text-sm font-semibold text-white">查看推荐</Text>
      </View>
    </View>
  )
}
