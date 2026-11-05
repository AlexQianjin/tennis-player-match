import { Image, Text, View } from 'virtual:taro/components'
import Taro from 'virtual:taro/api'
import { useDidShow } from 'virtual:taro/api'
import { useAuthStore } from '../../stores/auth.ts'

const FIELD_LABELS: Record<string, string> = {
  nickname: '昵称',
  avatar: '头像',
  ntrp: 'NTRP',
  gender: '性别',
  age: '年龄',
  city: '城市',
}

const GENDER_LABELS = { male: '男', female: '女' } as const

const LISTS = [
  { type: 'published', label: '我发布的' },
  { type: 'applied', label: '我申请的' },
  { type: 'matched', label: '已匹配成功的' },
] as const

export default function MePage() {
  const profile = useAuthStore((state) => state.profile)
  const ready = useAuthStore((state) => state.ready)
  const error = useAuthStore((state) => state.error)

  useDidShow(() => {
    void (async () => {
      const state = useAuthStore.getState()
      if (!state.ready) await state.bootstrap()
      try {
        await useAuthStore.getState().refreshProfile()
      } catch {
        // Keep the last snapshot when the profile read fails.
      }
    })()
  })

  const missing = (profile?.missingFields ?? [])
    .map((field) => FIELD_LABELS[field] ?? field)
    .join('、')
  const rating =
    profile?.avgRating == null ? '暂无评分' : `${profile.avgRating.toFixed(1)}（${profile.ratingCount}次）`
  const mode = profile?.profileCompleted ? 'edit' : 'onboarding'

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">个人中心</Text>
      <View
        className="mt-4 flex flex-row items-center rounded-2xl bg-white px-4 py-4"
        onClick={() => {
          void Taro.navigateTo({ url: `/subpackages/user/profile-edit/index?mode=${mode}` })
        }}
      >
        {profile?.avatar && !profile.avatar.startsWith('cloud://dev.local/') ? (
          <Image className="h-16 w-16 rounded-full bg-slate-200" src={profile.avatar} mode="aspectFill" />
        ) : (
          <View className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
            <Text className="text-lg text-emerald-800">{profile?.nickname?.slice(0, 1) || '球'}</Text>
          </View>
        )}
        <View className="ml-4 flex-1">
          <Text className="block text-lg font-semibold text-slate-900">
            {profile?.nickname || (ready ? '未完善资料' : '正在读取资料…')}
          </Text>
          <Text className="mt-1 block text-sm text-slate-600">
            NTRP {profile?.ntrp ?? '--'} · 信用分 {profile?.creditScore ?? 0}
          </Text>
          <Text className="mt-1 block text-xs text-slate-500">
            {profile?.gender ? GENDER_LABELS[profile.gender] : '性别未填'} · {rating}
          </Text>
        </View>
      </View>
      {error && !profile ? <Text className="mt-3 block text-sm text-rose-700">{error}</Text> : null}
      {profile && !profile.profileCompleted ? (
        <Text className="mt-3 block text-sm leading-6 text-amber-800">
          还缺：{missing || '必填资料'}。完善后才能发布、推荐和申请。
        </Text>
      ) : null}
      {profile?.bio ? <Text className="mt-3 block text-sm leading-6 text-slate-600">{profile.bio}</Text> : null}
      {profile?.style?.length ? (
        <Text className="mt-2 block text-xs text-slate-500">风格 {profile.style.join(' / ')}</Text>
      ) : null}
      <View className="mt-6 overflow-hidden rounded-2xl bg-white">
        {LISTS.map((item) => (
          <View
            key={item.type}
            className="border-b border-slate-100 px-4 py-3"
            onClick={() => {
              void Taro.navigateTo({ url: `/subpackages/user/my-list/index?type=${item.type}` })
            }}
          >
            <Text className="text-sm text-slate-800">{item.label}</Text>
          </View>
        ))}
        <View
          className="px-4 py-3"
          onClick={() => {
            void Taro.navigateTo({ url: `/subpackages/user/profile-edit/index?mode=${mode}` })
          }}
        >
          <Text className="text-sm text-emerald-800">{profile?.profileCompleted ? '编辑资料' : '完善资料'}</Text>
        </View>
      </View>
      <View
        className="mt-4 rounded-2xl bg-white px-4 py-3"
        onClick={() => {
          void Taro.navigateTo({ url: '/subpackages/user/settings/index' })
        }}
      >
        <Text className="text-sm text-emerald-800">设置</Text>
      </View>
    </View>
  )
}
