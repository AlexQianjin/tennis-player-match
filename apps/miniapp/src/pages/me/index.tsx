import { Text, View } from 'virtual:taro/components'
import Taro from 'virtual:taro/api'
import { useEffect } from 'react'
import { useAuthStore } from '../../stores/auth.ts'

export default function MePage() {
  const profile = useAuthStore((state) => state.profile)
  const ready = useAuthStore((state) => state.ready)
  const bootstrap = useAuthStore((state) => state.bootstrap)

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  const title = profile?.nickname ?? (ready ? '未登录（本地接口未连通）' : '正在读取资料…')

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">个人中心</Text>
      <Text className="mt-3 block text-sm text-slate-600">{title}</Text>
      <View
        className="mt-6 rounded-2xl bg-white px-4 py-3"
        onClick={() => {
          void Taro.navigateTo({ url: '/subpackages/user/settings/index' })
        }}
      >
        <Text className="text-sm text-emerald-800">设置</Text>
      </View>
    </View>
  )
}
