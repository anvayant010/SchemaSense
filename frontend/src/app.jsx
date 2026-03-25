import React from 'react'
import { Routes, Route } from 'react-router-dom'
import UploadPage from './pages/UploadPage.jsx'
import ResultsPage from './pages/ResultsPage.jsx'
import SignInPage from './pages/SigninPage.jsx'
import SignUpPage from './pages/SignupPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/"          element={<UploadPage />} />
      <Route path="/results"   element={<ResultsPage />} />
      <Route path="/sign-in"   element={<SignInPage />} />
      <Route path="/sign-up"   element={<SignUpPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
    </Routes>
  )
}