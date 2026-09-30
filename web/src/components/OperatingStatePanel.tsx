import { useEffect, useState } from 'react'

interface StateEvent { status: string; drifted_feature_ratio: number; retraining_requested: boolean }

export function OperatingStatePanel({ trajectoryKey }: { trajectoryKey: string }) {
  const [event, setEvent] = useState<StateEvent | null>(null)
  const [receivedAt, setReceivedAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    let pending = false
    const refresh = async () => {
      if (pending) return
      pending = true
      try {
        const response = await fetch(`/v1/monitoring/latest?trajectory_key=${encodeURIComponent(trajectoryKey)}`,
          { cache: 'no-store', signal: AbortSignal.timeout(5000) })
        if (!active) return
        if (response.status === 404) { setEvent(null); setError(null); return }
        if (!response.ok) throw new Error(`Monitor API ${response.status}`)
        const data = await response.json()
        if (!active) return
        if (typeof data.event?.status !== 'string' || !Number.isFinite(data.event?.drifted_feature_ratio)
          || typeof data.event?.retraining_requested !== 'boolean') throw new Error('Monitor 응답 형식 오류')
        setEvent(data.event); setReceivedAt(data.received_at); setError(null)
      } catch (err) { if (active) setError(String(err)) }
      finally { pending = false }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 5000)
    return () => { active = false; window.clearInterval(timer) }
  }, [trajectoryKey])
  return <section className="stream-controls" aria-label="운전상태·열화 모니터링">
    <div className="stream-state">
      <strong>운전상태·열화 변화 · {event?.status ?? '판정 준비 중'}</strong>
      {event && <span>변화 변수 비율 {(event.drifted_feature_ratio * 100).toFixed(2)}% · 수신 {receivedAt}</span>}
      <small>운영 Data Drift·오탐률이 아닌 공정 변화 신호예요. 자동 재학습은 보류 상태입니다.</small>
      {event?.retraining_requested && <span role="alert">설정 확인 필요: 재학습 요청 감지</span>}
      {error && <span role="alert">{error}</span>}
    </div>
  </section>
}
