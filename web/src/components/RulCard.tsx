interface RulCardProps {
  hours: number
}

export function RulCard({ hours }: RulCardProps) {
  return (
    <section className="card rul-card">
      <h2>예측 잔여수명</h2>
      <p className="rul-value">
        {hours.toFixed(2)}
        <span className="rul-unit">시간</span>
      </p>
      <p className="metric-caption">최근 예측 기준 · 공정 전체 잔여시간</p>
    </section>
  )
}
