import { MATCH_STATUS_LABEL, type MatchStatus } from '@tennis/shared'

export function genderLabel(gender: string | null | undefined): string {
  if (gender === 'female') return '女'
  if (gender === 'male') return '男'
  return '未填'
}

export function genderPrefLabel(pref: string | null | undefined): string {
  if (pref === 'male') return '男'
  if (pref === 'female') return '女'
  return '不限'
}

const STYLE_LABEL: Record<string, string> = {
  singles: '单打',
  doubles: '双打',
  casual: '休闲',
  competitive: '竞技',
}

export function styleLabel(style: string): string {
  return STYLE_LABEL[style] ?? style
}

export function matchStatusLabel(status: string): string {
  if (status in MATCH_STATUS_LABEL) return MATCH_STATUS_LABEL[status as MatchStatus]
  return status
}
