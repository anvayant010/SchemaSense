import React, { useEffect, useRef, useState } from 'react'
import './ERDiagram.css'

export default function ERDiagram({ erData }) {
  const mermaidRef = useRef(null)
  const [copied, setCopied] = useState(false)
  const [rendered, setRendered] = useState(false)
  const [error, setError] = useState(false)
  const [activeTab, setActiveTab] = useState('diagram')

  const mermaidCode = erData?.mermaid_code || ''

  useEffect(() => {
    if (activeTab !== 'diagram' || !mermaidCode || !mermaidRef.current) return

    let cancelled = false

    const render = async () => {
      try {
        if (!window.mermaid) {
          await new Promise((resolve, reject) => {
            const script = document.createElement('script')
            script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js'
            script.onload = resolve
            script.onerror = reject
            document.head.appendChild(script)
          })
        }

        if (cancelled) return

        window.mermaid.initialize({
          startOnLoad: false,
          theme: 'base',
          themeVariables: {
            darkMode: true,
            background: '#0d0d14',
            primaryColor: '#1a1a2e',
            primaryTextColor: '#e8e8f0',
            primaryBorderColor: '#2a2a3e',
            lineColor: '#6b6b8a',
            secondaryColor: '#111118',
            tertiaryColor: '#0d0d14',
            fontSize: '13px',
            fontFamily: '"DM Mono", monospace',
            edgeLabelBackground: '#0d0d14',
            attributeBackgroundColorEven: '#111118',
            attributeBackgroundColorOdd: '#0d0d14',
          },
        })

        const id = `er-${Date.now()}`
        const { svg } = await window.mermaid.render(id, mermaidCode)

        if (!cancelled && mermaidRef.current) {
          mermaidRef.current.innerHTML = svg

          // Style the SVG to match our dark theme
          const svgEl = mermaidRef.current.querySelector('svg')
          if (svgEl) {
            svgEl.style.width = '100%'
            svgEl.style.maxWidth = '100%'
            svgEl.style.background = 'transparent'
          }
          setRendered(true)
          setError(false)
        }
      } catch (e) {
        console.error('Mermaid render error:', e)
        if (!cancelled) setError(true)
      }
    }

    render()
    return () => { cancelled = true }
  }, [mermaidCode, activeTab])

  const handleCopy = () => {
    navigator.clipboard.writeText(mermaidCode).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (!erData || !mermaidCode) return null

  return (
    <div className="er-card">
      <div className="er-card__header">
        <div className="er-card__title-row">
          <span className="er-card__title">ER Diagram</span>
          <div className="er-card__meta">
            <span className="er-card__stat">{erData.table_count} tables</span>
            <span className="er-card__dot">·</span>
            <span className="er-card__stat">{erData.relationship_count} relationships</span>
          </div>
        </div>

        <div className="er-card__controls">
          <div className="er-tabs">
            <button
              className={`er-tab ${activeTab === 'diagram' ? 'er-tab--active' : ''}`}
              onClick={() => setActiveTab('diagram')}
            >
              Diagram
            </button>
            <button
              className={`er-tab ${activeTab === 'code' ? 'er-tab--active' : ''}`}
              onClick={() => setActiveTab('code')}
            >
              Mermaid code
            </button>
          </div>
          <button className="er-copy-btn" onClick={handleCopy}>
            {copied ? '✓ Copied!' : '⎘ Copy code'}
          </button>
        </div>
      </div>

      {/* Diagram view */}
      {activeTab === 'diagram' && (
        <div className="er-diagram-wrap">
          {!rendered && !error && (
            <div className="er-loading">
              <span className="er-spinner" />
              Rendering diagram...
            </div>
          )}
          {error && (
            <div className="er-error">
              Failed to render diagram. Use the Mermaid code tab to copy and paste into
              <a href="https://mermaid.live" target="_blank" rel="noopener noreferrer"> mermaid.live</a>
            </div>
          )}
          <div
            ref={mermaidRef}
            className="er-diagram"
            style={{ display: rendered ? 'block' : 'none' }}
          />
        </div>
      )}

      {/* Code view */}
      {activeTab === 'code' && (
        <div className="er-code-wrap">
          <div className="er-code-hint">
            Copy and paste into{' '}
            <a href="https://mermaid.live" target="_blank" rel="noopener noreferrer">mermaid.live</a>,
            Notion, GitHub README, or any Mermaid renderer
          </div>
          <pre className="er-code">{mermaidCode}</pre>
        </div>
      )}
    </div>
  )
}