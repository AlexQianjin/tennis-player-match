import { Text, View } from 'virtual:taro/components'

const tabs = ['待确认', '已确认', '已完成', '已取消'] as const

export default function MyMatchesPage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">我的约球</Text>
      <View className="mt-4 flex flex-row flex-wrap gap-2">
        {tabs.map((tab) => (
          <View key={tab} className="rounded-full bg-white px-3 py-1">
            <Text className="text-xs text-slate-600">{tab}</Text>
          </View>
        ))}
      </View>
    </View>
  )
}
