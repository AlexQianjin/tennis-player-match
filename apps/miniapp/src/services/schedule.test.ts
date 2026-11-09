import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  DATE_WINDOW_DAYS,
  addDays,
  applyDate,
  applyStart,
  defaultSchedule,
  formatWhen,
  repairIfPast,
  scheduleError,
  shanghaiToday,
  shiftEnd,
} from './schedule.ts'

function at(iso: string): Date {
  return new Date(iso)
}

describe('defaultSchedule', () => {
  it('uses the next whole hour and a two-hour end', () => {
    const choice = defaultSchedule(at('2026-06-01T05:06:00Z'))
    assert.equal(shanghaiToday(at('2026-06-01T05:06:00Z')), '2026-06-01')
    assert.deepEqual(choice, { date: '2026-06-01', startTime: '14:00', endTime: '16:00' })
  })

  it('moves an exact hour forward as well', () => {
    assert.deepEqual(defaultSchedule(at('2026-06-01T06:00:00.000Z')), {
      date: '2026-06-01',
      startTime: '15:00',
      endTime: '17:00',
    })
    assert.deepEqual(defaultSchedule(at('2026-06-01T06:00:01.000Z')), {
      date: '2026-06-01',
      startTime: '15:00',
      endTime: '17:00',
    })
  })

  it('keeps a late start today and lets the end fall on the next day', () => {
    assert.deepEqual(defaultSchedule(at('2026-06-01T14:30:00Z')), {
      date: '2026-06-01',
      startTime: '23:00',
      endTime: '01:00',
    })
    assert.equal(scheduleError(defaultSchedule(at('2026-06-01T14:30:00Z')), at('2026-06-01T14:30:00Z')), null)
  })

  it('rolls the date when the next hour is after midnight', () => {
    const now = at('2026-06-01T15:10:00Z')
    assert.deepEqual(defaultSchedule(now), {
      date: '2026-06-02',
      startTime: '00:00',
      endTime: '02:00',
    })
    assert.equal(scheduleError(defaultSchedule(now), now), null)
    assert.deepEqual(defaultSchedule(at('2026-06-01T15:00:00Z')), {
      date: '2026-06-02',
      startTime: '00:00',
      endTime: '02:00',
    })
  })
})

describe('shiftEnd', () => {
  it('keeps the duration when the start moves, including across midnight', () => {
    assert.equal(shiftEnd('14:00', '16:30', '18:00'), '20:30')
    assert.equal(shiftEnd('14:00', '16:00', '23:00'), '01:00')
    assert.equal(shiftEnd('22:00', '23:30', '23:30'), '01:00')
  })

  it('falls back to two hours when the previous duration is not allowed', () => {
    assert.equal(shiftEnd('10:00', '20:00', '11:00'), '13:00')
    assert.equal(shiftEnd('10:00', '10:10', '12:00'), '14:00')
  })
})

describe('scheduleError', () => {
  const now = at('2026-06-01T05:06:00Z')

  it('rejects a past start, a short or long window, and a date outside 30 days', () => {
    assert.equal(
      scheduleError({ date: '2026-06-01', startTime: '13:00', endTime: '15:00' }, now),
      '不能选择过去的时间',
    )
    assert.equal(
      scheduleError({ date: '2026-05-31', startTime: '18:00', endTime: '20:00' }, now),
      '不能选择过去的时间',
    )
    assert.equal(
      scheduleError({ date: '2026-06-03', startTime: '15:20', endTime: '15:40' }, now),
      '时长至少 30 分钟',
    )
    assert.equal(
      scheduleError({ date: '2026-06-03', startTime: '15:20', endTime: '15:20' }, now),
      '结束时间需要晚于开始时间',
    )
    assert.equal(
      scheduleError({ date: '2026-06-03', startTime: '10:00', endTime: '19:00' }, now),
      '时长不能超过 8 小时',
    )
    assert.equal(
      scheduleError({ date: '2026-06-03', startTime: '18:00', endTime: '09:00' }, now),
      '时长不能超过 8 小时',
    )
    const tooLate = addDays('2026-06-01', DATE_WINDOW_DAYS + 1)
    assert.equal(
      scheduleError({ date: tooLate, startTime: '10:00', endTime: '12:00' }, now),
      '开始日期需在今天起 30 天内',
    )
  })

  it('accepts 30 minutes, 8 hours, the last window day, and a next-day end', () => {
    assert.equal(scheduleError({ date: '2026-06-03', startTime: '15:20', endTime: '15:50' }, now), null)
    assert.equal(scheduleError({ date: '2026-06-03', startTime: '10:00', endTime: '18:00' }, now), null)
    assert.equal(scheduleError({ date: '2026-06-03', startTime: '23:00', endTime: '01:00' }, now), null)
    const last = addDays('2026-06-01', DATE_WINDOW_DAYS)
    assert.equal(scheduleError({ date: last, startTime: '23:00', endTime: '01:00' }, now), null)
    assert.equal(scheduleError({ date: '2026-06-01', startTime: '14:00', endTime: '16:00' }, now), null)
  })
})

describe('applyStart and applyDate', () => {
  it('shifts the end with the start and repairs a past selection on today', () => {
    const current = { date: '2026-06-03', startTime: '14:00', endTime: '16:00' }
    assert.deepEqual(applyStart(current, '23:00'), {
      date: '2026-06-03',
      startTime: '23:00',
      endTime: '01:00',
    })
    const now = at('2026-06-01T14:30:00Z')
    const repaired = applyDate({ date: '2026-06-02', startTime: '10:00', endTime: '12:00' }, '2026-06-01', now)
    assert.deepEqual(repaired, { date: '2026-06-01', startTime: '23:00', endTime: '01:00' })
    assert.equal(scheduleError(repaired, now), null)
  })

  it('rolls today forward when the only future start is after midnight', () => {
    const now = at('2026-06-01T15:10:00Z')
    const repaired = repairIfPast({ date: '2026-06-01', startTime: '22:00', endTime: '23:30' }, now)
    assert.equal(repaired.date, '2026-06-02')
    assert.equal(repaired.startTime, '00:00')
    assert.equal(repaired.endTime, '01:30')
    assert.equal(scheduleError(repaired, now), null)
  })
})

describe('formatWhen', () => {
  it('marks an end that is not after the start as the next day', () => {
    assert.equal(formatWhen('2026-06-04', '23:00-01:00'), '2026-06-04 23:00-次日01:00')
    assert.equal(formatWhen('2026-06-04', '15:20-16:50'), '2026-06-04 15:20-16:50')
  })
})
