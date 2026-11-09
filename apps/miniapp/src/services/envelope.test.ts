import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { ApiError, coerceEnvelope, shouldRetry, unwrap } from './envelope.ts'

describe('unwrap', () => {
  it('returns data when code is 0', () => {
    assert.deepEqual(unwrap({ code: 0, message: 'success', data: { list: [] } }), { list: [] })
  })

  it('throws ApiError for a business code', () => {
    assert.throws(
      () => unwrap({ code: 401, message: '缺少或不可信的微信身份', data: null }),
      (error: unknown) => error instanceof ApiError && error.code === 401,
    )
  })
})

describe('coerceEnvelope', () => {
  it('parses a string body the way some runtimes return JSON', () => {
    const body = coerceEnvelope<{ ok: boolean }>('{"code":0,"message":"success","data":{"ok":true}}')
    assert.deepEqual(unwrap(body), { ok: true })
  })

  it('rejects a non-envelope payload', () => {
    assert.throws(() => coerceEnvelope('not-json'), (error: unknown) => error instanceof ApiError)
    assert.throws(() => coerceEnvelope({ message: 'missing code' }), (error: unknown) => error instanceof ApiError)
  })
})

describe('shouldRetry', () => {
  it('retries transport failures and database warmup', () => {
    assert.equal(shouldRetry(null, 0), true)
    assert.equal(shouldRetry(50301, 1), true)
    assert.equal(shouldRetry(401, 0), false)
    assert.equal(shouldRetry(50301, 2), false)
  })
})
