import { useEffect, useState } from 'react'

interface StateEvent { status: string; drifted_feature_ratio: number; retraining_requested: boolean }
const statusLabels: Record<string, string> = { NORMAL: '정상', CAUTION: '주의', DRIFT: '변화 감지', CONFIRMED_DRIFT: '변화 확인', INSUFFICIENT_DATA: '판정 준비 중' }

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
        if (!response.ok) throw new Error(`상태 감지 서버 오류 (${response.status})`)
        const data = await response.json()
        if (!active) return
        if (typeof data.event?.status !== 'string' || !Number.isFinite(data.event?.drifted_feature_ratio)
          || typeof data.event?.retraining_requested !== 'boolean') throw new Error('상태 감지 응답 형식 오류')
        setEvent(data.event); setReceivedAt(data.received_at); setError(null)
      } catch (err) { if (active) setError(String(err)) }
      finally { pending = false }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 5000)
    return () => { active = false; window.clearInterval(timer) }
  }, [trajectoryKey])
  return <section className="card operating-state" aria-label="운전상태·열화 모니터링" data-monitor-status={event?.status ?? 'INSUFFICIENT_DATA'}>
    <div className="stream-state">
      <h2>운전상태·열화 변화</h2>
      <div className="monitor-reading"><strong>{event ? statusLabels[event.status] ?? '알 수 없는 상태' : '판정 준비 중'}</strong><span>{event ? `${(event.drifted_feature_ratio * 100).toFixed(2)}%` : '—'}</span></div>
      <small>변화 변수 비율 · 자동 재학습 꺼짐</small>
      {receivedAt && <time dateTime={receivedAt}>수신 {new Date(receivedAt).toLocaleTimeString('ko-KR', { hour12: false })}</time>}
      {event?.retraining_requested && <span role="alert">설정 확인 필요: 재학습 요청 감지</span>}
      {error && <span role="alert">{error}</span>}
    </div>
  </section>
}
