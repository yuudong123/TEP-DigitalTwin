import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchLatestPrediction, isPrediction } from './predictionApi'
import { samplePrediction } from '../mock/samplePrediction'

afterEach(() => vi.unstubAllGlobals())

describe('live prediction contract', () => {
  it('rejects invalid risk, negative RUL and rank', () => {
    expect(isPrediction(samplePrediction)).toBe(true)
    expect(isPrediction({ ...samplePrediction, rul: { hours: -1 } })).toBe(false)
    expect(isPrediction({ ...samplePrediction, schema_version: '9' })).toBe(false)
    const bad = structuredClone(samplePrediction)
    bad.risk.failure_within_1h.score = 2
    expect(isPrediction(bad)).toBe(false)
    bad.risk.failure_within_1h.score = .1
    bad.top_risk_factors[0].rank = 9
    expect(isPrediction(bad)).toBe(false)
  })

  it('keeps server receipt time; polling is not a new prediction', async () => {
    vi.stubGlobal('window', globalThis)
    const receipt = '2026-09-30T00:00:00+00:00'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(samplePrediction), {
      headers: { 'X-Prediction-Received-At': receipt },
    })))
    const result = await fetchLatestPrediction('/api/predictions/latest', 1000)
    expect(result.receivedAt.toISOString()).toBe('2026-09-30T00:00:00.000Z')
    expect(result.prediction).toEqual(samplePrediction)
  })

  it('fails explicitly on missing receipt or HTTP error', async () => {
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(samplePrediction))))
    await expect(fetchLatestPrediction('/api', 1000)).rejects.toThrow('수신 시각')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })))
    await expect(fetchLatestPrediction('/api', 1000)).rejects.toThrow('503')
  })
})
