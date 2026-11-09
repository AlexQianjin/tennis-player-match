import { Input, Text, View } from 'virtual:taro/components'
import Taro, { useLoad } from 'virtual:taro/api'
import { useState } from 'react'
import { DEV_OPENID_KEY } from '../../../services/request.ts'
import { useAuthStore } from '../../../stores/auth.ts'

export default function SettingsPage() {
  const httpTransport = import.meta.env.TARO_APP_TRANSPORT !== 'cloud'
  const [openid, setOpenid] = useState('dev_user_1')
  const profile = useAuthStore((state) => state.profile)

  useLoad(() => {
    if (!httpTransport) return
    try {
      const stored = Taro.getStorageSync(DEV_OPENID_KEY) as unknown
      if (typeof stored === 'string' && stored.trim()) setOpenid(stored.trim())
    } catch {
      // Keep the default dev user.
    }
  })

  return (
    <View className="min-h-screen bg-slate-50 px-6 py-8">
      <Text className="block text-2xl font-bold text-emerald-800">设置</Text>
      <Text className="mt-3 block text-sm leading-6 text-slate-600">
        {httpTransport
          ? '本地联调用下面的测试账号区分用户。清除缓存会保留当前测试账号，并重新登录。'
          : '清除本地缓存不会更换微信账号；身份仍是当前登录用户。'}
      </Text>
      {profile ? (
        <Text className="mt-3 block text-xs text-slate-500">当前用户 {profile.id}</Text>
      ) : null}
      {httpTransport ? (
        <View className="mt-6 rounded-2xl bg-white px-4 py-4">
          <Text className="block text-xs text-slate-500">本地测试账号（X-Dev-Openid）</Text>
          <Input
            className="mt-2 text-sm"
            value={openid}
            maxlength={64}
            onInput={(event) => setOpenid(event.detail.value)}
          />
          <View
            className="mt-4 rounded-full bg-emerald-800 px-4 py-2"
            onClick={() => {
              const next = openid.trim()
              if (!next) return
              try {
                Taro.setStorageSync(DEV_OPENID_KEY, next)
              } catch {
                return
              }
              useAuthStore.getState().clearLocal()
              void useAuthStore.getState().bootstrap()
              void Taro.showToast({ title: '已切换账号', icon: 'none' })
            }}
          >
            <Text className="text-sm text-white">保存并重新登录</Text>
          </View>
        </View>
      ) : (
        <Text className="mt-6 block text-sm text-slate-600">云托管通道使用微信身份，不能切换测试账号。</Text>
      )}
      <View
        className="mt-4 rounded-2xl bg-white px-4 py-3"
        onClick={() => {
          let preserved = ''
          if (httpTransport) {
            try {
              const stored = Taro.getStorageSync(DEV_OPENID_KEY) as unknown
              if (typeof stored === 'string') preserved = stored.trim()
            } catch {
              preserved = ''
            }
          }
          useAuthStore.getState().clearLocal()
          try {
            Taro.clearStorageSync()
            if (preserved) Taro.setStorageSync(DEV_OPENID_KEY, preserved)
          } catch {
            // Ignore storage failures.
          }
          void useAuthStore.getState().bootstrap()
          void Taro.showToast({ title: '已清除本地缓存', icon: 'none' })
        }}
      >
        <Text className="text-sm text-slate-800">清除本地缓存</Text>
      </View>
    </View>
  )
}
