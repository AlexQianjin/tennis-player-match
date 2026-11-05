import { ApiError, NetworkError } from './envelope.ts'

export function formatCooldownMessage(nextEditableAt: string | null | undefined): string {
  if (!nextEditableAt) return '每月仅可修改一次'
  const parsed = new Date(nextEditableAt)
  if (Number.isNaN(parsed.getTime())) return '每月仅可修改一次'
  const formatted = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(parsed)
  return `每月仅可修改一次，请于${formatted}后修改`
}

export function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 40301) {
      const next = readNextEditableAt(error.data)
      return formatCooldownMessage(next)
    }
    if (error.code === 40001) return '资料未完善，请先完善资料'
    if (error.code === 40004) return '头像文件无效'
    if (error.code === 401) return '请在微信中打开'
    return error.message || '请求失败'
  }
  if (error instanceof NetworkError) return error.message
  if (error instanceof Error && error.message) return error.message
  return '网络异常，请检查后重试'
}

function readNextEditableAt(data: unknown): string | null {
  if (!data || typeof data !== 'object' || !('nextEditableAt' in data)) return null
  const value = data.nextEditableAt
  return typeof value === 'string' ? value : null
}
