import { create } from 'zustand'
import { request } from '../services/request.ts'

export interface Court {
  id: string
  name: string
  district: string | null
  address: string
  latitude: number | null
  longitude: number | null
}

interface CourtBucket {
  list: Court[]
  ts: number
}

interface CourtState {
  byCity: Record<string, CourtBucket>
  load: (city: string, force?: boolean) => Promise<Court[]>
}

const TTL_MS = 10 * 60 * 1000

export const useCourtStore = create<CourtState>((set, get) => ({
  byCity: {},
  async load(city, force = false) {
    const cached = get().byCity[city]
    if (!force && cached && Date.now() - cached.ts < TTL_MS) return cached.list
    try {
      const data = await request<{ list: Court[] }>({
        url: `/courts?city=${encodeURIComponent(city)}`,
      })
      const list = data.list ?? []
      set((state) => ({ byCity: { ...state.byCity, [city]: { list, ts: Date.now() } } }))
      return list
    } catch (error) {
      if (cached) return cached.list
      throw error
    }
  },
}))
