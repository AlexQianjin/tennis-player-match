import { Text, View } from 'virtual:taro/components'
import { useDidShow } from 'virtual:taro/api'
import { useState } from 'react'
import { MatchCard } from '../../components/match-card.tsx'
import { ProfileGate } from '../../components/profile-gate.tsx'
import { presentError } from '../../services/feedback.ts'
import { flushPendingRatings } from '../../services/offline-queue.ts'
import { request } from '../../services/request.ts'
import { useAuthStore } from '../../stores/auth.ts'
import type { MatchSummary } from '../../stores/recommend.ts'

const TABS = [
  { id: 'pending', label: '待确认' },
  { id: 'confirmed', label: '已确认' },
  { id: 'completed', label: '已完成' },
  { id: 'cancelled', label: '已取消' },
] as const

interface MyItem extends MatchSummary {
  tab: string
  pendingApplicationCount: number | null
}

export default function MyMatchesPage() {
  const ready = useAuthStore((state) => state.profile?.profileCompleted === true)
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('pending')
  const [items, setItems] = useState<MyItem[]>([])

  async function load(next = tab): Promise<void> {
    if (!useAuthStore.getState().profile?.profileCompleted) return
    const data = await request<{ list: MyItem[] }>({ url: `/match/my?tab=${next}` })
    setItems(data.list)
  }

  useDidShow(() => {
    void (async () => {
      if (!useAuthStore.getState().ready) await useAuthStore.getState().bootstrap()
      await flushPendingRatings()
      await load().catch((error: unknown) => presentError(error))
    })()
  })

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">我的约球</Text>
      <ProfileGate action="查看约球" />
      <View className="mt-4 flex flex-row flex-wrap gap-2">
        {TABS.map((item) => (
          <View
            key={item.id}
            className={item.id === tab ? 'rounded-full bg-emerald-800 px-3 py-1' : 'rounded-full bg-white px-3 py-1'}
            onClick={() => {
              setTab(item.id)
              void load(item.id).catch((error: unknown) => presentError(error))
            }}
          >
            <Text className={item.id === tab ? 'text-xs text-white' : 'text-xs text-slate-600'}>{item.label}</Text>
          </View>
        ))}
      </View>
      {ready && items.length === 0 ? (
        <Text className="mt-4 block text-sm text-slate-500">这个分类还没有约球</Text>
      ) : null}
      <View className="mt-4">
        {items.map((item) => (
          <MatchCard key={item.id} item={item} onChanged={() => void load()} />
        ))}
      </View>
    </View>
  )
}
