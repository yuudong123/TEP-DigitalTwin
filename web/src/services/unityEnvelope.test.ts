import { describe, expect, it } from 'vitest'
import { unityEnvelope } from './unityEnvelope'
import { samplePrediction } from '../mock/samplePrediction'

describe('Unity 수신 정보', () => {
  it('오래된 서버 수신 시각을 조회 시각으로 덮어쓰지 않는다', () => {
    const receivedAt = new Date('2026-09-30T08:24:13Z')
    const envelope = JSON.parse(unityEnvelope(samplePrediction, receivedAt, 'api', 'stale'))
    expect(envelope.received_at_unix_ms).toBe(receivedAt.getTime())
    expect(envelope.connection_state).toBe('stale')
    expect(envelope.prediction).toEqual(samplePrediction)
  })
  it('연결 오류와 명시적 모의 모드를 그대로 전달한다', () => {
    const receivedAt = new Date()
    expect(JSON.parse(unityEnvelope(samplePrediction, receivedAt, 'api', 'error')).connection_state).toBe('error')
    expect(JSON.parse(unityEnvelope(samplePrediction, receivedAt, 'mock', 'mock')).source_mode).toBe('mock')
  })
  it('누락된 수신 시각은 거부한다', () => {
    expect(() => unityEnvelope(samplePrediction, new Date(NaN), 'api', 'connected')).toThrow()
  })
})
