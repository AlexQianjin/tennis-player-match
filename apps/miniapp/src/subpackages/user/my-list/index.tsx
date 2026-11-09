import { Text, View } from 'virtual:taro/components'
import { useDidShow, useLoad } from 'virtual:taro/api'
import { useRef, useState } from 'react'
import type { Page } from '@tennis/shared'
import { MatchCard } from '../../../components/match-card.tsx'
import { ProfileGate } from '../../../components/profile-gate.tsx'
import { messageFor } from '../../../services/errors.ts'
import { presentError } from '../../../services/feedback.ts'
import { request } from '../../../services/request.ts'
import type { MatchSummary } from '../../../stores/recommend.ts'

const TITLES: Record<string, string> = {
  published: '我发布的',
  applied: '我申请的',
  matched: '已匹配成功的',
}

export default function MyListPage() {
  const [type, setType] = useState('published')
  const [items, setItems] = useState<MatchSummary[]>([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [failed, setFailed] = useState('')
  const requestSeq = useRef(0)

  async function load(next: string, nextPage = 1): Promise<void> {
    const seq = nextPage === 1 ? ++requestSeq.current : requestSeq.current
    const data = await request<Page<MatchSummary>>({
      url: `/match/my?type=${next}&page=${nextPage}&pageSize=10`,
    })
    if (seq !== requestSeq.current) return
    setItems((current) => (nextPage === 1 ? data.list : [...current, ...data.list]))
    setPage(data.page)
    setHasMore(data.hasMore)
    setFailed('')
  }

  useLoad((query) => {
    const next = typeof query.type === 'string' && query.type in TITLES ? query.type : 'published'
    setType(next)
    void load(next).catch(async (error: unknown) => {
      setFailed(messageFor(error))
      await presentError(error)
    })
  })

  useDidShow(() => {
    if (!type) return
    void load(type).catch(async (error: unknown) => {
      setFailed(messageFor(error))
      await presentError(error)
    })
  })

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">{TITLES[type] ?? '我的列表'}</Text>
      <ProfileGate action="查看约球记录" />
      {failed ? <Text className="mt-4 block text-sm text-rose-700">{failed}</Text> : null}
      {!failed && items.length === 0 ? <Text className="mt-4 block text-sm text-slate-500">还没有记录</Text> : null}
      <View className="mt-4">
        {items.map((item) => (
          <MatchCard key={item.id} item={item} onChanged={() => void load(type, 1)} />
        ))}
      </View>
      {hasMore ? (
        <Text
          className="mt-2 block text-center text-sm text-emerald-800"
          onClick={() => {
            void load(type, page + 1).catch(async (error: unknown) => {
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
