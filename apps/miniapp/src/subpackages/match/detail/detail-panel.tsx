import { Text, View } from 'virtual:taro/components'
import Taro, { useDidShow } from 'virtual:taro/api'
import { useState } from 'react'
import { messageFor } from '../../../services/errors.ts'
import { presentError } from '../../../services/feedback.ts'
import { genderPrefLabel, matchStatusLabel, styleLabel } from '../../../services/labels.ts'
import { confirmAndCancel, markArrived } from '../../../services/match-actions.ts'
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
  cancel: '取消约球',
  arrive: '已到场',
  rate: '去评分',
}

export default function DetailPanel({ requestId }: { requestId: string }) {
  const [detail, setDetail] = useState<MatchDetail | null>(null)
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState('')

  async function load(): Promise<void> {
    const data = await request<MatchDetail>({ url: `/match/detail/${requestId}` })
    setDetail(data)
    setFailed('')
  }

  useDidShow(() => {
    void load().catch(async (error: unknown) => {
      setFailed(messageFor(error))
      await presentError(error)
    })
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
      } else if (action === 'cancel') {
        if (await confirmAndCancel(detail.id)) await load()
      } else if (action === 'arrive') {
        await markArrived(detail.id)
        await load()
      } else if (action === 'rate') {
        await Taro.navigateTo({ url: `/subpackages/match/rate/index?id=${detail.id}` })
      }
    } catch (error) {
      await presentError(error)
    } finally {
      setBusy(false)
    }
  }

  if (!detail) {
    return <Text className="mt-4 block text-sm text-slate-500">{failed || '加载中…'}</Text>
  }

  const rating =
    detail.publisher.avgRating == null
      ? '暂无评分'
      : `${detail.publisher.avgRating.toFixed(1)}（${detail.publisher.ratingCount}次）`

  const buttons = detail.availableActions.filter((action) => action in ACTION_LABEL)

  return (
    <View className="mt-4">
      <View className="rounded-2xl bg-white px-4 py-4">
        <Text className="block text-lg font-semibold text-slate-900">
          {detail.publisher.nickname || '球友'} · NTRP {detail.publisher.ntrp ?? '--'}
        </Text>
        <Text className="mt-1 block text-xs text-slate-500">
          信用分 {detail.publisher.creditScore} · 平均评分 {rating}
        </Text>
        {detail.publisher.style?.length ? (
          <Text className="mt-1 block text-xs text-slate-500">
            风格 {detail.publisher.style.map((item) => styleLabel(item)).join(' / ')}
          </Text>
        ) : null}
        {detail.publisher.bio ? (
          <Text className="mt-2 block text-sm leading-6 text-slate-600">{detail.publisher.bio}</Text>
        ) : null}
        <Text className="mt-3 block text-sm text-slate-800">
          {detail.court.name} {detail.court.address}
        </Text>
        <Text className="mt-1 block text-sm text-slate-700">
          {detail.date} {detail.timeSlot} · {detail.matchType === 'doubles' ? '双打' : '单打'}
        </Text>
        <Text className="mt-1 block text-sm text-slate-700">
          人数 {detail.filledCount + 1}/{detail.slotsNeeded + 1} · {matchStatusLabel(detail.status)}
        </Text>
        <Text className="mt-1 block text-xs text-slate-500">
          期望等级 {detail.expectedNtrpMin ?? '不限'} - {detail.expectedNtrpMax ?? '不限'} · 性别
          {genderPrefLabel(detail.genderPref)}
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
            {person.user.ntrp ?? '--'} · {person.arrived ? '已到场' : '未到场'}
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
