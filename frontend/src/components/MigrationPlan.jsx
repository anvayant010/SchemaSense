import React from 'react'
import './MigrationPlan.css'

export default function MigrationPlan({ plan, risk }) {
  if (!plan) return null
  return (
    <div className="card migration-plan">
      <div className="card-title">Migration Plan</div>

      <div className="plan-section">
        <div className="plan-section__label">Creation order</div>
        <div className="plan-steps">
          {plan.table_creation_order?.map((t, i) => (
            <div key={t} className="plan-step">
              <span className="plan-step__num">{i + 1}</span>
              <span className="plan-step__name mono">{t}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="plan-section">
        <div className="plan-section__label">Steps</div>
        <div className="plan-constraints">
          {plan.constraint_steps?.map((s, i) => (
            <div key={i} className="plan-constraint">
              <span className="plan-constraint__dot">◦</span>
              <span>{s}</span>
            </div>
          ))}
          {plan.index_steps?.filter(s => s !== 'No indexes defined').map((s, i) => (
            <div key={i} className="plan-constraint">
              <span className="plan-constraint__dot">◦</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>

      {risk?.risk_factors?.length > 0 && (
        <div className="plan-section">
          <div className="plan-section__label">Risk factors</div>
          {risk.risk_factors.map((f, i) => (
            <div key={i} className="plan-risk">{f}</div>
          ))}
        </div>
      )}
    </div>
  )
}