import { Text, View } from 'virtual:taro/components'
import Taro from 'virtual:taro/api'
import { presentError } from '../services/feedback.ts'
import { confirmAndCancel, markArrived } from '../services/match-actions.ts'
import { request } from '../services/request.ts'
import type { MatchSummary } from '../stores/recommend.ts'

const ACTION_LABEL: Record<string, string> = {
  apply: '申请',
  withdraw: '撤回',
  viewApplications: '申请列表',
  cancel: '取消',
  arrive: '到场',
  rate: '评分',
}

export function MatchCard({ item, onChanged }: { item: MatchSummary; onChanged?: () => void }) {
  async function run(action: string): Promise<void> {
    try {
      if (action === 'cancel') {
        if (await confirmAndCancel(item.id)) onChanged?.()
      } else if (action === 'arrive') {
        await markArrived(item.id)
        onChanged?.()
      } else if (action === 'viewApplications') {
        await Taro.navigateTo({ url: `/subpackages/match/applications/index?requestId=${item.id}` })
      } else if (action === 'rate') {
        await Taro.navigateTo({ url: `/subpackages/match/rate/index?id=${item.id}` })
      } else if (action === 'withdraw' && item.myApplicationId) {
        await request({
          url: '/match/application/withdraw',
          method: 'POST',
          data: { applicationId: item.myApplicationId },
        })
        onChanged?.()
      }
    } catch (error) {
      await presentError(error)
    }
  }

  const actions = item.availableActions.filter((action) => action in ACTION_LABEL)

  return (
    <View className="mb-3 rounded-2xl bg-white px-4 py-3">
      <View
        onClick={() => {
          void Taro.navigateTo({ url: `/subpackages/match/detail/index?id=${item.id}` })
        }}
      >
        <Text className="block text-base font-semibold text-slate-900">
          {item.publisher.nickname || '球友'} · {item.matchType === 'doubles' ? '双打' : '单打'}
        </Text>
        <Text className="mt-1 block text-sm text-slate-700">
          {item.court.name} · {item.date} {item.timeSlot}
        </Text>
        <Text className="mt-1 block text-xs text-slate-500">
          人数 {item.filledCount + 1}/{item.slotsNeeded + 1}
        </Text>
      </View>
      <View className="mt-2 flex flex-row flex-wrap gap-3">
        {actions.map((action) => (
          <Text key={action} className="text-sm text-emerald-800" onClick={() => void run(action)}>
            {ACTION_LABEL[action]}
          </Text>
        ))}
      </View>
    </View>
  )
}
