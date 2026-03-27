import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { FaGithub } from 'react-icons/fa'
import { useUser, useAuth, UserButton } from '@clerk/clerk-react'
import DBScoreCard from '../components/DBScoreCard.jsx'
import SchemaOverview from '../components/SchemaOverview.jsx'
import MigrationPlan from '../components/MigrationPlan.jsx'
import AIExplanation from '../components/AIExplanation.jsx'
import ERDiagram from '../components/ERDiagram.jsx'
import './ResultsPage.css'
import API_BASE from '../api.js'

function deriveQuality(expl) {
  const type = expl.type_support_frac ?? 1
  const constraint = expl.constraint_frac ?? 1
  const violations = expl.type_violations ?? 0
  return Math.max(0, (type * 0.5 + constraint * 0.5) * 10 - violations * 0.5)
}

function deriveMigrationRisk(expl) {
  const violations = expl.type_violations ?? 0
  const constraint = expl.constraint_frac ?? 1
  return violations * 15 + (1 - constraint) * 40
}

function derivePerformance(expl) {
  const type = expl.type_support_frac ?? 1
  const special = expl.special_frac ?? 1
  return (type * 0.6 + special * 0.4) * 100
}

function exportReport(result) {
  const scores = Object.entries(result.db_scores || {})
  const lines = []
  const s = result.schema_summary || {}
  const plan = result.migration_plan || {}
  const fileName = result.source_file?.replace(/^tmp\w+\./, 'schema.') || 'schema'

  lines.push('SCHEMASENSE ANALYSIS REPORT')
  lines.push('='.repeat(60))
  lines.push(`Generated: ${new Date().toLocaleString()}`)
  lines.push(`Source: ${fileName} (${result.source_format?.toUpperCase()})`)
  lines.push('')
  lines.push(`Tables: ${s.tables}  Columns: ${s.columns}  PKs: ${s.pks}  FKs: ${s.fks}`)
  lines.push(`Quality: ${result.quality?.quality_score}/10  Risk: ${result.migration_risk?.risk_level}`)
  lines.push('')

  if (result.ai_explanation) {
    lines.push('AI ANALYSIS')
    lines.push('-'.repeat(40))
    lines.push(result.ai_explanation)
    lines.push('')
  }

  lines.push('DATABASE COMPATIBILITY RANKING')
  lines.push('-'.repeat(40))
  scores.forEach(([db, info], i) => {
    lines.push(`#${i+1}  ${db.padEnd(18)} ${String(info.absolute_pct + '%').padEnd(8)} ${(info.verdict || '').toUpperCase()}`)
    const warnings = info.explanation?.migration_warnings || []
    warnings.filter(w => !w.toLowerCase().includes('no major')).forEach(w => lines.push(`     > ${w}`))
  })
  lines.push('')

  lines.push('MIGRATION PLAN')
  lines.push('-'.repeat(40))
  plan.table_creation_order?.forEach((t, i) => lines.push(`  ${i+1}. ${t}`))
  plan.constraint_steps?.forEach(s => lines.push(`  - ${s}`))

  const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `schemasense-report-${Date.now()}.txt`
  a.click()
  URL.revokeObjectURL(url)
}


export default function ResultsPage() {
  const [result, setResult] = useState(null)
  const [copied, setCopied] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const { isSignedIn } = useUser()
  const { getToken } = useAuth()
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

  const handleSave = async () => {
    if (!isSignedIn) { navigate('/sign-in'); return }
    setSaving(true)
    try {
      const token = await getToken()
      const res = await fetch(`${API_BASE}/analyses/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          file_name: result.source_file?.replace(/^tmp\w+\./, 'schema.') || 'schema',
          file_format: result.source_format || 'sql',
          result,
        })
      })
      if (res.ok) setSaved(true)
    } catch(e) { console.error(e) }
    finally { setSaving(false) }
  }

  if (!result) return null

  const fileName = result.source_file?.replace(/^tmp\w+\./, 'schema.') || 'schema'

  const sortedScores = Object.entries(result.db_scores || {})

  const topDB = sortedScores[0]
  return (
    <div className="results-page">

      {/* Navbar */}
      <nav className="results-nav">
        <div className="results-nav__logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          <span className="results-nav__logo-icon">⬡</span>
          <span className="results-nav__logo-text">SchemaSense</span>
        </div>
        <div className="results-nav__right">
          <button className="results-nav__new btn btn--ghost" onClick={() => navigate('/')}>
            ← New analysis
          </button>
         
          <button className="btn btn--ghost results-nav__export" onClick={() => exportReport(result)}>
            ↓ Export Report
          </button>
          <button
            className={`btn btn--ghost results-nav__save ${saved ? 'results-nav__save--saved' : ''}`}
            onClick={handleSave}
            disabled={saving || saved}
          >
            {saved ? '✓ Saved' : saving ? 'Saving...' : '⊕ Save'}
          </button>
          <button className="results-nav__share btn btn--ghost" onClick={handleCopyLink}>
            {copied ? '✓ Copied!' : '⎘ Share'}
          </button>
          {isSignedIn && <UserButton afterSignOutUrl="/" />}
        </div>
      </nav>

      {/* Two-column layout */}
      <div className="results-layout">

        {/* Left panel */}
        <div className="results-left fade-up">
          <div className="results-header">
            <div className="results-header__eyebrow">
              <span className="results-header__eyebrow-line" />
              Analysis complete
            </div>
            <div className="results-header__meta">
              <span className="mono results-header__file">{fileName}</span>
              <span className="results-header__format">{result.source_format?.toUpperCase()}</span>
            </div>
            <h1 className="results-title">
              {topDB ? (
                <><span className="results-title__match">{topDB[0]}</span><br />is your best fit</>
              ) : 'Analysis Complete'}
            </h1>
            {topDB && (
              <p className="results-subtitle">
                {topDB[1].absolute_pct}% compatibility — {topDB[1].verdict} match
              </p>
            )}
          </div>

          {result.ai_explanation && (
            <div className="fade-up fade-up-delay-1">
              <AIExplanation text={result.ai_explanation} />
            </div>
          )}

          <div className="results-cards fade-up fade-up-delay-2">
            <SchemaOverview result={result} />
            <MigrationPlan plan={result.migration_plan} risk={result.migration_risk} />
            {result.er_diagram && (
              <ERDiagram erData={result.er_diagram} />
            )}
          </div>
        </div>

        {/* Right panel */}
        <div className="results-right fade-up fade-up-delay-1">
          <div className="results-scores-header">
            <span className="results-scores-label">Database Compatibility</span>
            <span className="results-scores-count">{sortedScores.length} databases</span>
          </div>

          <div className="scores-list">
            {sortedScores.map(([dbName, info], index) => (
              <DBScoreCard
                key={dbName}
                dbName={dbName}
                info={info}
                rank={index + 1}
                style={{ animationDelay: `${0.1 + index * 0.03}s` }}
              />
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}