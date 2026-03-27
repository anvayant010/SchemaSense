import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUser, useAuth, UserButton } from '@clerk/clerk-react'
import { FaGithub } from 'react-icons/fa'
import './DashboardPage.css'
import API_BASE from '../api.js'

const FORMAT_COLOR = { sql: 'accent', csv: 'blue', json: 'amber' }
const SCORE_COLOR = (pct) => {
  if (pct >= 90) return 'green'
  if (pct >= 75) return 'blue'
  if (pct >= 55) return 'amber'
  return 'red'
}

function AnalysisCard({ record, onClick, onDelete }) {
  const date = new Date(record.created_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric'
  })
  const scoreColor = SCORE_COLOR(record.top_score || 0)
  const fmtColor   = FORMAT_COLOR[record.file_format] || 'accent'

  return (
    <div className="analysis-card" onClick={onClick}>
      <div className="analysis-card__header">
        <span className={`analysis-card__format analysis-card__format--${fmtColor}`}>
          .{record.file_format}
        </span>
        <span className="analysis-card__date">{date}</span>
      </div>

      <div className="analysis-card__name">{record.file_name}</div>

      <div className="analysis-card__footer">
        <div className="analysis-card__db">
          <span className={`analysis-card__score analysis-card__score--${scoreColor}`}>
            {record.top_score}%
          </span>
          <span className="analysis-card__db-name">{record.top_db}</span>
        </div>
        <div className="analysis-card__meta">
          <span>{record.table_count} tables</span>
          <button
            className="analysis-card__delete"
            onClick={(e) => { e.stopPropagation(); onDelete(record.id) }}
            title="Delete"
          >✕</button>
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { user, isLoaded } = useUser()
  const { getToken } = useAuth()
  const navigate = useNavigate()

  const [history, setHistory] = useState([])
  const [stats, setStats]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!isLoaded) return
    if (!user) { navigate('/sign-in'); return }
    fetchHistory()
  }, [isLoaded, user])

  const fetchHistory = async () => {
    try {
      const token = await getToken()
      const res = await fetch('${API_BASE}/analyses/history', {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Failed to fetch history')
      const data = await res.json()
      setHistory(data.history || [])
      setStats(data.stats || null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleOpen = async (record) => {
    try {
      const token = await getToken()
      const res = await fetch(`${API_BASE}/analyses/${record.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await res.json()
      if (data.record?.result) {
        const result = data.record.result
        const topDbName = data.record.top_db
        if (topDbName && result.db_scores && result.db_scores[topDbName]) {
          const entries = Object.entries(result.db_scores)
          const sorted = [
            [topDbName, result.db_scores[topDbName]],
            ...entries.filter(([k]) => k !== topDbName)
              .sort(([, a], [, b]) => (b.absolute_pct ?? 0) - (a.absolute_pct ?? 0))
          ]
          result.db_scores = Object.fromEntries(sorted)
        }
        sessionStorage.setItem('schemasense_result', JSON.stringify(result))
        navigate('/results')
      }
    } catch (e) {
      console.error('Failed to open analysis', e)
    }
  }

  const handleDelete = async (id) => {
    try {
      const token = await getToken()
      await fetch(`${API_BASE}/analyses/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      })
      setHistory(h => h.filter(r => r.id !== id))
    } catch (e) {
      console.error('Failed to delete', e)
    }
  }

  if (!isLoaded || loading) {
    return (
      <div className="dashboard-loading">
        <span className="dashboard-spinner" />
      </div>
    )
  }

  return (
    <div className="dashboard-page">

      {/* Navbar */}
      <nav className="dashboard-nav">
        <div className="dashboard-nav__logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          <span className="dashboard-nav__logo-icon">⬡</span>
          <span className="dashboard-nav__logo-text">SchemaSense</span>
        </div>
        <div className="dashboard-nav__right">
          <button className="btn btn--ghost dashboard-nav__new" style={{ fontSize: '16px', padding: '7px 14px', fontFamily: 'var(--font-mono)' }} onClick={() => navigate('/')}>
            + New analysis
          </button>
          
          <UserButton afterSignOutUrl="/" />
        </div>
      </nav>

      <div className="dashboard-layout">

        {/* Left — user info + stats */}
        <div className="dashboard-left fade-up">
          <div className="dashboard-user">
            <div className="dashboard-user__avatar">
              {user?.imageUrl
                ? <img src={user.imageUrl} alt="avatar" />
                : <span>{user?.firstName?.[0] || '?'}</span>
              }
            </div>
            <div>
              <div className="dashboard-user__name">
                {user?.fullName || user?.firstName || 'Welcome'}
              </div>
              <div className="dashboard-user__email">
                {user?.primaryEmailAddress?.emailAddress}
              </div>
            </div>
          </div>

          {stats && (
            <div className="dashboard-stats">
              <div className="dashboard-stat">
                <span className="dashboard-stat__num">{stats.total_analyses}</span>
                <span className="dashboard-stat__label">Analyses run</span>
              </div>
              <div className="dashboard-stat__divider" />
              <div className="dashboard-stat">
                <span className="dashboard-stat__num">.{stats.favourite_format}</span>
                <span className="dashboard-stat__label">Top format</span>
              </div>
              <div className="dashboard-stat__divider" />
              <div className="dashboard-stat">
                <span className="dashboard-stat__num" style={{ fontSize: '30px' }}>
                  {stats.favourite_db || '—'}
                </span>
                <span className="dashboard-stat__label">Top database</span>
              </div>
            </div>
          )}

          <div className="dashboard-left__eyebrow">
            <span className="dashboard-left__eyebrow-line" />
            Your analyses
          </div>
          <p className="dashboard-left__hint">
            Click any card to re-open the full results page.
          </p>
        </div>

        {/* Right — analysis history grid */}
        <div className="dashboard-right fade-up fade-up-delay-1">
          {error && (
            <div className="dashboard-error">⚠ {error}</div>
          )}

          {!loading && history.length === 0 && (
            <div className="dashboard-empty">
              <span className="dashboard-empty__icon">◈</span>
              <p>No analyses yet.</p>
              <button className="btn btn--primary" onClick={() => navigate('/')}>
                Run your first analysis
              </button>
            </div>
          )}

          <div className="dashboard-grid">
            {history.map(record => (
              <AnalysisCard
                key={record.id}
                record={record}
                onClick={() => handleOpen(record)}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}