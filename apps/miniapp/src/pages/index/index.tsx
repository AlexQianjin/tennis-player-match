import { Text, View } from 'virtual:taro/components'
import Taro from 'virtual:taro/api'
import { ERROR_CODES } from '@tennis/shared'

export default function IndexPage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">网球约球</Text>
      <Text className="mt-3 block text-sm leading-6 text-slate-600">
        首页推荐列表会接在这里。当前是骨架页，错误码 {ERROR_CODES.SUCCESS} 表示成功。
      </Text>
      <View
        className="mt-6 rounded-2xl bg-emerald-700 px-4 py-3"
        onClick={() => {
          void Taro.navigateTo({ url: '/subpackages/match/detail/index' })
        }}
      >
        <Text className="text-sm font-semibold text-white">查看约球详情占位</Text>
      </View>
    </View>
  )
}
