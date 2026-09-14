import { Header } from './components/Header'
import { StatusBadge } from './components/StatusBadge'
import { RulCard } from './components/RulCard'
import { RiskPanel } from './components/RiskPanel'
import { RiskFactorList } from './components/RiskFactorList'
import { UnityDigitalTwin } from './components/UnityDigitalTwin'
import { samplePrediction } from './mock/samplePrediction'
import './App.css'

function App() {
  const prediction = samplePrediction

  return (
    <div className="dashboard">
      <Header prediction={prediction} />

      <div className="dashboard-status-row">
        <StatusBadge status={prediction.status} />
      </div>

      <UnityDigitalTwin />

      <main className="dashboard-grid">
        <RulCard hours={prediction.rul.hours} />
        <RiskPanel risk={prediction.risk} />
        <RiskFactorList
          factors={prediction.top_risk_factors}
          explanationModel={prediction.explanation_model}
        />
      </main>
    </div>
  )
}

export default App
