import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { ApiError } from './envelope.ts'
import { formatCooldownMessage, messageFor } from './errors.ts'

describe('formatCooldownMessage', () => {
  it('includes the Shanghai calendar date', () => {
    const text = formatCooldownMessage('2026-11-01T10:00:00+08:00')
    assert.match(text, /每月仅可修改一次/)
    assert.match(text, /2026/)
    assert.match(text, /11/)
    assert.match(text, /后修改/)
  })
})

describe('messageFor', () => {
  it('maps incomplete profile and cooldown payloads', () => {
    assert.equal(messageFor(new ApiError(40001, 'raw')), '资料未完善，请先完善资料')
    assert.equal(messageFor(new ApiError(40002, '时长至少 30 分钟')), '时长至少 30 分钟')
    const cooldown = messageFor(
      new ApiError(40301, 'raw', { nextEditableAt: '2026-02-15T10:00:00+08:00' }),
    )
    assert.match(cooldown, /2026/)
    assert.match(cooldown, /2/)
  })
})
