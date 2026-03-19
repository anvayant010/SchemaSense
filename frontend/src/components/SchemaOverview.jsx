import React from 'react'
import './SchemaOverview.css'

const RISK_COLOR    = { LOW: 'green', MEDIUM: 'amber', HIGH: 'red' }
const QUALITY_COLOR = { excellent: 'green', good: 'blue', fair: 'amber', poor: 'red' }

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat__value">{value}</span>
      <span className="stat__label">{label}</span>
    </div>
  )
}

export default function SchemaOverview({ result }) {
  const s = result.schema_summary || {}
  const q = result.quality || {}
  const r = result.migration_risk || {}
  const c = result.complexity || {}

  const riskColor = RISK_COLOR[r.risk_level] || 'text-muted'
  const qualColor = QUALITY_COLOR[q.quality_label] || 'text-muted'

  return (
    <div className="card schema-overview">
      <div className="card-title">Schema Overview</div>

      <div className="stats-grid">
        <Stat label="Tables"  value={s.tables}  />
        <Stat label="Columns" value={s.columns} />
        <Stat label="PKs"     value={s.pks}     />
        <Stat label="FKs"     value={s.fks}     />
      </div>

      <div className="overview-row">
        <span className="overview-label">Quality</span>
        <span className={`overview-value overview-value--${qualColor}`}>
          {q.quality_score}/10
          <span className="overview-tag">{q.quality_label}</span>
        </span>
      </div>

      <div className="overview-row">
        <span className="overview-label">Complexity</span>
        <span className="overview-value">
          {c.complexity_score}
          <span className="overview-tag">{c.complexity_label}</span>
        </span>
      </div>

      <div className="overview-row">
        <span className="overview-label">Migration risk</span>
        <span className={`overview-value overview-value--${riskColor}`}>
          {r.risk_level}
          <span className="overview-tag">{r.risk_score?.toFixed(1)}</span>
        </span>
      </div>

      {q.fk_without_index?.length > 0 && (
        <div className="overview-warning">
          ⚠ {q.fk_without_index.length} FK column{q.fk_without_index.length > 1 ? 's' : ''} missing index
        </div>
      )}

      {q.tables_without_pk?.length > 0 && (
        <div className="overview-warning">
          ⚠ Tables without PK: {q.tables_without_pk.join(', ')}
        </div>
      )}
    </div>
  )
}