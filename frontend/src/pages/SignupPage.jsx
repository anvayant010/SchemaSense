import React from 'react';
import { SignUp } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import './SignupPage.css'; 

export default function SignUpPage() {
  const navigate = useNavigate();

  return (
    <div className="signup-page">
      <div className="signup-page__grid" aria-hidden="true" />

      <nav className="signup-nav">
        <div
          className="signup-nav__logo"
          onClick={() => navigate('/')}
          style={{ cursor: 'pointer' }}
        >
          <span className="signup-nav__logo-icon">⬡</span>
          <span className="signup-nav__logo-text">SchemaSense</span>
        </div>
      </nav>

      <div className="signup-layout">
        {/* Left side – promotional / value proposition content */}
        <div className="signup-left">
          <div className="signup-eyebrow">
            <span className="signup-eyebrow__line" />
            GET STARTED FREE
          </div>

          <h1 className="signup-title">
            Create your
            <br />
            SchemaSense
            <br />
            account
          </h1>

          <p className="signup-subtitle">
            Join thousands of developers who use SchemaSense
            to find the right database for their schema.
          </p>

          <div className="signup-features">
            <div className="signup-feature">
              <span className="signup-feature__icon">◈</span>
              Save unlimited analyses
            </div>
            <div className="signup-feature">
              <span className="signup-feature__icon">⬡</span>
              Re-open any past result
            </div>
            <div className="signup-feature">
              <span className="signup-feature__icon">∞</span>
              Track your schema history
            </div>
          </div>
        </div>

        {/* Right side – Clerk SignUp component */}
        <div className="signup-right">
          <div className="signup-clerk">
            <SignUp
              routing="hash"
              signInUrl="/sign-in"
              afterSignUpUrl="/dashboard"
              appearance={{
                variables: {
                  colorPrimary: '#7c6aff',
                  colorBackground: '#111118',
                  colorInputBackground: '#0d0d14',
                  colorInputText: '#e8e8f0',
                  colorText: '#e8e8f0',
                  colorTextSecondary: '#9ca3af',
                  colorNeutral: '#2a2a3e',
                  borderRadius: '10px',
                  fontFamily: '"DM Sans", system-ui, sans-serif',
                  fontSize: '15px',
                },
                elements: {
                  card: {
                    padding: '2.5rem',
                    boxShadow: '0 10px 40px rgba(0,0,0,0.45)',
                  },
                  socialButtonsBlockButton: {
                    height: '48px',
                    borderRadius: '10px',
                  },
                  formButtonPrimary: {
                    height: '48px',
                    fontSize: '16px',
                    fontWeight: 600,
                  },
                  headerTitle: {
                    fontSize: '22px',
                  },
                },
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}