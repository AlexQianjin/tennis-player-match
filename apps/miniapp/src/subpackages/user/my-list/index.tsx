import { Text, View } from 'virtual:taro/components'
import { useDidShow, useLoad } from 'virtual:taro/api'
import { useState } from 'react'
import { MatchCard } from '../../../components/match-card.tsx'
import { ProfileGate } from '../../../components/profile-gate.tsx'
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

  async function load(next: string): Promise<void> {
    const data = await request<{ list: MatchSummary[] }>({ url: `/match/my?type=${next}` })
    setItems(data.list)
  }

  useLoad((query) => {
    const next = typeof query.type === 'string' && query.type in TITLES ? query.type : 'published'
    setType(next)
    void load(next).catch((error: unknown) => presentError(error))
  })

  useDidShow(() => {
    if (!type) return
    void load(type).catch((error: unknown) => presentError(error))
  })

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">{TITLES[type] ?? '我的列表'}</Text>
      <ProfileGate action="查看约球记录" />
      {items.length === 0 ? <Text className="mt-4 block text-sm text-slate-500">还没有记录</Text> : null}
      <View className="mt-4">
        {items.map((item) => (
          <MatchCard key={item.id} item={item} onChanged={() => void load(type)} />
        ))}
      </View>
    </View>
  )
}
