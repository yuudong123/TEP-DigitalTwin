import type { RiskEntry, RiskHorizon } from '../types/prediction'

const HORIZON_LABEL: Record<RiskHorizon, string> = {
  failure_within_4h: '4시간 이내',
  failure_within_2h: '2시간 이내',
  failure_within_1h: '1시간 이내',
}

// prediction_schema.json 상 risk의 키 순서를 그대로 사용
const HORIZON_ORDER: RiskHorizon[] = [
  'failure_within_4h',
  'failure_within_2h',
  'failure_within_1h',
]

interface RiskPanelProps {
  risk: Record<RiskHorizon, RiskEntry>
}

export function RiskPanel({ risk }: RiskPanelProps) {
  return (
    <section className="card risk-panel">
      <h2>고장 위험 (Risk Score)</h2>
      <div className="risk-grid">
        {HORIZON_ORDER.map((horizon) => {
          const entry = risk[horizon]
          const scorePercent = Math.min(entry.score, 1) * 100
          const thresholdPercent = Math.min(entry.threshold, 1) * 100

          return (
            <div
              key={horizon}
              className={`risk-item${entry.alert ? ' risk-item--alert' : ''}`}
            >
              <span className="risk-label">{HORIZON_LABEL[horizon]}</span>
              <span className="risk-score">{(entry.score * 100).toFixed(1)}%</span>

              <div className="risk-bar">
                <div className="risk-bar__fill" style={{ width: `${scorePercent}%` }} />
                <div
                  className="risk-bar__threshold"
                  style={{ left: `${thresholdPercent}%` }}
                />
              </div>

              <span className="risk-threshold">
                threshold {(entry.threshold * 100).toFixed(1)}%
              </span>
              {entry.alert && <span className="risk-alert-flag">ALERT</span>}
            </div>
          )
        })}
      </div>
    </section>
  )
}
