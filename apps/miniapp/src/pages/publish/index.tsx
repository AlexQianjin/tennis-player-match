import { Picker, Text, View } from 'virtual:taro/components'
import Taro from 'virtual:taro/api'
import { useDidShow } from 'virtual:taro/api'
import { useState } from 'react'
import { ProfileGate } from '../../components/profile-gate.tsx'
import { requireCompleteProfile } from '../../services/onboarding.ts'
import { useCourtStore, type Court } from '../../stores/court.ts'

function courtLabel(court: Court): string {
  return court.district ? `${court.name} · ${court.district}` : court.name
}

export default function PublishPage() {
  const loadCourts = useCourtStore((state) => state.load)
  const [courts, setCourts] = useState<Court[]>([])
  const [courtId, setCourtId] = useState('')
  const [hint, setHint] = useState('球场信息加载中')

  useDidShow(() => {
    void loadCourts('武汉')
      .then((list) => {
        setCourts(list)
        setCourtId((current) => current || list[0]?.id || '')
        setHint(
          list.length
            ? ''
            : '暂无球场。武汉真实场地仍待产品确认，本地可用占位种子导入。',
        )
      })
      .catch(() => {
        setHint('球场信息加载中')
      })
  })

  const selected = courts.find((court) => court.id === courtId) ?? null
  const labels = courts.map(courtLabel)

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">发布约球</Text>
      <Text className="mt-3 block text-sm leading-6 text-slate-600">
        先选择球场。日期、时段和单双打会在下一版本开放。
      </Text>
      <ProfileGate action="发布约球" />
      {hint ? <Text className="mt-4 block text-sm text-slate-500">{hint}</Text> : null}
      {labels.length > 0 ? (
        <Picker
          mode="selector"
          range={labels}
          value={Math.max(labels.findIndex((_, index) => courts[index]?.id === courtId), 0)}
          onChange={(event) => {
            const index = Number(event.detail.value)
            const next = courts[index]
            if (next) setCourtId(next.id)
          }}
        >
          <View className="mt-4 rounded-2xl bg-white px-4 py-3">
            <Text className="block text-xs text-slate-500">球场</Text>
            <Text className="mt-1 block text-sm text-slate-800">
              {selected ? courtLabel(selected) : '请选择球场'}
            </Text>
            {selected ? (
              <Text className="mt-1 block text-xs text-slate-500">{selected.address}</Text>
            ) : null}
          </View>
        </Picker>
      ) : null}
      <View
        className="mt-6 rounded-2xl bg-emerald-700 px-4 py-3"
        onClick={() => {
          if (!requireCompleteProfile()) return
          void Taro.showToast({ title: '发布即将开放', icon: 'none' })
        }}
      >
        <Text className="text-sm font-semibold text-white">发布约球</Text>
      </View>
    </View>
  )
}
