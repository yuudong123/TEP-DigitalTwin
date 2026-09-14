interface RulCardProps {
  hours: number
}

export function RulCard({ hours }: RulCardProps) {
  return (
    <section className="card rul-card">
      <h2>잔여수명 (RUL)</h2>
      <p className="rul-value">
        {hours.toFixed(2)}
        <span className="rul-unit">h</span>
      </p>
    </section>
  )
}
