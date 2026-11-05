import { Text, View } from 'virtual:taro/components'

export default function ApplicationsPage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">申请列表</Text>
      <Text className="mt-3 block text-sm text-slate-600">发布方同意或拒绝申请的占位页。</Text>
    </View>
  )
}
