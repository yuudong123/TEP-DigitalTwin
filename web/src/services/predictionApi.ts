import type {
  Prediction,
  RiskEntry,
  RiskFactor,
  RiskHorizon,
  Status,
} from '../types/prediction'

const riskHorizons: readonly RiskHorizon[] = [
  'failure_within_4h',
  'failure_within_2h',
  'failure_within_1h',
]
const statuses: readonly Status[] = ['NORMAL', 'CAUTION', 'WARNING', 'CRITICAL']

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isRiskEntry(value: unknown): value is RiskEntry {
  return (
    isRecord(value) &&
    isFiniteNumber(value.score) &&
    isFiniteNumber(value.threshold) &&
    typeof value.alert === 'boolean'
  )
}

function isRiskFactor(value: unknown): value is RiskFactor {
  return (
    isRecord(value) &&
    Number.isInteger(value.rank) &&
    typeof value.feature === 'string' &&
    typeof value.source_feature === 'string' &&
    typeof value.transform === 'string' &&
    (value.window_minutes === null || isFiniteNumber(value.window_minutes)) &&
    isFiniteNumber(value.shap_value)
  )
}

export function isPrediction(value: unknown): value is Prediction {
  if (!isRecord(value) || !isRecord(value.rul) || !isRecord(value.risk)) return false
  const risk = value.risk

  return (
    typeof value.schema_version === 'string' &&
    typeof value.model_version === 'string' &&
    typeof value.trajectory_key === 'string' &&
    isFiniteNumber(value.timestamp_hours) &&
    isFiniteNumber(value.rul.hours) &&
    riskHorizons.every((horizon) => isRiskEntry(risk[horizon])) &&
    typeof value.status === 'string' &&
    statuses.includes(value.status as Status) &&
    typeof value.explanation_model === 'string' &&
    riskHorizons.includes(value.explanation_model as RiskHorizon) &&
    Array.isArray(value.top_risk_factors) &&
    value.top_risk_factors.every(isRiskFactor)
  )
}

export async function fetchLatestPrediction(
  url: string,
  timeoutMs: number,
  signal?: AbortSignal,
): Promise<Prediction> {
  const timeoutController = new AbortController()
  const timeout = window.setTimeout(() => timeoutController.abort(), timeoutMs)
  const abort = () => timeoutController.abort()
  signal?.addEventListener('abort', abort, { once: true })

  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal: timeoutController.signal,
    })
    if (!response.ok) throw new Error(`API 응답 오류 (${response.status})`)

    const body: unknown = await response.json()
    if (!isPrediction(body)) throw new Error('API 응답이 Prediction 형식과 다릅니다.')
    return body
  } catch (error) {
    if (timeoutController.signal.aborted && !signal?.aborted) {
      throw new Error(`API 응답 시간이 ${timeoutMs}ms를 초과했습니다.`)
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
    signal?.removeEventListener('abort', abort)
  }
}
