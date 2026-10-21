import { useState } from 'react'
import { API_URL, readApiJson } from '../api/client.js'

export default function AuthPanel({ csrfToken, onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPasswords, setShowPasswords] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function submit(event) {
    event.preventDefault()
    setError('')
    setNotice('')

    if (mode === 'signup') {
      if (!name.trim()) {
        setError('Enter your name.')
        return
      }
      if (password !== confirmPassword) {
        setError('The passwords do not match.')
        return
      }
    }

    setIsSubmitting(true)
    try {
      const response = await fetch(`${API_URL}/auth/${mode === 'signup' ? 'register' : 'login'}`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify(
          mode === 'signup'
            ? { name: name.trim(), email: email.trim(), password }
            : { email: email.trim(), password }
        ),
      })
      const result = await readApiJson(response, 'Could not sign in. Please try again.')
      onAuthenticated(result, mode === 'signup')
    } catch (submitError) {
      setError(submitError.message || 'Could not connect to the server.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-shell">
      <div className="auth-layout">
        <header className="auth-story">
          <a className="auth-brand" href="/">
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 32 32" width="24" height="24" fill="none">
                <path d="M6 17h3l2-6 4 12 3-10 2 4h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span>Smart Meeting Assistant</span>
          </a>
          <h1>Meeting transcripts and reports</h1>
          <p>Sign in to review saved transcripts, correct text, and generate reports from your meetings.</p>
        </header>

        <section className="auth-card" aria-labelledby="auth-title">
        <h2 id="auth-title">{mode === 'signup' ? 'Create your account' : 'Welcome back'}</h2>
        <p className="auth-description">
          {mode === 'signup' ? 'Create an account to save and review your meetings.' : 'Enter your email and password to continue.'}
        </p>

        <form onSubmit={submit}>
          {mode === 'signup' && (
            <>
              <label htmlFor="auth-name">Name</label>
              <input
                id="auth-name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={100}
                required
              />
            </>
          )}

          <label htmlFor="auth-email">Email</label>
          <input
            id="auth-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            maxLength={254}
            required
          />

          <label htmlFor="auth-password">Password</label>
          <div className="auth-password-field">
            <input
              id="auth-password"
              type={showPasswords ? 'text' : 'password'}
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={mode === 'signup' ? 8 : 1}
              maxLength={128}
              required
            />
            <button
              type="button"
              className="auth-visibility-toggle"
              onClick={() => setShowPasswords((visible) => !visible)}
              aria-label={showPasswords ? 'Hide password' : 'Show password'}
            >
              {showPasswords ? 'Hide' : 'Show'}
            </button>
          </div>

          {mode === 'signup' && (
            <>
              <label htmlFor="auth-confirm-password">Confirm password</label>
              <input
                id="auth-confirm-password"
                type={showPasswords ? 'text' : 'password'}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                minLength={8}
                maxLength={128}
                required
              />
            </>
          )}

          {error && <p className="auth-feedback auth-feedback--error" role="alert">{error}</p>}
          {notice && <p className="auth-feedback" role="status">{notice}</p>}

          <button type="submit" className="auth-submit" disabled={isSubmitting} aria-busy={isSubmitting}>
            {isSubmitting ? 'Please wait...' : mode === 'signup' ? 'Create account' : 'Sign in'}
          </button>
        </form>

        {mode === 'login' && (
          <button
            type="button"
            className="auth-link-button auth-forgot-link"
            onClick={() => setNotice('Password reset is unavailable because no email service is configured. Ask the application administrator to reset your account.')}
          >
            Forgot password?
          </button>
        )}

        <p className="auth-switch">
          {mode === 'signup' ? 'Already have an account?' : 'New to Smart Meeting Assistant?'}{' '}
          <button
            type="button"
            className="auth-link-button"
            onClick={() => {
              setMode((current) => current === 'signup' ? 'login' : 'signup')
              setError('')
              setNotice('')
            }}
          >
            {mode === 'signup' ? 'Sign in' : 'Create an account'}
          </button>
        </p>
        </section>
      </div>

      <footer className="auth-footer">
        <a href="/privacy.html">Privacy Policy</a>
        <a href="/terms.html">Terms and Conditions</a>
      </footer>
    </main>
  )
}
