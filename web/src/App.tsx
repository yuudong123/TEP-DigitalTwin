import { Header } from './components/Header'
import { StatusBadge } from './components/StatusBadge'
import { RulCard } from './components/RulCard'
import { RiskPanel } from './components/RiskPanel'
import { RiskFactorList } from './components/RiskFactorList'
import { UnityDigitalTwin } from './components/UnityDigitalTwin'
import { StreamControls } from './components/StreamControls'
import { usePredictionStream } from './hooks/usePredictionStream'
import './App.css'

function App() {
  const stream = usePredictionStream()
  const { prediction } = stream

  return (
    <div className="dashboard">
      {prediction ? (
        <>
          <Header prediction={prediction} sourceMode={stream.mode} />
          <div className="dashboard-status-row">
            <StatusBadge status={prediction.status} />
          </div>
        </>
      ) : (
        <header className="dashboard-header">
          <div>
            <h1>TEP Digital Twin</h1>
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

      {prediction ? (
        <>
          <UnityDigitalTwin prediction={prediction} />

          <main className="dashboard-grid">
            <RulCard hours={prediction.rul.hours} />
            <RiskPanel risk={prediction.risk} />
            <RiskFactorList
              factors={prediction.top_risk_factors}
              explanationModel={prediction.explanation_model}
            />
          </main>
        </>
      ) : (
        <section className="prediction-empty" aria-live="polite">
          <strong>예측 데이터를 기다리는 중입니다.</strong>
          <span>API가 연결되면 대시보드와 Unity 화면이 자동으로 표시됩니다.</span>
        </section>
      )}
    </div>
  )
}

export default App
