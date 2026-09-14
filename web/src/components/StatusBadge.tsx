import type { Status } from '../types/prediction'

// docs/06-final-model.md §9 상태 판정 우선순위: CRITICAL > WARNING > CAUTION > NORMAL
const LABEL: Record<Status, string> = {
  NORMAL: '정상',
  CAUTION: '주의',
  WARNING: '경고',
  CRITICAL: '위험',
}

interface StatusBadgeProps {
  status: Status
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`status-badge status-badge--${status.toLowerCase()}`}>
      {LABEL[status]} · {status}
    </span>
  )
}
