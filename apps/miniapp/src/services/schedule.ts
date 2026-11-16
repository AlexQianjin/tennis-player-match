/**
 * Publish-time defaults and checks. Asia/Shanghai, no daylight saving.
 *
 * Playable hours are 07:00–22:00 on the chosen date. A match does not cross midnight.
 *
 * Start default: the next whole hour strictly after now. 13:06 → 14:00.
 * 14:00:00 exactly → 15:00 (an on-the-hour instant is not offered as "now").
 * If that hour is before 07:00, use 07:00 on that same date.
 * End default: min(start + 2 hours, 22:00).
 * If the start would be later than 21:30 (not enough room for 30 minutes), roll to
 * tomorrow 07:00–09:00. Near midnight (23:10 → next hour 00:00) the 00:00 is before
 * 07:00, so the default is 07:00–09:00 on that next date, not a second extra day.
 *
 * Changing the start keeps the previous duration, then clamps the end to 22:00.
 * A previous duration outside 30 minutes–8 hours falls back to 2 hours.
 */

export const DATE_WINDOW_DAYS = 30
export const MIN_DURATION_MINUTES = 30
export const MAX_DURATION_MINUTES = 8 * 60
export const DEFAULT_DURATION_MINUTES = 120
export const OPEN_MINUTES = 7 * 60
export const CLOSE_MINUTES = 22 * 60
export const LATEST_START_MINUTES = CLOSE_MINUTES - MIN_DURATION_MINUTES
export const OPEN_TIME = '07:00'
export const CLOSE_TIME = '22:00'
export const LATEST_START_TIME = '21:30'

/** Recommend-filter windows. A request matches when its interval overlaps the window. */
export const TIME_SLOTS = ['09:00-11:00', '14:00-16:00', '16:00-18:00', '19:00-21:00'] as const

const CLOCK = /^([01]\d|2[0-3]):([0-5]\d)$/
const DAY_MINUTES = 24 * 60

export interface ScheduleChoice {
  date: string
  startTime: string
  endTime: string
}

interface WallClock {
  year: number
  month: number
  day: number
  hour: number
  minute: number
  second: number
}

export function shanghaiToday(now = new Date()): string {
  const wall = shanghaiWall(now)
  return isoDate(wall.year, wall.month, wall.day)
}

export function addDays(isoDateText: string, days: number): string {
  const [year, month, day] = isoDateText.split('-').map(Number)
  const utc = new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1))
  utc.setUTCDate(utc.getUTCDate() + days)
  return utc.toISOString().slice(0, 10)
}

export function upcomingDates(now = new Date()): string[] {
  const today = shanghaiToday(now)
  return Array.from({ length: DATE_WINDOW_DAYS + 1 }, (_, index) => addDays(today, index))
}

export function defaultSchedule(now = new Date()): ScheduleChoice {
  const wall = shanghaiWall(now)
  const cursor = new Date(Date.UTC(wall.year, wall.month - 1, wall.day, wall.hour, 0, 0))
  cursor.setUTCHours(cursor.getUTCHours() + 1)
  let date = cursor.toISOString().slice(0, 10)
  let startMin = cursor.getUTCHours() * 60 + cursor.getUTCMinutes()
  if (startMin < OPEN_MINUTES) startMin = OPEN_MINUTES
  if (startMin > LATEST_START_MINUTES) {
    date = addDays(date, 1)
    startMin = OPEN_MINUTES
  }
  const endMin = Math.min(startMin + DEFAULT_DURATION_MINUTES, CLOSE_MINUTES)
  return { date, startTime: fromMinutes(startMin), endTime: fromMinutes(endMin) }
}

export function durationMinutes(startTime: string, endTime: string): number {
  const start = toMinutes(startTime)
  const end = toMinutes(endTime)
  if (start == null || end == null || end <= start) return 0
  return end - start
}

export function shiftEnd(previousStart: string, previousEnd: string, nextStart: string): string {
  let minutes = durationMinutes(previousStart, previousEnd)
  if (minutes < MIN_DURATION_MINUTES || minutes > MAX_DURATION_MINUTES) {
    minutes = DEFAULT_DURATION_MINUTES
  }
  const start = toMinutes(nextStart) ?? OPEN_MINUTES
  return fromMinutes(Math.min(start + minutes, CLOSE_MINUTES))
}

export function earliestEnd(startTime: string): string {
  const start = toMinutes(startTime) ?? OPEN_MINUTES
  const earliest = Math.max(start + MIN_DURATION_MINUTES, OPEN_MINUTES + MIN_DURATION_MINUTES)
  return fromMinutes(Math.min(earliest, CLOSE_MINUTES))
}

