import { Text, View } from 'virtual:taro/components'
import { useLoad } from 'virtual:taro/api'
import { useState } from 'react'
import { ApiError, NetworkError } from '../../../services/envelope.ts'
import { presentError } from '../../../services/feedback.ts'
import { enqueueRating, flushPendingRatings } from '../../../services/offline-queue.ts'
import { request } from '../../../services/request.ts'
import { useAuthStore } from '../../../stores/auth.ts'
import type { MatchSummary } from '../../../stores/recommend.ts'

interface Participant {
  user: MatchSummary['publisher']
  role: string
}

interface Detail extends MatchSummary {
  participants: Participant[]
}

export default function RatePage() {
  const [requestId, setRequestId] = useState('')
  const [people, setPeople] = useState<Participant['user'][]>([])
  const [scores, setScores] = useState<Record<string, number>>({})
  const [done, setDone] = useState('')

  useLoad((query) => {
    const id = typeof query.id === 'string' ? query.id : ''
    setRequestId(id)
    void (async () => {
      await flushPendingRatings()
      if (!id) return
      try {
        const detail = await request<Detail>({ url: `/match/detail/${id}` })
        const myId = useAuthStore.getState().profile?.id
        setPeople(detail.participants.map((person) => person.user).filter((user) => user.id !== myId))
        if (!detail.availableActions.includes('rate')) setDone('已评分')
      } catch (error) {
        await presentError(error)
      }
    })()
  })

  async function submit(): Promise<void> {
    if (people.some((person) => !scores[person.id])) {
      await presentError(new Error('请给每位球友打分'))
      return
    }
    const payload = {
      requestId,
      ratings: people.map((person) => ({ rateeId: person.id, score: scores[person.id] ?? 0 })),
    }
    try {
      const result = await request<{ myCreditScore: number }>({
        url: '/match/rate',
        method: 'POST',
        data: payload,
      })
      setDone(`评分已提交，信用分 ${result.myCreditScore}`)
    } catch (error) {
      if (error instanceof NetworkError || (error instanceof ApiError && error.code === 50301)) {
        enqueueRating(payload)
        setDone('已保存，联网后自动提交')
        return
      }
      if (error instanceof ApiError && error.code === 40905) {
        setDone('已评分，不可修改')
        return
      }
      await presentError(error)
    }
  }

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">评分</Text>
      <Text className="mt-2 block text-sm text-slate-500">请给其他每位参与者打 1 到 5 星，提交后不能修改。</Text>
      {done ? <Text className="mt-4 block text-sm text-emerald-800">{done}</Text> : null}
      {people.map((person) => (
        <View key={person.id} className="mt-4 rounded-2xl bg-white px-4 py-3">
          <Text className="block text-sm text-slate-800">{person.nickname || '球友'}</Text>
          <View className="mt-2 flex flex-row gap-2">
            {[1, 2, 3, 4, 5].map((score) => (
              <Text
                key={score}
                className={scores[person.id] === score ? 'text-emerald-800' : 'text-slate-400'}
                onClick={() => setScores((current) => ({ ...current, [person.id]: score }))}
              >
                {score}星
              </Text>
            ))}
          </View>
        </View>
      ))}
      {!done && people.length > 0 ? (
        <View className="mt-6 rounded-2xl bg-emerald-700 px-4 py-3" onClick={() => void submit()}>
          <Text className="text-sm font-semibold text-white">提交评分</Text>
        </View>
      ) : null}
    </View>
  )
}
