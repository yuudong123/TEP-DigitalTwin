import { useEffect, useState } from 'react'

interface Trajectory { trajectory_key: string; row_count: string; raw_available: boolean }
interface Replay { status: string; sent: number; total?: number; trajectory_key?: string; error?: string;
  inference_caught_up?: boolean; prediction_timestamp_hours?: number | null; end_timestamp_hours?: number }

async function request(path: string, method = 'GET', body?: unknown) {
  const response = await fetch(`/v1/${path}`, {
    method, headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(5000), cache: 'no-store',
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail ?? `API 오류 ${response.status}`)
  return data
}

export function ReplayControls() {
  const [catalog, setCatalog] = useState<Trajectory[]>([])
  const [key, setKey] = useState('')
  const [interval, setIntervalValue] = useState(.1)
  const [replay, setReplay] = useState<Replay>({ status: '연결 중', sent: 0 })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    void request('trajectories').then((data) => {
      if (!active) return
      setCatalog(data.items)
      setKey(data.items.find((item: Trajectory) => item.raw_available)?.trajectory_key ?? '')
    }).catch((err) => { if (active) setError(String(err)) })
    let pending = false
    const refresh = async () => {
      if (pending) return
      pending = true
      try { const data = await request('replay'); if (active) setReplay(data) }
      catch (err) { if (active) setError(String(err)) }
      finally { pending = false }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  const command = async (action: string) => {
    setBusy(true)
    try {
      setReplay(await request(`replay/${action}`, 'POST', action === 'start'
        ? { trajectory_key: key, interval_seconds: interval } : undefined))
      setError(null)
    } catch (err) { setError(String(err)) }
    finally { setBusy(false) }
  }
  const active = ['running', 'paused', 'stopping'].includes(replay.status)
  const processing = ['completed', 'stopped'].includes(replay.status) && replay.inference_caught_up === false
  return <section className="stream-controls replay-controls" aria-label="실제 TEP 재생">
    <div className="stream-state">
      <strong>실제 CSV → Kafka 재생</strong>
      <label>Trajectory <select value={key} disabled={active || busy} onChange={(e) => setKey(e.target.value)}>
        {catalog.map((item) => <option key={item.trajectory_key} value={item.trajectory_key} disabled={!item.raw_available}>
          {item.trajectory_key}{item.raw_available ? '' : ' · 원본 없음'}
        </option>)}
      </select></label>
      <label>전송 간격(초) <input type="number" min=".01" max="10" step=".01" value={interval}
        disabled={active || busy} onChange={(e) => setIntervalValue(Number(e.target.value))} /></label>
      <span aria-live="polite">{replay.status} · {replay.sent}/{replay.total ?? '—'}
        {replay.trajectory_key ? ` · ${replay.trajectory_key}` : ''}</span>
      {processing && <span>센서 전송 종료 · 추론 처리 중 ({replay.prediction_timestamp_hours?.toFixed(2) ?? '준비'} h)</span>}
      <small>센서 시간은 3분 간격 그대로예요. 첫 20행은 예측 준비 구간입니다.</small>
      {(error || replay.error) && <span role="alert">{error ?? replay.error}</span>}
    </div>
    <div className="stream-actions">
      <button disabled={active || processing || busy || !key || !Number.isFinite(interval) || interval < .01 || interval > 10} onClick={() => void command('start')}>시작</button>
      <button disabled={!['running', 'paused'].includes(replay.status) || busy}
        onClick={() => void command(replay.status === 'paused' ? 'resume' : 'pause')}>
        {replay.status === 'paused' ? '이어 재생' : '재생 일시정지'}</button>
      <button disabled={!active || busy} onClick={() => void command('stop')}>중지</button>
    </div>
  </section>
}
