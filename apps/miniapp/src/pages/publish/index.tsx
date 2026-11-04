import { Text, View } from 'virtual:taro/components'

export default function PublishPage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">发布约球</Text>
      <Text className="mt-3 block text-sm leading-6 text-slate-600">
        日期、时段、球场和单打/双打表单会接在这里。
      </Text>
    </View>
  )
}
