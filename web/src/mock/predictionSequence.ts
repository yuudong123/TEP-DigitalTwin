import { samplePrediction } from './samplePrediction'
import type { Prediction, Status } from '../types/prediction'

const thresholds = {
  failure_within_4h: samplePrediction.risk.failure_within_4h.threshold,
  failure_within_2h: samplePrediction.risk.failure_within_2h.threshold,
  failure_within_1h: samplePrediction.risk.failure_within_1h.threshold,
}

function riskEntry(score: number, threshold: number) {
  return { score, threshold, alert: score >= threshold }
}

function snapshot(
  timestampHours: number,
  rulHours: number,
  status: Status,
  scores: [number, number, number],
): Prediction {
  return {
    ...samplePrediction,
    timestamp_hours: timestampHours,
    rul: { hours: rulHours },
    risk: {
      failure_within_4h: riskEntry(scores[0], thresholds.failure_within_4h),
      failure_within_2h: riskEntry(scores[1], thresholds.failure_within_2h),
      failure_within_1h: riskEntry(scores[2], thresholds.failure_within_1h),
    },
    status,
  }
}

export const predictionSequence: readonly Prediction[] = [
  snapshot(124, 7.8, 'NORMAL', [0.12, 0.08, 0.03]),
  snapshot(126, 4.1, 'CAUTION', [0.48, 0.36, 0.24]),
  snapshot(128, 1.85, 'WARNING', [0.74, 0.52, 0.45]),
  samplePrediction,
]
