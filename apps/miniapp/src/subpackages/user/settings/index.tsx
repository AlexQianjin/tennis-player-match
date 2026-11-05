import { Text, View } from 'virtual:taro/components'

export default function SettingsPage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">设置</Text>
      <Text className="mt-3 block text-sm leading-6 text-slate-600">
        本地 http 通道使用存储键 devOpenid（默认 dev_user_1）作为 X-Dev-Openid。
      </Text>
    </View>
  )
}
