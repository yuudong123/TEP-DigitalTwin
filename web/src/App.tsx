import { Header } from './components/Header'
import { StatusBadge } from './components/StatusBadge'
import { RulCard } from './components/RulCard'
import { RiskPanel } from './components/RiskPanel'
import { RiskFactorList } from './components/RiskFactorList'
import { UnityDigitalTwin } from './components/UnityDigitalTwin'
import { StreamControls } from './components/StreamControls'
import { ReplayControls } from './components/ReplayControls'
import { OperatingStatePanel } from './components/OperatingStatePanel'
import { usePredictionStream } from './hooks/usePredictionStream'
import './App.css'

function App() {
  const stream = usePredictionStream()
  const { prediction } = stream

  return (
    <div className="dashboard">
      <div className="command-bar">
      {prediction ? (
        <>
          <Header prediction={prediction} sourceMode={stream.mode} />
        </>
      ) : (
        <header className="dashboard-header">
          <div>
            <h1>TEP 공정 디지털트윈</h1>
            <p className="dashboard-subtitle">예지보전 모니터링</p>
          </div>
        </header>
      )}

      <StreamControls
        mode={stream.mode}
        connectionState={stream.connectionState}
        errorMessage={stream.errorMessage}
        currentIndex={stream.currentIndex}
        totalSnapshots={stream.totalSnapshots}
        isPlaying={stream.isPlaying}
        lastReceivedAt={stream.lastReceivedAt}
        onToggle={stream.toggle}
        onRestart={stream.restart}
      />
      </div>

      {prediction ? (
        <>
          <section className="summary-grid" aria-label="핵심 공정 상태">
            <section className={`card status-summary status-summary--${prediction.status.toLowerCase()}`}>
              <h2>{stream.connectionState === 'connected' ? '공정 전체 상태' : '마지막 공정 판정'}</h2>
              <StatusBadge status={prediction.status} />
              <p>공정 전체 예측 · 설비별 고장 위치 아님</p>
            </section>
            <RulCard hours={prediction.rul.hours} />
            <RiskPanel risk={prediction.risk} />
          </section>
          <main className="console-grid">
            <UnityDigitalTwin prediction={prediction} receivedAt={stream.lastReceivedAt!} sourceMode={stream.mode} connectionState={stream.connectionState} />
            <aside className="insight-column" aria-label="예측 해석과 운전상태">
            <RiskFactorList
              factors={prediction.top_risk_factors}
              explanationModel={prediction.explanation_model}
            />
            {stream.mode === 'api' && <OperatingStatePanel key={prediction.trajectory_key} trajectoryKey={prediction.trajectory_key} />}
            </aside>
          </main>
        </>
      ) : (
        <section className="prediction-empty" aria-live="polite">
          <strong>예측 데이터를 기다리는 중입니다.</strong>
          <span>API가 연결되면 대시보드와 Unity 화면이 자동으로 표시됩니다.</span>
        </section>
      )}
      {stream.mode === 'api' && <ReplayControls />}
      <footer className="console-footer"><span>TEP 공정 관제 · 예측 모델 v1.0.0</span><span>공정 흐름을 표현한 모형 · 물리 시뮬레이터 아님</span></footer>
      <div className="viewport-notice" role="status">관제 화면을 표시할 공간이 부족해.<br />가로 1,000 × 세로 720 이상으로 창을 넓혀줘.</div>
    </div>
  )
}

export default App
