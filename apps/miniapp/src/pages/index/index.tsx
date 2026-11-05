import { Text, View } from 'virtual:taro/components'
import Taro, { useDidShow } from 'virtual:taro/api'
import { useState } from 'react'
import { ProfileGate } from '../../components/profile-gate.tsx'
import { presentError } from '../../services/feedback.ts'
import { openOnboarding } from '../../services/onboarding.ts'
import { TIME_SLOTS, upcomingDates } from '../../services/schedule.ts'
import { useAuthStore } from '../../stores/auth.ts'
import { useCourtStore } from '../../stores/court.ts'
import { useRecommendStore, type RecommendFilters } from '../../stores/recommend.ts'

const NTRP = Array.from({ length: 13 }, (_, index) => (1 + index * 0.5).toFixed(1))
const GENDER = [
  { id: '', label: '不限' },
  { id: 'male', label: '男' },
  { id: 'female', label: '女' },
] as const

export default function IndexPage() {
  const profile = useAuthStore((state) => state.profile)
  const ready = useAuthStore((state) => state.ready)
  const list = useRecommendStore((state) => state.list)
  const loading = useRecommendStore((state) => state.loading)
  const hasMore = useRecommendStore((state) => state.hasMore)
  const courts = useCourtStore((state) => state.byCity['武汉']?.list ?? [])
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<RecommendFilters>({})
  const city = profile?.city || '武汉'
  const dates = ['', ...upcomingDates()]

  async function reload(filters = useRecommendStore.getState().filters): Promise<void> {
    if (!useAuthStore.getState().profile?.profileCompleted) return
    useRecommendStore.getState().setFilters(filters)
    try {
      await useRecommendStore.getState().refresh(city)
    } catch (error) {
      await presentError(error)
    }
  }

  useDidShow(() => {
    void (async () => {
      if (!useAuthStore.getState().ready) await useAuthStore.getState().bootstrap()
      openOnboarding()
      void useCourtStore.getState().load('武汉')
      await reload(useRecommendStore.getState().filters)
    })()
  })

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">网球约球</Text>
      <View className="mt-3 flex flex-row items-center justify-between">
        <Text className="text-sm text-slate-500">当前城市 {city}</Text>
        <Text className="text-sm text-emerald-800" onClick={() => setOpen((value) => !value)}>
          {open ? '收起筛选' : '筛选'}
        </Text>
      </View>
      <ProfileGate action="查看推荐" />
      {open && ready && profile?.profileCompleted ? (
        <View className="mt-4 rounded-2xl bg-white px-4 py-4">
          <Text className="block text-xs text-slate-500">等级 {draft.ntrpMin ?? '不限'} - {draft.ntrpMax ?? '不限'}</Text>
          <View className="mt-2 flex flex-row flex-wrap gap-2">
            {NTRP.map((value) => (
              <Text
                key={value}
                className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700"
                onClick={() =>
                  setDraft((current) => {
                    const next = Number(value)
                    if (current.ntrpMin == null || current.ntrpMax == null) {
                      return { ...current, ntrpMin: next, ntrpMax: next }
                    }
                    return {
                      ...current,
                      ntrpMin: Math.min(current.ntrpMin, next),
                      ntrpMax: Math.max(current.ntrpMax, next),
                    }
                  })
                }
              >
                {value}
              </Text>
            ))}
          </View>
          <View className="mt-3 flex flex-row flex-wrap gap-2">
            {GENDER.map((item) => (
              <Text
                key={item.label}
                className="rounded-full bg-slate-100 px-3 py-1 text-xs"
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    gender: item.id === '' ? undefined : item.id,
                  }))
                }
              >
                {item.label}
              </Text>
            ))}
          </View>
          <View className="mt-3 flex flex-row flex-wrap gap-2">
            {dates.slice(0, 8).map((value) => (
              <Text
                key={value || 'any-date'}
                className="text-xs text-slate-700"
                onClick={() => setDraft((current) => ({ ...current, date: value || undefined }))}
              >
                {value || '日期不限'}
              </Text>
            ))}
          </View>
          <View className="mt-3 flex flex-row flex-wrap gap-2">
            {['', ...TIME_SLOTS].map((value) => (
              <Text
                key={value || 'any-slot'}
                className="text-xs text-slate-700"
                onClick={() => setDraft((current) => ({ ...current, timeSlot: value || undefined }))}
              >
                {value || '时段不限'}
              </Text>
            ))}
          </View>
          <View className="mt-3 flex flex-row flex-wrap gap-2">
            <Text
              className="text-xs text-slate-700"
              onClick={() => setDraft((current) => ({ ...current, courtId: undefined }))}
            >
              球场不限
            </Text>
            {courts.map((court) => (
              <Text
                key={court.id}
                className="text-xs text-slate-700"
                onClick={() => setDraft((current) => ({ ...current, courtId: court.id }))}
              >
                {court.name}
              </Text>
            ))}
          </View>
          <View className="mt-4 flex flex-row gap-3">
            <Text
              className="text-sm text-slate-500"
              onClick={() => {
                setDraft({})
                void reload({})
              }}
            >
              重置
            </Text>
            <Text
              className="text-sm text-emerald-800"
              onClick={() => {
                setOpen(false)
                void reload(draft)
              }}
            >
              确定
            </Text>
          </View>
        </View>
      ) : null}
      {profile?.profileCompleted ? (
        <View className="mt-4">
          {list.length === 0 && !loading ? (
            <Text className="block text-sm leading-6 text-slate-500">
              暂无符合条件的约球，试试调整筛选条件
            </Text>
          ) : null}
          {list.map((item) => (
            <View
              key={item.id}
              className="mb-3 rounded-2xl bg-white px-4 py-3"
              onClick={() => {
                void Taro.navigateTo({ url: `/subpackages/match/detail/index?id=${item.id}` })
              }}
            >
              <Text className="block text-base font-semibold text-slate-900">
                {item.publisher.nickname || '球友'} · NTRP {item.publisher.ntrp ?? '--'}
              </Text>
              <Text className="mt-1 block text-xs text-slate-500">
                {item.publisher.gender === 'female' ? '女' : '男'} · 信用分 {item.publisher.creditScore}
              </Text>
              <Text className="mt-2 block text-sm text-slate-700">
                {item.court.name} · {item.date} {item.timeSlot}
              </Text>
              <Text className="mt-1 block text-xs text-slate-500">
                {item.matchType === 'doubles' ? '双打' : '单打'} · 人数 {item.filledCount + 1}/
                {item.slotsNeeded + 1}
              </Text>
            </View>
          ))}
          {hasMore ? (
            <Text
              className="mt-2 block text-center text-sm text-emerald-800"
              onClick={() => {
                void useRecommendStore.getState().loadMore(city).catch((error: unknown) => presentError(error))
              }}
            >
              {loading ? '加载中…' : '加载更多'}
            </Text>
          ) : null}
        </View>
      ) : null}
    </View>
  )
}
