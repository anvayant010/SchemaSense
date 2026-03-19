import React, { useState } from 'react'
import './DBScoreCard.css'

const VERDICT_CONFIG = {
  excellent: { label: 'Excellent', color: 'green' },
  good:      { label: 'Good',      color: 'blue'  },
  fair:      { label: 'Fair',      color: 'amber' },
  poor:      { label: 'Poor',      color: 'red'   },
}

const SCORE_BAR_COLOR = (pct) => {
  if (pct >= 90) return 'var(--green)'
  if (pct >= 75) return 'var(--blue)'
  if (pct >= 55) return 'var(--amber)'
  return 'var(--red)'
}

const DB_ICONS = {
  PostgreSQL: 'PG', MySQL: 'MY', MariaDB: 'MA', SQLite: 'SL',
  'SQL Server': 'SS', Oracle: 'OR', MongoDB: 'MG', CockroachDB: 'CR',
  Cassandra: 'CA', DynamoDB: 'DY', Redshift: 'RS', BigQuery: 'BQ',
}

function NoteItem({ note, type }) {
  return (
    <div className={`note-item note-item--${type}`}>
      <div className="note-item__location mono">
        {note.table !== '(global)' ? `${note.table}.${note.column}` : note.issue}
      </div>
      {note.table !== '(global)' && (
        <div className="note-item__issue">{note.issue}</div>
      )}
      <div className="note-item__suggestion">→ {note.suggestion}</div>
    </div>
  )
}

export default function DBScoreCard({ dbName, info, rank, style }) {
  const [expanded, setExpanded] = useState(false)

  const pct     = info.absolute_pct ?? 0
  const verdict = VERDICT_CONFIG[info.verdict] || VERDICT_CONFIG.fair
  const expl    = info.explanation || {}
  const warnings = expl.migration_warnings || []
  const notes    = expl.column_notes || []
  const hasDetails = warnings.filter(w => !w.toLowerCase().includes('no major')).length > 0
    || notes.length > 0

  const errorNotes = notes.filter(n => n.severity === 'error')
  const warnNotes  = notes.filter(n => n.severity === 'warning' && n.table !== '(global)')
  const infoNotes  = notes.filter(n => n.severity === 'info')

  return (
    <div className={`score-card score-card--${verdict.color} fade-up`} style={style}>
      <div
        className="score-card__header"
        onClick={() => hasDetails && setExpanded(e => !e)}
        style={{ cursor: hasDetails ? 'pointer' : 'default' }}
      >
        <div className="score-card__left">
          <span className="score-card__rank">#{rank}</span>
          <div className={`score-card__icon score-card__icon--${verdict.color}`}>
            {DB_ICONS[dbName] || dbName.slice(0,2).toUpperCase()}
          </div>
          <span className="score-card__name">{dbName}</span>
        </div>

        <div className="score-card__right">
          <div className="score-card__bar-wrap">
            <div className="score-bar">
              <div
                className="score-bar__fill"
                style={{ width: `${pct}%`, background: SCORE_BAR_COLOR(pct) }}
              />
            </div>
            <span className="score-card__pct">{pct}%</span>
          </div>
          <span className={`badge badge--${verdict.color}`}>{verdict.label}</span>
          {hasDetails && (
            <span className="score-card__chevron">{expanded ? '▴' : '▾'}</span>
          )}
        </div>
      </div>

      {expanded && (
        <div className="score-card__body">

          <div className="score-breakdown">
            <div className="score-breakdown__item">
              <span className="score-breakdown__label">Types</span>
              <span className="score-breakdown__val mono">{(expl.type_support_frac * 100).toFixed(0)}%</span>
            </div>
            <div className="score-breakdown__item">
              <span className="score-breakdown__label">Constraints</span>
              <span className="score-breakdown__val mono">{(expl.constraint_frac * 100).toFixed(0)}%</span>
            </div>
            <div className="score-breakdown__item">
              <span className="score-breakdown__label">Features</span>
              <span className="score-breakdown__val mono">{(expl.special_frac * 100).toFixed(0)}%</span>
            </div>
            {expl.type_violations > 0 && (
              <div className="score-breakdown__item">
                <span className="score-breakdown__label">Violations</span>
                <span className="score-breakdown__val mono score-breakdown__val--red">{expl.type_violations}</span>
              </div>
            )}
          </div>

          {warnings.filter(w => !w.toLowerCase().includes('no major')).length > 0 && (
            <div className="score-card__section">
              <div className="score-card__section-title">Warnings</div>
              {warnings.filter(w => !w.toLowerCase().includes('no major')).map((w, i) => (
                <div key={i} className="warning-item">
                  <span className="warning-item__dot">⚠</span>
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}

          {errorNotes.length > 0 && (
            <div className="score-card__section">
              <div className="score-card__section-title">Errors</div>
              {errorNotes.map((n, i) => <NoteItem key={i} note={n} type="error" />)}
            </div>
          )}

          {warnNotes.length > 0 && (
            <div className="score-card__section">
              <div className="score-card__section-title">Column notes</div>
              {warnNotes.map((n, i) => <NoteItem key={i} note={n} type="warning" />)}
            </div>
          )}

          {infoNotes.length > 0 && (
            <div className="score-card__section">
              {infoNotes.map((n, i) => <NoteItem key={i} note={n} type="info" />)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}