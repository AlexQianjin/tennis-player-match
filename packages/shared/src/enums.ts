export const GENDER = {
  male: 1,
  female: 2,
} as const

export const GENDER_PREF = {
  any: 0,
  male: 1,
  female: 2,
} as const

export const MATCH_TYPE = {
  singles: 1,
  doubles: 2,
} as const

export const MATCH_STATUS = {
  pending: 1,
  matched: 2,
  completed: 3,
  cancelled: 4,
} as const

export const APPLICATION_STATUS = {
  pending: 1,
  agreed: 2,
  rejected: 3,
  cancelled: 4,
} as const

export const PLAY_STYLES = ['singles', 'doubles', 'casual', 'competitive'] as const

export const MATCH_STATUS_LABEL = {
  pending: '待匹配',
  matched: '已匹配',
  completed: '已完成',
  cancelled: '已取消',
} as const

export type Gender = keyof typeof GENDER
export type GenderPref = keyof typeof GENDER_PREF
export type MatchType = keyof typeof MATCH_TYPE
export type MatchStatus = keyof typeof MATCH_STATUS
export type ApplicationStatus = keyof typeof APPLICATION_STATUS
export type PlayStyle = (typeof PLAY_STYLES)[number]
