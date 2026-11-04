import { Text, View } from 'virtual:taro/components'

export default function RatePage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">评分</Text>
      <Text className="mt-3 block text-sm text-slate-600">双打逐人打分的占位页。</Text>
    </View>
  )
}
