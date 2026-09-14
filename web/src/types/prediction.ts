/**
 * models/production/v1.0.0/prediction_schema.json 을 그대로 옮긴 타입.
 * 실제 FastAPI(13번) 연동 시 응답이 이 타입과 어긋나면 컴파일 에러로 드러난다.
 */

export type Status = 'NORMAL' | 'CAUTION' | 'WARNING' | 'CRITICAL'

export type RiskHorizon =
  | 'failure_within_4h'
  | 'failure_within_2h'
  | 'failure_within_1h'

export interface RiskEntry {
  score: number
  threshold: number
  alert: boolean
}

export interface RiskFactor {
  rank: number
  feature: string
  source_feature: string
  transform: string
  window_minutes: number | null
  shap_value: number
}

export interface Prediction {
  schema_version: string
  model_version: string
  trajectory_key: string
  timestamp_hours: number
  rul: {
    hours: number
  }
  risk: Record<RiskHorizon, RiskEntry>
  status: Status
  explanation_model: RiskHorizon
  top_risk_factors: RiskFactor[]
}
