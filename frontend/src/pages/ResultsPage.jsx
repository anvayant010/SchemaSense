import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import DBScoreCard from '../components/DBScoreCard.jsx'
import SchemaOverview from '../components/SchemaOverview.jsx'
import MigrationPlan from '../components/MigrationPlan.jsx'
import AIExplanation from '../components/AIExplanation.jsx'
import './ResultsPage.css'

export default function ResultsPage() {
  const [result, setResult] = useState(null)
  const [copied, setCopied] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const stored = sessionStorage.getItem('schemasense_result')
    if (!stored) { navigate('/'); return }
    setResult(JSON.parse(stored))
  }, [navigate])

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (!result) return null

  const scores = Object.entries(result.db_scores || {})
  const topDB = scores[0]

  return (
    <div className="results-page">
      <nav className="results-nav">
        <button className="results-nav__back btn btn--ghost" onClick={() => navigate('/')}>
          ← New analysis
        </button>
        <div className="results-nav__logo">
          <span style={{ color: 'var(--accent)' }}>⬡</span> SchemaSense
        </div>
        <button className="btn btn--ghost results-nav__share" onClick={handleCopyLink}>
          {copied ? '✓ Copied!' : '⎘ Share'}
        </button>
      </nav>

      <div className="results-container">

        <div className="results-header fade-up">
          <div className="results-header__file">
            <span className="mono">{result.source_file?.replace(/^tmp\w+\./, 'schema.')}</span>
            <span className="results-header__format">{result.source_format?.toUpperCase()}</span>
          </div>
          <h1 className="results-header__title">Analysis Complete</h1>
          {topDB && (
            <p className="results-header__sub">
              Best match: <strong>{topDB[0]}</strong> — {topDB[1].absolute_pct}% compatibility
            </p>
          )}
        </div>

        {result.ai_explanation && (
          <div className="fade-up fade-up-delay-1">
            <AIExplanation text={result.ai_explanation} />
          </div>
        )}

        <div className="results-grid fade-up fade-up-delay-2">
          <SchemaOverview result={result} />
          <MigrationPlan plan={result.migration_plan} risk={result.migration_risk} />
        </div>

        <div className="fade-up fade-up-delay-3">
          <div className="section-header">
            <h2 className="section-title">Database Compatibility</h2>
            <span className="section-count">{scores.length} databases scored</span>
          </div>
          <div className="scores-list">
            {scores.map(([dbName, info], index) => (
              <DBScoreCard
                key={dbName}
                dbName={dbName}
                info={info}
                rank={index + 1}
                style={{ animationDelay: `${0.2 + index * 0.03}s` }}
              />
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}