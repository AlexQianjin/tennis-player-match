import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { ERROR_CODES, ERROR_MESSAGES } from './errorCodes.ts'

describe('error codes', () => {
  it('has a message for every code', () => {
    for (const code of Object.values(ERROR_CODES)) {
      assert.equal(typeof ERROR_MESSAGES[code], 'string')
    }
  })

  it('keeps the warmup code used by the request layer', () => {
    assert.equal(ERROR_CODES.STARTING, 50301)
  })
})
