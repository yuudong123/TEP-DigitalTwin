export type PredictionSourceMode = 'mock' | 'api'

function positiveNumber(value: string | undefined, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function sourceMode(value: string | undefined): PredictionSourceMode {
  return value?.toLowerCase() === 'api' ? 'api' : 'mock'
}

export const predictionSourceConfig = {
  mode: sourceMode(import.meta.env.VITE_PREDICTION_SOURCE),
  apiUrl:
    import.meta.env.VITE_PREDICTION_API_URL?.trim() ||
    'http://localhost:8000/api/predictions/latest',
  pollIntervalMs: positiveNumber(import.meta.env.VITE_PREDICTION_POLL_MS, 2_000),
  timeoutMs: positiveNumber(import.meta.env.VITE_PREDICTION_TIMEOUT_MS, 5_000),
} as const
