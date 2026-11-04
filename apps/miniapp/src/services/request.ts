import Taro from 'virtual:taro/api'
import type { ApiResponse } from '@tennis/shared'
import { NetworkError, RETRY_DELAYS_MS, shouldRetry, unwrap } from './envelope.ts'

export interface RequestOptions {
  url: string
  method?: 'GET' | 'POST'
  data?: Record<string, unknown>
}

const DEV_OPENID_KEY = 'devOpenid'
let warmedUp = false

function requestId(): string {
  const cryptoRef = globalThis.crypto
  if (cryptoRef && typeof cryptoRef.randomUUID === 'function') {
    return cryptoRef.randomUUID()
  }
  return `req_${Date.now().toString(16)}_${Math.random().toString(16).slice(2)}`
}

function devOpenid(): string {
  try {
    const stored = Taro.getStorageSync(DEV_OPENID_KEY)
    if (typeof stored === 'string' && stored.trim()) return stored.trim()
  } catch {
    // Storage is unavailable outside the mini program runtime.
  }
  return 'dev_user_1'
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

async function showWarming(): Promise<void> {
  try {
    await Taro.showToast({ title: '服务启动中…', icon: 'none' })
  } catch {
    // Toast is best-effort during cold start.
  }
}

async function dispatch<T>(options: RequestOptions, attempt: number): Promise<ApiResponse<T>> {
  const header = {
    'X-Request-Id': requestId(),
  }
  const timeout = attempt === 0 && !warmedUp ? 15000 : 10000
  if (import.meta.env.TARO_APP_TRANSPORT === 'cloud') {
    const response = await Taro.cloud.callContainer({
      config: { env: import.meta.env.TARO_APP_CLOUD_ENV },
      path: `/api/v1${options.url}`,
      method: options.method ?? 'GET',
      data: options.data,
      timeout,
      header: {
        ...header,
        'X-WX-SERVICE': import.meta.env.TARO_APP_CLOUD_SERVICE,
      },
    })
    return response.data as ApiResponse<T>
  }

  const response = await Taro.request<ApiResponse<T>>({
    url: `${import.meta.env.TARO_APP_API_BASE_URL}${options.url}`,
    method: options.method ?? 'GET',
    data: options.data,
    timeout,
    header: {
      ...header,
      'X-Dev-Openid': devOpenid(),
    },
  })
  return response.data
}

export async function request<T>(options: RequestOptions, attempt = 0): Promise<T> {
  let body: ApiResponse<T>
  try {
    body = await dispatch<T>(options, attempt)
    warmedUp = true
  } catch (error) {
    if (shouldRetry(null, attempt)) {
      await showWarming()
      await sleep(RETRY_DELAYS_MS[attempt] ?? 1000)
      return request<T>(options, attempt + 1)
    }
    throw new NetworkError(error)
  }

  if (body.code === 50301 && shouldRetry(body.code, attempt)) {
    await showWarming()
    await sleep(RETRY_DELAYS_MS[attempt] ?? 1000)
    return request<T>(options, attempt + 1)
  }
  return unwrap(body)
}
