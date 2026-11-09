import { Picker, Text, View } from 'virtual:taro/components'
import Taro, { useDidShow } from 'virtual:taro/api'
import { useRef, useState } from 'react'
import { ProfileGate } from '../../components/profile-gate.tsx'
import { presentError } from '../../services/feedback.ts'
import { requireCompleteProfile } from '../../services/onboarding.ts'
import { request } from '../../services/request.ts'
import {
  DATE_WINDOW_DAYS,
  addDays,
  applyDate,
  applyStart,
  defaultSchedule,
  formatDuration,
  repairIfPast,
  scheduleError,
  shanghaiToday,
} from '../../services/schedule.ts'
import { useAuthStore } from '../../stores/auth.ts'
import { useCourtStore, type Court } from '../../stores/court.ts'

const GENDER_PREF = [
  { id: 'any', label: '不限' },
  { id: 'male', label: '男' },
  { id: 'female', label: '女' },
] as const

function courtLabel(court: Court): string {
  return court.district ? `${court.name} · ${court.district}` : court.name
}

export default function PublishPage() {
  const profile = useAuthStore((state) => state.profile)
  const loadCourts = useCourtStore((state) => state.load)
  const initial = defaultSchedule()
  const [courts, setCourts] = useState<Court[]>([])
  const [courtId, setCourtId] = useState('')
  const [hint, setHint] = useState('球场信息加载中')
  const [date, setDate] = useState(initial.date)
  const [startTime, setStartTime] = useState(initial.startTime)
  const [endTime, setEndTime] = useState(initial.endTime)
  const scheduleRef = useRef({ date, startTime, endTime })
  scheduleRef.current = { date, startTime, endTime }
  const [matchType, setMatchType] = useState<'singles' | 'doubles'>('doubles')
  const [slots, setSlots] = useState(3)
  const [genderPref, setGenderPref] = useState<(typeof GENDER_PREF)[number]['id']>('any')
  const [saving, setSaving] = useState(false)

  useDidShow(() => {
    const current = scheduleRef.current
    const repaired = repairIfPast(current)
    if (
      repaired.date !== current.date ||
      repaired.startTime !== current.startTime ||
      repaired.endTime !== current.endTime
    ) {
      setDate(repaired.date)
      setStartTime(repaired.startTime)
      setEndTime(repaired.endTime)
    }
    void loadCourts(profile?.city || '武汉')
      .then((list) => {
        setCourts(list)
        setCourtId((current) => current || list[0]?.id || '')
        setHint(list.length ? '' : '暂无球场。武汉真实场地仍待产品确认，本地可用占位种子导入。')
      })
      .catch(() => setHint('球场信息加载中'))
  })

  const today = shanghaiToday()
  const lastDate = addDays(today, DATE_WINDOW_DAYS)
  const problem = scheduleError({ date, startTime, endTime })
  const selected = courts.find((court) => court.id === courtId) ?? null
  const labels = courts.map(courtLabel)
  const ntrp = profile?.ntrp
  const expected =
    ntrp == null
      ? null
      : {
          min: Math.max(1, ntrp - 0.5),
          max: Math.min(7, ntrp + 0.5),
        }

  async function submit(): Promise<void> {
    if (!requireCompleteProfile()) return
    const invalid = scheduleError({ date, startTime, endTime })
    if (invalid) {
      await presentError(new Error(invalid))
      return
    }
    if (!selected) {
      await presentError(new Error('请选择球场'))
      return
    }
    setSaving(true)
    try {
      await request({
        url: '/match/publish',
        method: 'POST',
        data: {
          date,
          startTime,
          endTime,
          courtId: selected.id,
          matchType,
          slotsNeeded: matchType === 'singles' ? 1 : slots,
          genderPref,
          ...(expected
            ? { expectedNtrpMin: expected.min, expectedNtrpMax: expected.max }
            : {}),
        },
      })
      await useAuthStore.getState().refreshProfile().catch(() => undefined)
      await Taro.showToast({ title: '已发布', icon: 'none' })
      await Taro.switchTab({ url: '/pages/index/index' })
    } catch (error) {
      await presentError(error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">发布约球</Text>
      <ProfileGate action="发布约球" />
      {profile?.activeRequestId ? (
        <Text className="mt-3 block text-sm leading-6 text-amber-800">
          您已有一个进行中的约球，请先完成或取消
        </Text>
      ) : null}
      {hint ? <Text className="mt-4 block text-sm text-slate-500">{hint}</Text> : null}
      {labels.length > 0 ? (
        <Picker
          mode="selector"
          range={labels}
          value={Math.max(
            labels.findIndex((_, index) => courts[index]?.id === courtId),
            0,
          )}
          onChange={(event) => {
            const next = courts[Number(event.detail.value)]
            if (next) setCourtId(next.id)
          }}
        >
          <View className="mt-4 rounded-2xl bg-white px-4 py-3">
            <Text className="block text-xs text-slate-500">球场</Text>
            <Text className="mt-1 block text-sm text-slate-800">
              {selected ? courtLabel(selected) : '请选择球场'}
            </Text>
          </View>
        </Picker>
      ) : null}
      <Picker
        mode="date"
        start={today}
        end={lastDate}
        value={date}
        onChange={(event) => {
          const next = applyDate({ date, startTime, endTime }, String(event.detail.value))
          setDate(next.date)
          setStartTime(next.startTime)
          setEndTime(next.endTime)
        }}
      >
        <View className="mt-3 rounded-2xl bg-white px-4 py-3">
          <Text className="block text-xs text-slate-500">日期（今天起 30 天）</Text>
          <Text className="mt-1 block text-sm">{date}</Text>
        </View>
      </Picker>
      <Picker
        mode="time"
        value={startTime}
        onChange={(event) => {
          const next = applyStart({ date, startTime, endTime }, String(event.detail.value))
          setStartTime(next.startTime)
          setEndTime(next.endTime)
        }}
      >
        <View className="mt-3 rounded-2xl bg-white px-4 py-3">
          <Text className="block text-xs text-slate-500">开始时间</Text>
          <Text className="mt-1 block text-sm">{startTime}</Text>
        </View>
      </Picker>
      <Picker
        mode="time"
        value={endTime}
        onChange={(event) => setEndTime(String(event.detail.value))}
      >
        <View className="mt-3 rounded-2xl bg-white px-4 py-3">
          <Text className="block text-xs text-slate-500">
            结束时间{endTime <= startTime ? '（次日）' : ''}
          </Text>
          <Text className="mt-1 block text-sm">
            {endTime}
            {endTime <= startTime ? ' 次日' : ''} · {formatDuration(startTime, endTime)}
          </Text>
        </View>
      </Picker>
      {problem ? <Text className="mt-3 block text-sm text-amber-800">{problem}</Text> : null}
      <View className="mt-3 flex flex-row gap-2">
        {(['singles', 'doubles'] as const).map((type) => (
          <View
            key={type}
            className={type === matchType ? 'rounded-full bg-emerald-800 px-4 py-2' : 'rounded-full bg-white px-4 py-2'}
            onClick={() => setMatchType(type)}
          >
            <Text className={type === matchType ? 'text-sm text-white' : 'text-sm text-slate-700'}>
              {type === 'singles' ? '单打' : '双打'}
            </Text>
          </View>
        ))}
      </View>
      {matchType === 'doubles' ? (
        <View className="mt-3 flex flex-row gap-2">
          {[1, 2, 3].map((count) => (
            <View
              key={count}
              className={count === slots ? 'rounded-full bg-emerald-800 px-4 py-2' : 'rounded-full bg-white px-4 py-2'}
              onClick={() => setSlots(count)}
            >
              <Text className={count === slots ? 'text-sm text-white' : 'text-sm text-slate-700'}>
                还需 {count} 人
              </Text>
            </View>
          ))}
        </View>
      ) : (
        <Text className="mt-3 block text-sm text-slate-500">单打固定再招募 1 人</Text>
      )}
      <View className="mt-3 flex flex-row gap-2">
        {GENDER_PREF.map((item) => (
          <View
            key={item.id}
            className={item.id === genderPref ? 'rounded-full bg-emerald-800 px-4 py-2' : 'rounded-full bg-white px-4 py-2'}
            onClick={() => setGenderPref(item.id)}
          >
            <Text className={item.id === genderPref ? 'text-sm text-white' : 'text-sm text-slate-700'}>
              性别{item.label}
            </Text>
          </View>
        ))}
      </View>
      {expected ? (
        <Text className="mt-3 block text-xs text-slate-500">
          期望等级 {expected.min.toFixed(1)} - {expected.max.toFixed(1)}（按你的 NTRP ±0.5）
        </Text>
      ) : null}
      <View
        className="mt-6 rounded-2xl bg-emerald-700 px-4 py-3"
        onClick={() => {
          if (!saving) void submit()
        }}
      >
        <Text className="text-sm font-semibold text-white">{saving ? '发布中…' : '发布约球'}</Text>
      </View>
    </View>
  )
}
