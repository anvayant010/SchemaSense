import React from 'react'
import { Routes, Route } from 'react-router-dom'
import UploadPage from './pages/UploadPage.jsx'
import ResultsPage from './pages/ResultsPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/results" element={<ResultsPage />} />
    </Routes>
  )
}