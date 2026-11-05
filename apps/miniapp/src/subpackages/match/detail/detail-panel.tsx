import { Text, View } from 'virtual:taro/components'
import Taro, { useDidShow } from 'virtual:taro/api'
import { useState } from 'react'
import { presentError } from '../../../services/feedback.ts'
import { request } from '../../../services/request.ts'
import type { MatchSummary } from '../../../stores/recommend.ts'

interface Participant {
  user: MatchSummary['publisher']
  role: 'publisher' | 'partner'
  arrived: boolean
  rated: boolean
}

interface MatchDetail extends MatchSummary {
  participants: Participant[]
  pendingApplicationCount: number | null
  publisher: MatchSummary['publisher'] & {
    age: number | null
    city: string | null
    style: string[]
    bio: string | null
  }
}

const ACTION_LABEL: Record<string, string> = {
  apply: '申请加入',
  withdraw: '撤回申请',
  viewApplications: '查看申请',
}

export default function DetailPanel({ requestId }: { requestId: string }) {
  const [detail, setDetail] = useState<MatchDetail | null>(null)
  const [busy, setBusy] = useState(false)

  async function load(): Promise<void> {
    const data = await request<MatchDetail>({ url: `/match/detail/${requestId}` })
    setDetail(data)
  }

  useDidShow(() => {
    void load().catch((error: unknown) => presentError(error))
  })

  async function run(action: string): Promise<void> {
    if (!detail || busy) return
    setBusy(true)
    try {
      if (action === 'apply') {
        await request({ url: '/match/apply', method: 'POST', data: { requestId: detail.id } })
        await load()
      } else if (action === 'withdraw' && detail.myApplicationId) {
        await request({
          url: '/match/application/withdraw',
          method: 'POST',
          data: { applicationId: detail.myApplicationId },
        })
        await load()
      } else if (action === 'viewApplications') {
        await Taro.navigateTo({
          url: `/subpackages/match/applications/index?requestId=${detail.id}`,
        })
      }
    } catch (error) {
      await presentError(error)
    } finally {
      setBusy(false)
    }
  }

  if (!detail) {
    return <Text className="mt-4 block text-sm text-slate-500">加载中…</Text>
  }

  const buttons = detail.availableActions.filter((action) => action in ACTION_LABEL)

  return (
    <View className="mt-4">
      <View className="rounded-2xl bg-white px-4 py-4">
        <Text className="block text-lg font-semibold text-slate-900">
          {detail.publisher.nickname || '球友'} · NTRP {detail.publisher.ntrp ?? '--'}
        </Text>
        <Text className="mt-1 block text-xs text-slate-500">
          信用分 {detail.publisher.creditScore}
          {detail.publisher.bio ? ` · ${detail.publisher.bio}` : ''}
        </Text>
        <Text className="mt-3 block text-sm text-slate-800">
          {detail.court.name} {detail.court.address}
        </Text>
        <Text className="mt-1 block text-sm text-slate-700">
          {detail.date} {detail.timeSlot} · {detail.matchType === 'doubles' ? '双打' : '单打'}
        </Text>
        <Text className="mt-1 block text-sm text-slate-700">
          人数 {detail.filledCount + 1}/{detail.slotsNeeded + 1} ·{' '}
          {detail.status === 'matched' ? '已匹配' : detail.status === 'pending' ? '待匹配' : detail.status}
        </Text>
        {detail.pendingApplicationCount != null ? (
          <Text className="mt-1 block text-xs text-slate-500">
            待处理申请 {detail.pendingApplicationCount}
          </Text>
        ) : null}
      </View>
      <View className="mt-4 rounded-2xl bg-white px-4 py-4">
        <Text className="block text-sm font-semibold text-slate-800">参与者</Text>
        {detail.participants.map((person) => (
          <Text key={person.user.id} className="mt-2 block text-sm text-slate-700">
            {person.role === 'publisher' ? '发布者' : '搭档'} · {person.user.nickname || '球友'} · NTRP{' '}
            {person.user.ntrp ?? '--'}
          </Text>
        ))}
      </View>
      {buttons.map((action) => (
        <View
          key={action}
          className="mt-4 rounded-2xl bg-emerald-700 px-4 py-3"
          onClick={() => void run(action)}
        >
          <Text className="text-sm font-semibold text-white">
            {busy ? '处理中…' : ACTION_LABEL[action]}
          </Text>
        </View>
      ))}
    </View>
  )
}
