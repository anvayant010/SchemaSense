import React, { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import './UploadPage.css'
import { FaGithub } from 'react-icons/fa'
import { useUser, UserButton } from '@clerk/clerk-react'
import API_BASE from '../api.js'

const SAMPLE_SCHEMA = `-- E-Commerce Platform Schema (SchemaSense sample)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    parent_id INT,
    FOREIGN KEY (parent_id) REFERENCES categories(id)
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    category_id INT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(10,2) NOT NULL,
    shipping_address JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id UUID NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE UNIQUE INDEX idx_users_email ON users(email);`

const FORMATS = ['sql', 'csv', 'json']
const FORMAT_HINTS = {
  sql: 'CREATE TABLE statements, ALTER TABLE, foreign keys',
  csv: 'table_name, column_name, data_type, is_pk, is_fk ...',
  json: 'Array of table objects with columns and constraints',
}

function ClerkNavItem() {
  const { isSignedIn } = useUser()
  const navigate = useNavigate()
  if (isSignedIn) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button className="btn btn--ghost" style={{ fontSize: '15px', padding: '7px 14px', fontFamily: 'var(--font-mono)' }} onClick={() => navigate('/dashboard')}>
          Dashboard
        </button>
        <UserButton afterSignOutUrl="/" />
      </div>
    )
  }
  return (
    <a href="/sign-in" className="upload-nav__signin">Sign in</a>
  )
}

export default function UploadPage() {
  const [file, setFile] = useState(null)
  const [format, setFormat] = useState('sql')
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)
  const navigate = useNavigate()

  const handleFile = useCallback((f) => {
    if (!f) return
    setFile(f)
    setError(null)
    const ext = f.name.split('.').pop().toLowerCase()
    if (FORMATS.includes(ext)) setFormat(ext)
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [handleFile])

  const onDragOver = (e) => { e.preventDefault(); setDragging(true) }
  const onDragLeave = () => setDragging(false)
  const onFileChange = (e) => { if (e.target.files[0]) handleFile(e.target.files[0]) }

  const handleAnalyze = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('format', format)
      formData.append('async_mode', 'false')

      const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Server error ${res.status}`)
      }
      const data = await res.json()
      if (data.status === 'error') throw new Error(data.error || 'Analysis failed')
      sessionStorage.setItem('schemasense_result', JSON.stringify(data.result))
      navigate('/results')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSample = async () => {
    setLoading(true)
    setError(null)
    try {
      const blob = new Blob([SAMPLE_SCHEMA], { type: 'text/plain' })
      const sampleFile = new File([blob], 'ecommerce_sample.sql', { type: 'text/plain' })
      setFile(sampleFile)
      setFormat('sql')

      const formData = new FormData()
      formData.append('file', sampleFile)
      formData.append('format', 'sql')
      formData.append('async_mode', 'false')

      const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Server error ${res.status}`)
      }
      const data = await res.json()
      if (data.status === 'error') throw new Error(data.error || 'Analysis failed')
      sessionStorage.setItem('schemasense_result', JSON.stringify(data.result))
      navigate('/results')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="upload-page">
      <div className="upload-page__grid" aria-hidden="true" />

      <nav className="upload-nav">
        <div className="upload-nav__logo">
          <span className="upload-nav__logo-icon">⬡</span>
          <span className="upload-nav__logo-text">SchemaSense</span>
        </div>

        <div className="upload-nav__right">
          <span className="upload-nav__status">
            <span className="upload-nav__status-dot" />
            API online
          </span>
          <a href="https://github.com/anvayant010/SchemaSense" target="_blank" rel="noopener noreferrer" className="upload-nav__github">
            <FaGithub size={18} /> GitHub
          </a>
          <ClerkNavItem />
        </div>
      </nav>

      {/* Two-column layout */}
      <div className="upload-layout">

        {/* Left panel — hero text */}
        <div className="upload-left fade-up">
          <div className="upload-left__eyebrow">Database schema analyzer</div>
          <h1 className="upload-title">
            Find the right<br />database for<br />your schema in seconds
          </h1>
          <p className="upload-subtitle">
            Upload a schema file and get instant compatibility scores,
            migration warnings, and AI-powered recommendations across 12 databases.
          </p>

          <div className="upload-stats">
            <div className="upload-stats__item">
              <span className="upload-stats__num">12</span>
              <span className="upload-stats__label">Databases</span>
            </div>
            <div className="upload-stats__divider" />
            <div className="upload-stats__item">
              <span className="upload-stats__num">AI</span>
              <span className="upload-stats__label">Explanations</span>
            </div>
            <div className="upload-stats__divider" />
            <div className="upload-stats__item">
              <span className="upload-stats__num">Unlimited</span>
              <span className="upload-stats__label">Column notes</span>
            </div>
          </div>
        </div>

        {/* Right panel — upload form */}
        <div className="upload-right fade-up fade-up-delay-1">

          <div
            className={`dropzone ${dragging ? 'dropzone--active' : ''} ${file ? 'dropzone--filled' : ''}`}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".sql,.csv,.json"
              onChange={onFileChange}
              style={{ display: 'none' }}
            />
            {file ? (
              <div className="dropzone__file">
                <span className="dropzone__file-icon">◈</span>
                <div className="dropzone__file-info">
                  <span className="dropzone__file-name">{file.name}</span>
                  <span className="dropzone__file-size">
                    {(file.size / 1024).toFixed(1)} KB · {format.toUpperCase()}
                  </span>
                </div>
                <button
                  className="dropzone__clear"
                  onClick={(e) => { e.stopPropagation(); setFile(null) }}
                >✕</button>
              </div>
            ) : (
              <div className="dropzone__empty">
                <span className="dropzone__icon">⊕</span>
                <p className="dropzone__label">Drop your schema file here</p>
                <p className="dropzone__hint">or click to browse · .sql .csv .json</p>
              </div>
            )}
          </div>

          {/* ── Sample schema button ── */}
          <button
            className="sample-btn"
            onClick={handleSample}
            disabled={loading}
          >
            {loading && !file ? (
              <><span className="spinner spinner--dark" />Loading sample...</>
            ) : (
              <>Try with a sample schema: E-Commerce (5 tables)</>
            )}
          </button>

          <div className="format-selector">
            <span className="format-selector__label">Format</span>
            <div className="format-selector__tabs">
              {FORMATS.map(f => (
                <button
                  key={f}
                  className={`format-tab ${format === f ? 'format-tab--active' : ''}`}
                  onClick={() => setFormat(f)}
                >.{f}</button>
              ))}
            </div>
            <span className="format-selector__hint">{FORMAT_HINTS[format]}</span>
          </div>

          {error && (
            <div className="upload-error">
              <span>⚠</span> {error}
            </div>
          )}

          <button
            className="btn btn--primary analyze-btn"
            onClick={handleAnalyze}
            disabled={!file || loading}
          >
            {loading ? (
              <><span className="spinner" />Analyzing schema...</>
            ) : (
              <><span>▶</span>Start Analysis</>
            )}
          </button>

          <div className="upload-right__footer">
            Supports PostgreSQL · MySQL · MongoDB · SQLite · and 8 more
          </div>

        </div>
      </div>
    </div>
  )
}