import { Text, View } from 'virtual:taro/components'

export default function MyListPage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">我的列表</Text>
      <Text className="mt-3 block text-sm text-slate-600">我发布的、我申请的、已匹配成功的共用此页。</Text>
    </View>
  )
}
