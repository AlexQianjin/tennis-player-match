import { create } from 'zustand'
import { request } from '../services/request.ts'

export interface MatchPublisher {
  id: string
  nickname: string | null
  avatar: string | null
  ntrp: number | null
  gender: string | null
  creditScore: number
  avgRating: number | null
  ratingCount: number
}

export interface MatchCourt {
  id: string
  name: string
  district: string | null
  address: string
}

export interface MatchSummary {
  id: string
  status: string
  matchType: 'singles' | 'doubles'
  slotsNeeded: number
  filledCount: number
  date: string
  timeSlot: string
  startAt: string
  court: MatchCourt
  publisher: MatchPublisher
  expectedNtrpMin: number | null
  expectedNtrpMax: number | null
  genderPref: string
  myRole: string
  myApplicationStatus: string | null
  myApplicationId: string | null
  availableActions: string[]
}

export interface RecommendItem extends MatchSummary {
  ruleScore: number
  llmScore: number | null
  finalScore: number | null
  matchReason: string | null
}

export interface RecommendFilters {
  ntrpMin?: number
  ntrpMax?: number
  gender?: 'male' | 'female'
  date?: string
  timeSlot?: string
  courtId?: string
}

interface RecommendPage {
  list: RecommendItem[]
  page: number
  pageSize: number
  total: number
  hasMore: boolean
  llmApplied: boolean
}

interface RecommendState {
  filters: RecommendFilters
  list: RecommendItem[]
  page: number
  hasMore: boolean
  loading: boolean
  llmApplied: boolean
  error: string | null
  setFilters: (filters: RecommendFilters) => void
  resetFilters: () => void
  refresh: (city: string) => Promise<void>
  loadMore: (city: string) => Promise<void>
}

function query(city: string, filters: RecommendFilters, page: number): string {
  const params = new URLSearchParams({ city, page: String(page), pageSize: '10' })
  if (filters.ntrpMin != null) params.set('ntrpMin', String(filters.ntrpMin))
  if (filters.ntrpMax != null) params.set('ntrpMax', String(filters.ntrpMax))
  if (filters.gender) params.set('gender', filters.gender)
  if (filters.date) params.set('date', filters.date)
  if (filters.timeSlot) params.set('timeSlot', filters.timeSlot)
  if (filters.courtId) params.set('courtId', filters.courtId)
  return `/match/recommend?${params.toString()}`
}

export const useRecommendStore = create<RecommendState>((set, get) => ({
  filters: {},
  list: [],
  page: 1,
  hasMore: false,
  loading: false,
  llmApplied: false,
  error: null,
  setFilters(filters) {
    set({ filters })
  },
  resetFilters() {
    set({ filters: {} })
  },
  async refresh(city) {
    set({ loading: true, error: null })
    try {
      const data = await request<RecommendPage>({ url: query(city, get().filters, 1) })
      set({
        list: data.list,
        page: 1,
        hasMore: data.hasMore,
        llmApplied: data.llmApplied,
        loading: false,
      })
    } catch (error) {
      set({ loading: false, error: error instanceof Error ? error.message : '加载失败' })
      throw error
    }
  },
  async loadMore(city) {
    const state = get()
    if (state.loading || !state.hasMore) return
    const next = state.page + 1
    set({ loading: true })
    try {
      const data = await request<RecommendPage>({ url: query(city, state.filters, next) })
      set({
        list: [...state.list, ...data.list],
        page: next,
        hasMore: data.hasMore,
        llmApplied: data.llmApplied,
        loading: false,
      })
    } catch (error) {
      set({ loading: false })
      throw error
    }
  },
}))
