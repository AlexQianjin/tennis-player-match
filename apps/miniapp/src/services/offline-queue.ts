import Taro from 'virtual:taro/api'
import { ApiError, NetworkError } from './envelope.ts'
import { request } from './request.ts'

const KEY = 'pendingRatings'

export interface PendingRating {
  requestId: string
  ratings: { rateeId: string; score: number }[]
}

function readQueue(): PendingRating[] {
  try {
    const raw = Taro.getStorageSync(KEY) as unknown
    const text = typeof raw === 'string' ? raw : ''
    if (!text) return []
    const parsed = JSON.parse(text) as PendingRating[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeQueue(items: PendingRating[]): void {
  try {
    Taro.setStorageSync(KEY, JSON.stringify(items))
  } catch {
    // Storage can be unavailable outside the mini program runtime.
  }
}

export function enqueueRating(item: PendingRating): void {
  const rest = readQueue().filter((row) => row.requestId !== item.requestId)
  rest.push(item)
  writeQueue(rest)
}

export async function flushPendingRatings(): Promise<void> {
  const pending = readQueue()
  if (pending.length === 0) return
  const kept: PendingRating[] = []
  for (const item of pending) {
    try {
      await request({ url: '/match/rate', method: 'POST', data: item })
    } catch (error) {
      if (error instanceof ApiError && (error.code === 40905 || error.code === 400)) continue
      if (error instanceof NetworkError) kept.push(item)
    }
  }
  writeQueue(kept)
}
