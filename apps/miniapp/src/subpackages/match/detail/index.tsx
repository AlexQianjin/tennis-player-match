import { Text, View } from 'virtual:taro/components'
import { lazy, Suspense } from 'react'

const DetailPanel = lazy(() => import('./detail-panel.tsx'))

export default function MatchDetailPage() {
  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">约球详情</Text>
      <Suspense fallback={<Text className="mt-4 block text-sm text-slate-500">加载中…</Text>}>
        <DetailPanel />
      </Suspense>
    </View>
  )
}
