import { Button, Input, Picker, Text, Textarea, View } from 'virtual:taro/components'
import Taro, { useLoad } from 'virtual:taro/api'
import { useState } from 'react'
import { formatCooldownMessage } from '../../../services/errors.ts'
import { presentError } from '../../../services/feedback.ts'
import { uploadAvatarFile } from '../../../services/upload.ts'
import { useAuthStore, type ProfileInput } from '../../../stores/auth.ts'

const NTRP_VALUES = Array.from({ length: 13 }, (_, index) => (1 + index * 0.5).toFixed(1))
const GENDERS = [
  { id: 'male', label: '男' },
  { id: 'female', label: '女' },
] as const
const STYLES = [
  { id: 'singles', label: '单打' },
  { id: 'doubles', label: '双打' },
  { id: 'casual', label: '休闲' },
  { id: 'competitive', label: '竞技' },
] as const
const CITIES = ['武汉']

type Gender = (typeof GENDERS)[number]['id']
type StyleId = (typeof STYLES)[number]['id']

function ntrpLocked(nextEditableAt: string | null): boolean {
  if (!nextEditableAt) return false
  const time = new Date(nextEditableAt).getTime()
  return !Number.isNaN(time) && time > Date.now()
}

export default function ProfileEditPage() {
  const updateProfile = useAuthStore((state) => state.updateProfile)
  const [mode, setMode] = useState<'onboarding' | 'edit'>('edit')
  const [nickname, setNickname] = useState('')
  const [avatar, setAvatar] = useState('')
  const [preview, setPreview] = useState('')
  const [ntrp, setNtrp] = useState('')
  const [locked, setLocked] = useState(false)
  const [cooldownText, setCooldownText] = useState('')
  const [gender, setGender] = useState<Gender | ''>('')
  const [age, setAge] = useState('')
  const [city, setCity] = useState('武汉')
  const [styles, setStyles] = useState<StyleId[]>([])
  const [bio, setBio] = useState('')
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)

  useLoad((query) => {
    const nextMode = query.mode === 'onboarding' ? 'onboarding' : 'edit'
    setMode(nextMode)
    void Taro.setNavigationBarTitle({ title: nextMode === 'onboarding' ? '完善资料' : '编辑资料' })
    void (async () => {
      const state = useAuthStore.getState()
      if (!state.ready) await state.bootstrap()
      try {
        await useAuthStore.getState().refreshProfile()
      } catch (error) {
        await presentError(error)
      }
      const profile = useAuthStore.getState().profile
      if (!profile) return
      setNickname(profile.nickname ?? '')
      setAvatar(profile.avatar ?? '')
      setNtrp(profile.ntrp == null ? '' : profile.ntrp.toFixed(1))
      const isLocked = ntrpLocked(profile.ntrpNextEditableAt)
      setLocked(isLocked)
      setCooldownText(isLocked ? formatCooldownMessage(profile.ntrpNextEditableAt) : '')
      setGender(profile.gender === 'male' || profile.gender === 'female' ? profile.gender : '')
      setAge(profile.age == null ? '' : String(profile.age))
      setCity(profile.city || '武汉')
      setStyles(profile.style.filter((item): item is StyleId => STYLES.some((style) => style.id === item)))
      setBio(profile.bio ?? '')
    })()
  })

  const ntrpIndex = Math.max(NTRP_VALUES.indexOf(ntrp), 0)
  const genderIndex = Math.max(
    GENDERS.findIndex((item) => item.id === gender),
    0,
  )

  async function onChooseAvatar(avatarUrl: string): Promise<void> {
    setUploading(true)
    setPreview(avatarUrl)
    try {
      const fileId = await uploadAvatarFile(avatarUrl)
      setAvatar(fileId)
    } catch (error) {
      setPreview('')
      await presentError(error)
    } finally {
      setUploading(false)
    }
  }

  function toggleStyle(id: StyleId): void {
    setStyles((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  async function save(): Promise<void> {
    const trimmedName = nickname.trim()
    const ageNumber = Number(age)
    if (!trimmedName || trimmedName.length > 20) {
      await presentError(new Error('昵称需要 1-20 个字'))
      return
    }
    if (!avatar) {
      await presentError(new Error('请选择头像'))
      return
    }
    if (!ntrp) {
      await presentError(new Error('请选择 NTRP'))
      return
    }
    if (gender !== 'male' && gender !== 'female') {
      await presentError(new Error('请选择性别'))
      return
    }
    if (!Number.isInteger(ageNumber) || ageNumber < 6 || ageNumber > 99) {
      await presentError(new Error('年龄需要在 6-99 岁'))
      return
    }
    if (!city) {
      await presentError(new Error('请选择城市'))
      return
    }
    if (bio.trim().length > 500) {
      await presentError(new Error('简介不能超过 500 字'))
      return
    }
    const payload: ProfileInput = {
      nickname: trimmedName,
      avatar,
      gender,
      age: ageNumber,
      city,
      style: styles,
      bio: bio.trim(),
    }
    if (!locked) payload.ntrp = Number(ntrp)
    setSaving(true)
    try {
      const saved = await updateProfile(payload)
      await Taro.showToast({ title: saved.profileCompleted ? '资料已保存' : '已保存', icon: 'none' })
      const pages = Taro.getCurrentPages()
      if (pages.length > 1) {
        await Taro.navigateBack()
      } else {
        await Taro.switchTab({ url: '/pages/me/index' })
      }
    } catch (error) {
      await presentError(error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">
        {mode === 'onboarding' ? '完善资料' : '编辑资料'}
      </Text>
      <Text className="mt-2 block text-sm leading-6 text-slate-500">
        头像、昵称、NTRP、性别、年龄和城市为必填。风格和简介选填，填写简介有助于之后的推荐。
      </Text>

      <View className="mt-6 rounded-2xl bg-white px-4 py-4">
        <Text className="block text-xs text-slate-500">头像</Text>
        <Button
          className="avatar-btn"
          openType="chooseAvatar"
          onChooseAvatar={(event) => {
            const avatarUrl = (event.detail as { avatarUrl?: string }).avatarUrl
            if (avatarUrl) void onChooseAvatar(avatarUrl)
          }}
        >
          {uploading ? '上传中…' : avatar || preview ? '重新选择头像' : '选择头像'}
        </Button>
        {avatar ? <Text className="mt-2 block text-xs text-slate-500">已记录头像文件</Text> : null}
      </View>

      <View className="mt-4 rounded-2xl bg-white px-4 py-4">
        <Text className="block text-xs text-slate-500">昵称</Text>
        <Input
          className="mt-2 text-sm"
          type="nickname"
          maxlength={20}
          placeholder="1-20 个字"
          value={nickname}
          onInput={(event) => setNickname(event.detail.value)}
        />
      </View>

      <View className="mt-4 rounded-2xl bg-white px-4 py-4">
        <Text className="block text-xs text-slate-500">NTRP</Text>
        {locked ? (
          <Text className="mt-2 block text-sm leading-6 text-slate-700">
            {ntrp || '--'}。{cooldownText}
          </Text>
        ) : (
          <Picker
            mode="selector"
            range={NTRP_VALUES}
            value={ntrpIndex}
            onChange={(event) => setNtrp(NTRP_VALUES[Number(event.detail.value)] ?? '')}
          >
            <Text className="mt-2 block text-sm text-slate-800">{ntrp || '请选择，步长 0.5'}</Text>
          </Picker>
        )}
      </View>

      <View className="mt-4 rounded-2xl bg-white px-4 py-4">
        <Text className="block text-xs text-slate-500">性别</Text>
        <Picker
          mode="selector"
          range={GENDERS.map((item) => item.label)}
          value={gender ? genderIndex : 0}
          onChange={(event) => {
            const next = GENDERS[Number(event.detail.value)]
            if (next) setGender(next.id)
          }}
        >
          <Text className="mt-2 block text-sm text-slate-800">
            {GENDERS.find((item) => item.id === gender)?.label ?? '请选择'}
          </Text>
        </Picker>
      </View>

      <View className="mt-4 rounded-2xl bg-white px-4 py-4">
        <Text className="block text-xs text-slate-500">年龄</Text>
        <Input
          className="mt-2 text-sm"
          type="number"
          maxlength={2}
          placeholder="6-99"
          value={age}
          onInput={(event) => setAge(event.detail.value)}
        />
      </View>

      <View className="mt-4 rounded-2xl bg-white px-4 py-4">
        <Text className="block text-xs text-slate-500">城市</Text>
        <Picker
          mode="selector"
          range={CITIES}
          value={Math.max(CITIES.indexOf(city), 0)}
          onChange={(event) => setCity(CITIES[Number(event.detail.value)] ?? '武汉')}
        >
          <Text className="mt-2 block text-sm text-slate-800">{city}</Text>
        </Picker>
      </View>

      <View className="mt-4 rounded-2xl bg-white px-4 py-4">
        <Text className="block text-xs text-slate-500">打球风格（可多选）</Text>
        <View className="mt-3 flex flex-row flex-wrap gap-2">
          {STYLES.map((item) => {
            const selected = styles.includes(item.id)
            return (
              <View
                key={item.id}
                className={selected ? 'rounded-full bg-emerald-800 px-3 py-1' : 'rounded-full bg-slate-100 px-3 py-1'}
                onClick={() => toggleStyle(item.id)}
              >
                <Text className={selected ? 'text-xs text-white' : 'text-xs text-slate-700'}>{item.label}</Text>
              </View>
            )
          })}
        </View>
      </View>

      <View className="mt-4 rounded-2xl bg-white px-4 py-4">
        <Text className="block text-xs text-slate-500">简介 / 期望（选填）</Text>
        <Textarea
          className="mt-2 h-24 w-full text-sm"
          maxlength={500}
          placeholder="填写简介可获得更精准的推荐"
          value={bio}
          onInput={(event) => setBio(event.detail.value)}
        />
      </View>

      <View
        className="mt-6 rounded-2xl bg-emerald-700 px-4 py-3"
        onClick={() => {
          if (!saving && !uploading) void save()
        }}
      >
        <Text className="text-center text-sm font-semibold text-white">
          {saving ? '保存中…' : '保存'}
        </Text>
      </View>
    </View>
  )
}
