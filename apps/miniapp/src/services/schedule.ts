export const TIME_SLOTS = ['09:00-11:00', '14:00-16:00', '16:00-18:00', '19:00-21:00'] as const

export function shanghaiToday(now = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)
}

export function addDays(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  const utc = new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1))
  utc.setUTCDate(utc.getUTCDate() + days)
  return utc.toISOString().slice(0, 10)
}

export function upcomingDates(count = 14, now = new Date()): string[] {
  const today = shanghaiToday(now)
  return Array.from({ length: count }, (_, index) => addDays(today, index))
}
