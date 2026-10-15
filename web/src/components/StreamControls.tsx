import type { PredictionSourceMode } from '../config/predictionSource'
import type { PredictionConnectionState } from '../hooks/usePredictionStream'

interface StreamControlsProps {
  mode: PredictionSourceMode
  connectionState: PredictionConnectionState
  errorMessage: string | null
  currentIndex: number
  totalSnapshots: number | null
  isPlaying: boolean
  lastReceivedAt: Date | null
  onToggle: () => void
  onRestart: () => void
}

export function StreamControls({
  mode,
  connectionState,
  errorMessage,
  currentIndex,
  totalSnapshots,
  isPlaying,
  lastReceivedAt,
  onToggle,
  onRestart,
}: StreamControlsProps) {
  const isHealthy = connectionState === 'mock' || connectionState === 'connected'
  const stateLabel = {
    mock: '모의 데이터 재생',
    connecting: '서버 연결 중',
    connected: '실시간 연결',
    stale: '예측 갱신 지연',
    error: '연결 오류',
    paused: '화면 갱신 일시정지',
  }[connectionState]

  return (
    <section className={`stream-controls stream-controls--${connectionState}`} aria-label="예측 데이터 연결 제어">
      <div className="stream-state">
        <span className={`stream-state__dot${isHealthy ? ' stream-state__dot--live' : ''}`} />
        <strong>{stateLabel}</strong>
        <span>
          {mode === 'mock' && totalSnapshots ? `${currentIndex + 1}/${totalSnapshots} · ` : ''}
          최근{' '}
          {lastReceivedAt ? (
            <time dateTime={lastReceivedAt.toISOString()}>{lastReceivedAt.toLocaleTimeString('ko-KR')}</time>
          ) : (
            '대기 중'
          )}
        </span>
        {errorMessage && <span className="stream-state__error">{errorMessage}</span>}
      </div>
      <div className="stream-actions">
        <button type="button" onClick={onToggle}>
          {isPlaying ? '일시정지' : '재생'}
        </button>
        <button type="button" className="button-secondary" onClick={onRestart}>
          {mode === 'mock' ? '처음부터' : '다시 연결'}
        </button>
      </div>
    </section>
  )
}
