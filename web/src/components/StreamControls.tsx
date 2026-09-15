interface StreamControlsProps {
  currentIndex: number
  totalSnapshots: number
  isPlaying: boolean
  lastReceivedAt: Date
  onToggle: () => void
  onRestart: () => void
}

export function StreamControls({
  currentIndex,
  totalSnapshots,
  isPlaying,
  lastReceivedAt,
  onToggle,
  onRestart,
}: StreamControlsProps) {
  return (
    <section className="stream-controls" aria-label="모의 예측 스트림 제어">
      <div className="stream-state">
        <span className={`stream-state__dot${isPlaying ? ' stream-state__dot--live' : ''}`} />
        <strong>{isPlaying ? 'LIVE MOCK' : 'PAUSED'}</strong>
        <span>
          {currentIndex + 1}/{totalSnapshots} · 마지막 갱신{' '}
          <time dateTime={lastReceivedAt.toISOString()}>{lastReceivedAt.toLocaleTimeString('ko-KR')}</time>
        </span>
      </div>
      <div className="stream-actions">
        <button type="button" onClick={onToggle}>
          {isPlaying ? '일시정지' : '재생'}
        </button>
        <button type="button" className="button-secondary" onClick={onRestart}>
          처음부터
        </button>
      </div>
    </section>
  )
}
