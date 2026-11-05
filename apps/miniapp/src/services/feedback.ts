import Taro from 'virtual:taro/api'
import { messageFor } from './errors.ts'

export async function presentError(error: unknown): Promise<void> {
  const content = messageFor(error)
  try {
    if (content.length > 14) {
      await Taro.showModal({ title: '提示', content, showCancel: false })
      return
    }
    await Taro.showToast({ title: content, icon: 'none' })
  } catch {
    // Toast is unavailable outside the mini program runtime.
  }
}
