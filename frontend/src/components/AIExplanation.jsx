import React from 'react'
import './AIExplanation.css'

export default function AIExplanation({ text }) {
  return (
    <div className="ai-card">
      <div className="ai-card__header">
        <span className="ai-card__icon">✦</span>
        <span className="ai-card__label">AI Analysis</span>
      </div>
      <p className="ai-card__text">{text}</p>
    </div>
  )
}