export { ERROR_CODES, ERROR_MESSAGES, type ErrorCode } from './errorCodes'
export {
  APPLICATION_STATUS,
  GENDER,
  GENDER_PREF,
  MATCH_STATUS,
  MATCH_STATUS_LABEL,
  MATCH_TYPE,
  PLAY_STYLES,
  type ApplicationStatus,
  type Gender,
  type GenderPref,
  type MatchStatus,
  type MatchType,
  type PlayStyle,
} from './enums'
export type { components, paths } from './generated/api'

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface Page<T> {
  list: T[]
  page: number
  pageSize: number
  total: number
  hasMore: boolean
}
