import { Text, View } from 'virtual:taro/components'
import { useLoad } from 'virtual:taro/api'
import { useState } from 'react'
import { ProfileGate } from '../../../components/profile-gate.tsx'

const TITLES: Record<string, string> = {
  published: '我发布的',
  applied: '我申请的',
  matched: '已匹配成功的',
}

export default function MyListPage() {
  const [title, setTitle] = useState('我的列表')

  useLoad((query) => {
    const type = typeof query.type === 'string' ? query.type : ''
    setTitle(TITLES[type] ?? '我的列表')
  })

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">{title}</Text>
      <ProfileGate action="查看约球记录" />
      <Text className="mt-3 block text-sm leading-6 text-slate-600">列表会在后续版本接上。</Text>
    </View>
  )
}
