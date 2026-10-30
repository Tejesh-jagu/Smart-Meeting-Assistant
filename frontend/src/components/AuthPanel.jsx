import { useState } from 'react'
import { API_URL, readApiJson } from '../api/client.js'
import AnimatedButton from './ui/AnimatedButton.jsx'
import AnimatedCard from './ui/AnimatedCard.jsx'
import GlyphBackgroundDemo from './GlyphBackgroundDemo.jsx'

export default function AuthPanel({ csrfToken, onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
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
    }
    if (mode === 'verify' || mode === 'reset-confirm') {
      if (password !== confirmPassword) {
        setError('The passwords do not match.')
        return
      }
    }

    setIsSubmitting(true)
    try {
      const endpoints = {
        signup: 'register',
        verify: 'verify-email',
        'reset-request': 'request-password-reset',
        'reset-confirm': 'reset-password',
        login: 'login',
      }
      const endpoint = endpoints[mode]
      const body = mode === 'signup'
        ? { name: name.trim(), email: email.trim() }
        : mode === 'verify' || mode === 'reset-confirm'
          ? { email: email.trim(), code: verificationCode, password }
          : mode === 'reset-request'
            ? { email: email.trim() }
            : { email: email.trim(), password }
      const response = await fetch(`${API_URL}/auth/${endpoint}`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify(body),
      })
      const result = await readApiJson(response, 'Could not sign in. Please try again.')
      if (mode === 'signup') {
        setMode('verify')
        setEmail(result.email)
        setPassword('')
        setConfirmPassword('')
        setVerificationCode('')
        setNotice(result.message)
      } else if (mode === 'reset-request') {
        setMode('reset-confirm')
        setVerificationCode('')
        setPassword('')
        setConfirmPassword('')
        setNotice(result.message)
      } else if (mode === 'reset-confirm') {
        setMode('login')
        setVerificationCode('')
        setPassword('')
        setConfirmPassword('')
        setNotice(result.message)
      } else {
        onAuthenticated(result, mode === 'verify')
      }
    } catch (submitError) {
      if (mode === 'signup' && submitError.message.startsWith('Could not send the verification email.')) {
        setMode('verify')
        setPassword('')
        setConfirmPassword('')
        setVerificationCode('')
        setNotice(`${submitError.message} You can request another code below.`)
      } else {
        setError(submitError.message || 'Could not connect to the server.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  async function resendCode() {
    setError('')
    setNotice('')
    setIsSubmitting(true)
    try {
      const response = await fetch(`${API_URL}/auth/resend-verification`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({ email: email.trim() }),
      })
      const result = await readApiJson(response, 'Could not request a verification code.')
      setVerificationCode('')
      setNotice(result.message)
    } catch (resendError) {
      setError(resendError.message || 'Could not request a verification code.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-shell">
      <GlyphBackgroundDemo
        glowColor="#2dd4bf"
        shapeColor="#38bdf8"
        fontSize={11}
        interactive={true}
      />
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

        <AnimatedCard as="section" className="auth-card" aria-labelledby="auth-title" hoverLift={false}>
        <h2 id="auth-title">
          {mode === 'signup' ? 'Create your account'
            : mode === 'verify' ? 'Verify your email'
              : mode === 'reset-request' ? 'Reset your password'
                : mode === 'reset-confirm' ? 'Choose a new password'
                  : 'Welcome back'}
        </h2>
        <p className="auth-description">
          {mode === 'signup' ? 'Create an account to save and review your meetings.'
            : mode === 'verify' || mode === 'reset-confirm' ? 'Enter the 8-digit code sent to your email address.'
              : mode === 'reset-request' ? 'Enter your email and we will send a password reset code if an account exists.'
                : 'Enter your email and password to continue.'}
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

          {mode === 'verify' || mode === 'reset-confirm' ? (
            <>
              <label htmlFor="auth-verification-code">Verification code</label>
              <input
                id="auth-verification-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{8}"
                maxLength={8}
                value={verificationCode}
                onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 8))}
                required
              />
              <label htmlFor="auth-password">{mode === 'verify' ? 'Choose a password' : 'New password'}</label>
              <input
                id="auth-password"
                type={showPasswords ? 'text' : 'password'}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <label htmlFor="auth-confirm-password">Confirm password</label>
              <input
                id="auth-confirm-password"
                type={showPasswords ? 'text' : 'password'}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
              />
            </>
          ) : mode === 'login' && (
          <>
          <label htmlFor="auth-password">Password</label>
          <div className="auth-password-field">
            <input
              id="auth-password"
              type={showPasswords ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={1}
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
          </>
          )}

          {error && <p className="auth-feedback auth-feedback--error" role="alert">{error}</p>}
          {notice && <p className="auth-feedback" role="status">{notice}</p>}

          <AnimatedButton type="submit" className="auth-submit" disabled={isSubmitting} aria-busy={isSubmitting}>
            {isSubmitting ? 'Please wait...'
              : mode === 'signup' ? 'Create account'
                : mode === 'verify' ? 'Verify email'
                  : mode === 'reset-request' ? 'Send reset code'
                    : mode === 'reset-confirm' ? 'Reset password'
                      : 'Sign in'}
          </AnimatedButton>
        </form>

        {mode === 'verify' && (
          <>
            <button type="button" className="auth-link-button auth-forgot-link" onClick={resendCode} disabled={isSubmitting}>
              Resend verification code
            </button>
            <button type="button" className="auth-link-button auth-forgot-link" onClick={() => { setMode('login'); setPassword(''); setConfirmPassword(''); setVerificationCode(''); setError(''); setNotice('') }}>
              Back to sign in
            </button>
          </>
        )}

        {mode === 'login' && (
          <>
            <button type="button" className="auth-link-button auth-forgot-link" onClick={() => { setMode('verify'); setPassword(''); setConfirmPassword(''); setVerificationCode(''); setError(''); setNotice('Enter your email to verify your account or request another code.') }}>
              Verify email / resend code
            </button>
            <button
              type="button"
              className="auth-link-button auth-forgot-link"
              onClick={() => { setMode('reset-request'); setPassword(''); setError(''); setNotice('') }}
            >
              Forgot password?
            </button>
          </>
        )}

        {(mode === 'reset-request' || mode === 'reset-confirm') && (
          <button
            type="button"
            className="auth-link-button auth-forgot-link"
            onClick={() => { setMode('login'); setPassword(''); setConfirmPassword(''); setVerificationCode(''); setError(''); setNotice('') }}
          >
            Back to sign in
          </button>
        )}

        {mode !== 'verify' && <p className="auth-switch">
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
        </p>}
        </AnimatedCard>
      </div>

      <footer className="auth-footer">
        <a href="/privacy.html">Privacy Policy</a>
        <a href="/terms.html">Terms and Conditions</a>
      </footer>
    </main>
  )
}
