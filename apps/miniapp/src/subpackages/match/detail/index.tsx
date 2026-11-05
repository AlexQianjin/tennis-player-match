import { Text, View } from 'virtual:taro/components'
import { useLoad } from 'virtual:taro/api'
import { lazy, Suspense, useState } from 'react'

const DetailPanel = lazy(() => import('./detail-panel.tsx'))

export default function MatchDetailPage() {
  const [requestId, setRequestId] = useState('')

  useLoad((query) => {
    setRequestId(typeof query.id === 'string' ? query.id : '')
  })

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">约球详情</Text>
      <Suspense fallback={<Text className="mt-4 block text-sm text-slate-500">加载中…</Text>}>
        {requestId ? (
          <DetailPanel requestId={requestId} />
        ) : (
          <Text className="mt-4 block text-sm text-slate-500">缺少约球编号</Text>
        )}
      </Suspense>
    </View>
  )
}
