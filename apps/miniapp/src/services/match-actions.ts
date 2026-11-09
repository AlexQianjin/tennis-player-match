import Taro from 'virtual:taro/api'
import { useAuthStore } from '../stores/auth.ts'
import { request } from './request.ts'

export interface CancelPreview {
  cancelCounted: boolean
  effect: 'reopen' | 'cancel_all' | 'leave'
}

export async function confirmAndCancel(requestId: string): Promise<boolean> {
  const preview = await request<CancelPreview>({
    url: `/match/cancel/preview?requestId=${requestId}`,
  })
  const counted = preview.cancelCounted ? '取消将计入取消次数。' : '本次不计入取消次数。'
  const effect =
    preview.effect === 'reopen'
      ? '名额将重新开放。'
      : preview.effect === 'leave'
        ? '你将退出该约球。'
        : '将取消整场约球。'
  const modal = await Taro.showModal({ title: '确认取消', content: `${counted}${effect}`, confirmText: '确认' })
  if (!modal.confirm) return false
  await request({ url: '/match/cancel', method: 'POST', data: { requestId } })
  await refreshActiveRequest()
  return true
}

export async function markArrived(requestId: string): Promise<void> {
  await request({ url: '/match/arrive', method: 'POST', data: { requestId } })
  await refreshActiveRequest()
}

async function refreshActiveRequest(): Promise<void> {
  try {
    await useAuthStore.getState().refreshProfile()
  } catch {
    // The write already succeeded. The next page show refreshes the profile.
  }
}
