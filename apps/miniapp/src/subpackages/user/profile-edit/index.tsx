import { Text, View } from 'virtual:taro/components'

export default function ProfileEditPage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">编辑资料</Text>
      <Text className="mt-3 block text-sm text-slate-600">新用户完善资料与资料编辑共用此页。</Text>
    </View>
  )
}
