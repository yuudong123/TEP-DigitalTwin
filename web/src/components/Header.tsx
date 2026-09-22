import type { PredictionSourceMode } from '../config/predictionSource'
import type { Prediction } from '../types/prediction'

interface HeaderProps {
  prediction: Prediction
  sourceMode: PredictionSourceMode
}

export function Header({ prediction, sourceMode }: HeaderProps) {
  return (
    <header className="dashboard-header">
      <div>
        <h1>TEP Digital Twin</h1>
        <p className="dashboard-subtitle">
          예지보전 모니터링 ({sourceMode === 'mock' ? '모의 데이터' : 'API 데이터'})
        </p>
      </div>
      <dl className="dashboard-meta">
        <div>
          <dt>Trajectory</dt>
          <dd>{prediction.trajectory_key}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{prediction.model_version}</dd>
        </div>
        <div>
          <dt>Time</dt>
          <dd>{prediction.timestamp_hours.toFixed(2)} h</dd>
        </div>
      </dl>
    </header>
  )
}
