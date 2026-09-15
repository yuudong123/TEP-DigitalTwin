import type { RiskFactor, RiskHorizon } from '../types/prediction'

interface RiskFactorListProps {
  factors: RiskFactor[]
  explanationModel: RiskHorizon
}

export function RiskFactorList({ factors, explanationModel }: RiskFactorListProps) {
  const maxAbsShap = Math.max(...factors.map((factor) => Math.abs(factor.shap_value)), 1e-6)

  return (
    <section className="card risk-factor-list">
      <h2>주요 위험 요인 (SHAP)</h2>
      <p className="risk-factor-source">설명 대상 모델: {explanationModel}</p>
      <ol>
        {factors.map((factor) => (
          <li key={factor.rank}>
            <div className="risk-factor-name">
              <span className="risk-factor-rank">#{factor.rank}</span>
              <span>{factor.source_feature}</span>
              <span className="risk-factor-transform">
                {factor.transform}
                {factor.window_minutes != null ? ` (${factor.window_minutes}m)` : ''}
              </span>
            </div>
            <div className="risk-factor-bar">
              <div
                className="risk-factor-bar__fill"
                style={{ width: `${(Math.abs(factor.shap_value) / maxAbsShap) * 100}%` }}
              />
            </div>
            <span className="risk-factor-value">{factor.shap_value.toFixed(3)}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
