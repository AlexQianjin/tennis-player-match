import { Text, View } from 'virtual:taro/components'

export default function DetailPanel() {
  return (
    <View className="mt-4 rounded-2xl bg-white p-4">
      <Text className="block text-base font-semibold text-slate-800">约球信息</Text>
      <Text className="mt-2 block text-sm leading-6 text-slate-600">
        发布者、球场、时段和申请按钮会接在这个按需加载的面板里。
      </Text>
    </View>
  )
}
