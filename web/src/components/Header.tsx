import type { PredictionSourceMode } from '../config/predictionSource'
import type { Prediction } from '../types/prediction'
import { trajectoryLabel } from '../config/koreanUi'

interface HeaderProps {
  prediction: Prediction
  sourceMode: PredictionSourceMode
}

export function Header({ prediction, sourceMode }: HeaderProps) {
  return (
    <header className="dashboard-header">
      <div>
        <h1>TEP 공정 디지털트윈</h1>
        <p className="dashboard-subtitle">
          예지보전 모니터링 ({sourceMode === 'mock' ? '모의 데이터' : 'API 데이터'})
        </p>
      </div>
      <dl className="dashboard-meta">
        <div>
          <dt>재생 데이터</dt>
          <dd>{trajectoryLabel(prediction.trajectory_key)}</dd>
        </div>
        <div>
          <dt>모델 버전</dt>
          <dd>{prediction.model_version}</dd>
        </div>
        <div>
          <dt>공정 경과시간</dt>
          <dd>{prediction.timestamp_hours.toFixed(2)} 시간</dd>
        </div>
      </dl>
    </header>
  )
}
