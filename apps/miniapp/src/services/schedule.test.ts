import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  DATE_WINDOW_DAYS,
  addDays,
  applyDate,
  applyStart,
  defaultSchedule,
  earliestEnd,
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
  it('uses the next whole hour and a two-hour end inside the day', () => {
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

  it('lifts a next hour before 07:00 to 07:00 the same day', () => {
    // 05:30 Shanghai.
    assert.deepEqual(defaultSchedule(at('2026-06-01T21:30:00Z')), {
      date: '2026-06-02',
      startTime: '07:00',
      endTime: '09:00',
    })
    // 00:30 Shanghai, next hour 01:00.
    assert.deepEqual(defaultSchedule(at('2026-05-31T16:30:00Z')), {
      date: '2026-06-01',
      startTime: '07:00',
      endTime: '09:00',
    })
    // 06:30 Shanghai, next hour is already 07:00.
    assert.deepEqual(defaultSchedule(at('2026-06-01T22:30:00Z')), {
      date: '2026-06-02',
      startTime: '07:00',
      endTime: '09:00',
    })
  })

  it('clamps the end at 22:00 when two hours would pass closing', () => {
    // 20:30 Shanghai → start 21:00, end min(23:00, 22:00).
    const now = at('2026-06-01T12:30:00Z')
    assert.deepEqual(defaultSchedule(now), {
      date: '2026-06-01',
      startTime: '21:00',
      endTime: '22:00',
    })
    assert.equal(scheduleError(defaultSchedule(now), now), null)
  })

  it('rolls to tomorrow 07:00–09:00 when today cannot fit 30 minutes', () => {
    // 21:31 Shanghai → next hour 22:00, later than 21:30.
    const after = at('2026-06-01T13:31:00Z')
    assert.deepEqual(defaultSchedule(after), {
      date: '2026-06-02',
      startTime: '07:00',
      endTime: '09:00',
    })
    // 21:30 exactly → next hour 22:00.
    assert.deepEqual(defaultSchedule(at('2026-06-01T13:30:00Z')), {
      date: '2026-06-02',
      startTime: '07:00',
      endTime: '09:00',
    })
  })

  it('near midnight opens at 07:00 the next morning', () => {
    // 23:10 Shanghai → next hour 00:00, which is before 07:00 that next date.
    const late = at('2026-06-01T15:10:00Z')
    assert.deepEqual(defaultSchedule(late), {
      date: '2026-06-02',
      startTime: '07:00',
      endTime: '09:00',
    })
    assert.equal(scheduleError(defaultSchedule(late), late), null)
    // 23:00 exactly and 22:00 exactly also leave no same-day slot.
    assert.equal(defaultSchedule(at('2026-06-01T15:00:00Z')).date, '2026-06-02')
    assert.deepEqual(defaultSchedule(at('2026-06-01T14:00:00Z')), {
      date: '2026-06-02',
      startTime: '07:00',
      endTime: '09:00',
    })
  })
})

describe('shiftEnd', () => {
  it('keeps the duration and clamps the end at 22:00', () => {
    assert.equal(shiftEnd('14:00', '16:30', '18:00'), '20:30')
    assert.equal(shiftEnd('14:00', '16:00', '21:00'), '22:00')
    assert.equal(shiftEnd('19:00', '21:00', '20:30'), '22:00')
    assert.equal(shiftEnd('14:00', '16:00', '21:30'), '22:00')
  })

  it('falls back to two hours when the previous duration is not allowed', () => {
    assert.equal(shiftEnd('10:00', '20:00', '11:00'), '13:00')
    assert.equal(shiftEnd('10:00', '10:10', '12:00'), '14:00')
  })
})

describe('scheduleError', () => {
  const now = at('2026-06-01T05:06:00Z')

  it('rejects a past start, a short or long window, hours outside 07:00–22:00, and a far date', () => {
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
      scheduleError({ date: '2026-06-03', startTime: '06:30', endTime: '08:30' }, now),
      '开始时间不能早于 07:00',
    )
    assert.equal(
      scheduleError({ date: '2026-06-03', startTime: '20:00', endTime: '22:30' }, now),
      '结束时间不能晚于 22:00',
    )
    assert.equal(
      scheduleError({ date: '2026-06-03', startTime: '21:00', endTime: '01:00' }, now),
      '结束时间需要晚于开始时间',
    )
    assert.equal(
      scheduleError({ date: '2026-06-03', startTime: '21:40', endTime: '22:00' }, now),
      '时长至少 30 分钟',
    )
    const tooLate = addDays('2026-06-01', DATE_WINDOW_DAYS + 1)
    assert.equal(
      scheduleError({ date: tooLate, startTime: '10:00', endTime: '12:00' }, now),
      '开始日期需在今天起 30 天内',
    )
  })

  it('accepts 30 minutes, 8 hours, the closing edge, and the last window day', () => {
    assert.equal(scheduleError({ date: '2026-06-03', startTime: '15:20', endTime: '15:50' }, now), null)
    assert.equal(scheduleError({ date: '2026-06-03', startTime: '07:00', endTime: '15:00' }, now), null)
    assert.equal(scheduleError({ date: '2026-06-03', startTime: '07:00', endTime: '09:00' }, now), null)
    assert.equal(scheduleError({ date: '2026-06-03', startTime: '21:30', endTime: '22:00' }, now), null)
    const last = addDays('2026-06-01', DATE_WINDOW_DAYS)
    assert.equal(scheduleError({ date: last, startTime: '21:00', endTime: '22:00' }, now), null)
    assert.equal(scheduleError({ date: '2026-06-01', startTime: '14:00', endTime: '16:00' }, now), null)
  })
})

describe('applyStart and applyDate', () => {
  it('shifts the end with the start and stops at 22:00', () => {
    const current = { date: '2026-06-03', startTime: '14:00', endTime: '16:00' }
    assert.deepEqual(applyStart(current, '18:00'), {
      date: '2026-06-03',
      startTime: '18:00',
      endTime: '20:00',
    })
    assert.deepEqual(applyStart(current, '21:00'), {
      date: '2026-06-03',
      startTime: '21:00',
      endTime: '22:00',
    })
    assert.equal(earliestEnd('21:30'), '22:00')
    assert.equal(earliestEnd('14:00'), '14:30')
  })

  it('repairs a past selection on today using the playable-hour default', () => {
    const now = at('2026-06-01T14:30:00Z')
    const repaired = applyDate({ date: '2026-06-02', startTime: '10:00', endTime: '12:00' }, '2026-06-01', now)
    assert.deepEqual(repaired, { date: '2026-06-02', startTime: '07:00', endTime: '09:00' })
    assert.equal(scheduleError(repaired, now), null)
  })

  it('rolls a late today selection to the next morning', () => {
    const now = at('2026-06-01T15:10:00Z')
    const repaired = repairIfPast({ date: '2026-06-01', startTime: '21:00', endTime: '22:00' }, now)
    assert.deepEqual(repaired, { date: '2026-06-02', startTime: '07:00', endTime: '08:00' })
    assert.equal(scheduleError(repaired, now), null)
  })
})

describe('formatWhen', () => {
  it('prints the clocks on the start date without a next-day mark', () => {
    assert.equal(formatWhen('2026-06-04', '15:20-16:50'), '2026-06-04 15:20-16:50')
    assert.equal(formatWhen('2026-06-04', '23:00-01:00'), '2026-06-04 23:00-01:00')
  })
})
