import { Text, View } from 'virtual:taro/components'
import { ProfileGate } from '../../components/profile-gate.tsx'

const tabs = ['待确认', '已确认', '已完成', '已取消'] as const

export default function MyMatchesPage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">我的约球</Text>
      <ProfileGate action="查看申请和约球" />
      <View className="mt-4 flex flex-row flex-wrap gap-2">
        {tabs.map((tab) => (
          <View key={tab} className="rounded-full bg-white px-3 py-1">
            <Text className="text-xs text-slate-600">{tab}</Text>
          </View>
        ))}
      </View>
      <Text className="mt-4 block text-sm leading-6 text-slate-600">约球状态会在后续版本接上。</Text>
    </View>
  )
}
