import { Text, View } from 'virtual:taro/components'
import { useDidShow } from 'virtual:taro/api'
import { useRef, useState } from 'react'
import type { Page } from '@tennis/shared'
import { MatchCard } from '../../components/match-card.tsx'
import { ProfileGate } from '../../components/profile-gate.tsx'
import { messageFor } from '../../services/errors.ts'
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
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [failed, setFailed] = useState('')
  const requestSeq = useRef(0)

  async function load(next = tab, nextPage = 1): Promise<void> {
    if (!useAuthStore.getState().profile?.profileCompleted) return
    const seq = nextPage === 1 ? ++requestSeq.current : requestSeq.current
    const data = await request<Page<MyItem>>({
      url: `/match/my?tab=${next}&page=${nextPage}&pageSize=10`,
    })
    if (seq !== requestSeq.current) return
    setItems((current) => (nextPage === 1 ? data.list : [...current, ...data.list]))
    setPage(data.page)
    setHasMore(data.hasMore)
    setFailed('')
  }

  useDidShow(() => {
    void (async () => {
      if (!useAuthStore.getState().ready) await useAuthStore.getState().bootstrap()
      await flushPendingRatings()
      await load().catch(async (error: unknown) => {
        setFailed(messageFor(error))
        await presentError(error)
      })
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
              setItems([])
              setHasMore(false)
              void load(item.id, 1).catch(async (error: unknown) => {
                setFailed(messageFor(error))
                await presentError(error)
              })
            }}
          >
            <Text className={item.id === tab ? 'text-xs text-white' : 'text-xs text-slate-600'}>{item.label}</Text>
          </View>
        ))}
      </View>
      {failed ? <Text className="mt-4 block text-sm text-rose-700">{failed}</Text> : null}
      {ready && !failed && items.length === 0 ? (
        <Text className="mt-4 block text-sm text-slate-500">这个分类还没有约球</Text>
      ) : null}
      <View className="mt-4">
        {items.map((item) => (
          <MatchCard key={item.id} item={item} onChanged={() => void load(tab, 1)} />
        ))}
      </View>
      {hasMore ? (
        <Text
          className="mt-2 block text-center text-sm text-emerald-800"
          onClick={() => {
            void load(tab, page + 1).catch(async (error: unknown) => {
              setFailed(messageFor(error))
              await presentError(error)
            })
          }}
        >
          加载更多
        </Text>
      ) : null}
    </View>
  )
}
