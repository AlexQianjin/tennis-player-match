import { Text, View } from 'virtual:taro/components'
import { useDidShow, useLoad } from 'virtual:taro/api'
import { useState } from 'react'
import { messageFor } from '../../../services/errors.ts'
import { presentError } from '../../../services/feedback.ts'
import { request } from '../../../services/request.ts'
import type { MatchSummary } from '../../../stores/recommend.ts'

interface ApplicationItem {
  applicationId: string
  applicant: MatchSummary['publisher'] & { bio: string | null; style: string[] }
  status: string
  applyTime: string
  llmScore: number | null
  matchReason: string | null
}

const STATUS_LABEL: Record<string, string> = {
  pending: '待处理',
  agreed: '已同意',
  rejected: '已拒绝',
  cancelled: '已取消',
}

export default function ApplicationsPage() {
  const [requestId, setRequestId] = useState('')
  const [items, setItems] = useState<ApplicationItem[]>([])
  const [busyId, setBusyId] = useState('')
  const [failed, setFailed] = useState('')

  async function load(id: string): Promise<void> {
    const data = await request<{ list: ApplicationItem[] }>({
      url: `/match/applications?requestId=${id}`,
    })
    setItems(data.list)
    setFailed('')
  }

  useLoad((query) => {
    const id = typeof query.requestId === 'string' ? query.requestId : ''
    setRequestId(id)
    if (id) {
      void load(id).catch(async (error: unknown) => {
        setFailed(messageFor(error))
        await presentError(error)
      })
    }
  })

  useDidShow(() => {
    if (!requestId) return
    void load(requestId).catch(async (error: unknown) => {
      setFailed(messageFor(error))
      await presentError(error)
    })
  })

  async function handle(applicationId: string, action: 'agree' | 'reject'): Promise<void> {
    setBusyId(applicationId)
    try {
      await request({ url: '/match/handle', method: 'POST', data: { applicationId, action } })
      await load(requestId)
    } catch (error) {
      await presentError(error)
    } finally {
      setBusyId('')
    }
  }

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">申请列表</Text>
      {failed ? <Text className="mt-4 block text-sm text-rose-700">{failed}</Text> : null}
      {!failed && items.length === 0 ? (
        <Text className="mt-4 block text-sm text-slate-500">还没有申请</Text>
      ) : null}
      {items.map((item) => (
        <View key={item.applicationId} className="mt-4 rounded-2xl bg-white px-4 py-4">
          <Text className="block text-base font-semibold text-slate-900">
            {item.applicant.nickname || '球友'} · NTRP {item.applicant.ntrp ?? '--'}
          </Text>
          <Text className="mt-1 block text-xs text-slate-500">
            信用分 {item.applicant.creditScore} · {STATUS_LABEL[item.status] ?? item.status}
          </Text>
          {item.applicant.bio ? (
            <Text className="mt-2 block text-sm text-slate-600">{item.applicant.bio}</Text>
          ) : null}
          {item.matchReason ? (
            <Text className="mt-2 block text-xs text-emerald-800">{item.matchReason}</Text>
          ) : null}
          {item.status === 'pending' ? (
            <View className="mt-3 flex flex-row gap-3">
              <Text className="text-sm text-emerald-800" onClick={() => void handle(item.applicationId, 'agree')}>
                {busyId === item.applicationId ? '处理中…' : '同意'}
              </Text>
              <Text className="text-sm text-rose-700" onClick={() => void handle(item.applicationId, 'reject')}>
                拒绝
              </Text>
            </View>
          ) : null}
        </View>
      ))}
    </View>
  )
}