export function applyStart(current: ScheduleChoice, startTime: string): ScheduleChoice {
  return {
    ...current,
    startTime,
    endTime: shiftEnd(current.startTime, current.endTime, startTime),
  }
}

export function applyDate(current: ScheduleChoice, nextDate: string, now = new Date()): ScheduleChoice {
  const today = shanghaiToday(now)
  const last = addDays(today, DATE_WINDOW_DAYS)
  let date = nextDate
  if (date < today) date = today
  if (date > last) date = last
  const candidate: ScheduleChoice = { ...current, date }
  if (scheduleError(candidate, now) !== '不能选择过去的时间') return candidate
  const fallback = defaultSchedule(now)
  return {
    date: fallback.date > date ? fallback.date : date,
    startTime: fallback.startTime,
    endTime: shiftEnd(current.startTime, current.endTime, fallback.startTime),
  }
}

export function repairIfPast(current: ScheduleChoice, now = new Date()): ScheduleChoice {
  const error = scheduleError(current, now)
  if (error === '不能选择过去的时间' || error === '开始日期需在今天起 30 天内') {
    return applyDate(current, current.date, now)
  }
  return current
}

export function scheduleError(
  choice: ScheduleChoice,
  now = new Date(),
): string | null {
  if (!CLOCK.test(choice.startTime) || !CLOCK.test(choice.endTime) || !/^\d{4}-\d{2}-\d{2}$/.test(choice.date)) {
    return '时段格式不正确'
  }
  const today = shanghaiToday(now)
  const last = addDays(today, DATE_WINDOW_DAYS)
  const startAt = shanghaiLocalToUtc(choice.date, choice.startTime)
  if (choice.date < today || startAt.getTime() <= now.getTime()) return '不能选择过去的时间'
  if (choice.date > last) return '开始日期需在今天起 30 天内'
  const startMin = toMinutes(choice.startTime) ?? -1
  const endMin = toMinutes(choice.endTime) ?? -1
  if (startMin < OPEN_MINUTES) return '开始时间不能早于 07:00'
  if (endMin > CLOSE_MINUTES) return '结束时间不能晚于 22:00'
  if (endMin <= startMin) return '结束时间需要晚于开始时间'
  const minutes = endMin - startMin
  if (minutes < MIN_DURATION_MINUTES) return '时长至少 30 分钟'
  if (minutes > MAX_DURATION_MINUTES) return '时长不能超过 8 小时'
  return null
}

export function formatWhen(date: string, timeSlot: string): string {
  const matched = /^(\d{2}:\d{2})-(\d{2}:\d{2})$/.exec(timeSlot)
  if (!matched) return `${date} ${timeSlot}`.trim()
  return `${date} ${matched[1]}-${matched[2]}`
}

export function formatDuration(startTime: string, endTime: string): string {
  const minutes = durationMinutes(startTime, endTime)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `${rest} 分钟`
  if (rest === 0) return `${hours} 小时`
  return `${hours} 小时 ${rest} 分钟`
}

function shanghaiWall(now: Date): WallClock {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(now)
  const map: Record<string, string> = {}
  for (const part of parts) {
    if (part.type !== 'literal') map[part.type] = part.value
  }
  let hour = Number(map.hour)
  let day = Number(map.day)
  let month = Number(map.month)
  let year = Number(map.year)
  if (hour === 24) {
    hour = 0
    const rolled = addDays(isoDate(year, month, day), 1)
    year = Number(rolled.slice(0, 4))
    month = Number(rolled.slice(5, 7))
    day = Number(rolled.slice(8, 10))
  }
  return {
    year,
    month,
    day,
    hour,
    minute: Number(map.minute),
    second: Number(map.second),
  }
}

function isoDate(year: number, month: number, day: number): string {
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function clockText(hour: number, minute: number): string {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

function toMinutes(value: string): number | null {
  const matched = CLOCK.exec(value)
  if (!matched) return null
  return Number(matched[1]) * 60 + Number(matched[2])
}

function fromMinutes(minutes: number): string {
  const clamped = Math.max(0, Math.min(minutes, DAY_MINUTES - 1))
  return clockText(Math.floor(clamped / 60), clamped % 60)
}

function shanghaiLocalToUtc(date: string, hhmm: string): Date {
  const [year, month, day] = date.split('-').map(Number)
  const [hour, minute] = hhmm.split(':').map(Number)
  return new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1, (hour ?? 0) - 8, minute ?? 0, 0))
}
