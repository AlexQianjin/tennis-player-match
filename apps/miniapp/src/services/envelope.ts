import type { ApiResponse } from '@tennis/shared'

export class ApiError extends Error {
  readonly code: number
  readonly data: unknown

  constructor(code: number, message: string, data: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.data = data
  }
}

export class NetworkError extends Error {
  readonly cause: unknown

  constructor(cause: unknown) {
    super('网络异常，请检查后重试')
    this.name = 'NetworkError'
    this.cause = cause
  }
}

export function coerceEnvelope<T>(payload: unknown): ApiResponse<T> {
  let body: unknown = payload
  if (typeof body === 'string') {
    const text = body.trim()
    if (!text) throw new ApiError(500, '响应格式错误', payload)
    try {
      body = JSON.parse(text) as unknown
    } catch {
      throw new ApiError(500, '响应格式错误', payload)
    }
  }
  if (!body || typeof body !== 'object' || !('code' in body) || typeof body.code !== 'number') {
    throw new ApiError(500, '响应格式错误', payload)
  }
  return body as ApiResponse<T>
}

export function unwrap<T>(body: ApiResponse<T> | null | undefined): T {
  if (!body || typeof body.code !== 'number') {
    throw new ApiError(500, '响应格式错误', body ?? null)
  }
  if (body.code === 0) {
    return body.data
  }
  throw new ApiError(body.code, body.message || '请求失败', body.data)
}

export const RETRY_DELAYS_MS = [1000, 3000] as const

export function shouldRetry(code: number | null, attempt: number): boolean {
  if (attempt >= RETRY_DELAYS_MS.length) return false
  return code === null || code === 50301
}
