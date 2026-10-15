import type { PredictionConnectionState } from '../hooks/usePredictionStream'
import type { PredictionSourceMode } from '../config/predictionSource'
import type { Prediction } from '../types/prediction'

export function unityEnvelope(prediction: Prediction, receivedAt: Date, sourceMode: PredictionSourceMode, connectionState: PredictionConnectionState) {
  if (!Number.isFinite(receivedAt.getTime())) throw new Error('예측 수신 시각이 올바르지 않습니다.')
  return JSON.stringify({ prediction, received_at_unix_ms: receivedAt.getTime(), source_mode: sourceMode, connection_state: connectionState })
}
