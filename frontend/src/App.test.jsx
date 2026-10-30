// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App.jsx'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function jsonResponse(body) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
}

function stubAuthenticatedFetch(handler) {
  vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
    if (url.endsWith('/auth/csrf')) return jsonResponse({ csrf_token: 'csrf-test' })
    if (url.endsWith('/auth/me')) {
      return jsonResponse({
        user: { id: 1, name: 'Test User', email: 'test@example.com' },
        csrf_token: 'csrf-test',
      })
    }
    return handler(url, options)
  }))
}

describe('Smart Meeting Assistant interactions', () => {
  it('shows the 200 MB upload limit and rejects larger audio files', async () => {
    stubAuthenticatedFetch((url) => {
      if (url.endsWith('/transcripts')) return jsonResponse([])
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })
    const createObjectURL = vi.fn(() => 'blob:preview-audio')
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL: vi.fn() })

    render(<App />)
    await screen.findByText('Signed in as Test User')
    expect(screen.getByText(/Maximum file size: 200 MB/)).toBeTruthy()

    const oversizedFile = new File(['sample audio'], 'meeting.wav', { type: 'audio/wav' })
    Object.defineProperty(oversizedFile, 'size', { value: 200 * 1024 * 1024 + 1 })
    fireEvent.change(screen.getByLabelText('Choose an audio file'), {
      target: { files: [oversizedFile] },
    })

    expect(await screen.findByText(/Audio file is too large/)).toBeTruthy()
    expect(createObjectURL).not.toHaveBeenCalled()
    expect(screen.queryByText('Audio preview')).toBeNull()
  })

  it('keeps audio play, pause, seeking, and duration connected', async () => {
    stubAuthenticatedFetch((url) => {
      if (url.endsWith('/transcripts')) return jsonResponse([])
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:preview-audio'),
      revokeObjectURL: vi.fn(),
    })
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})

    const { container } = render(<App />)
    await screen.findByText('Signed in as Test User')
    const audioFile = new File(['sample audio'], 'meeting.wav', { type: 'audio/wav' })
    fireEvent.change(screen.getByLabelText('Choose an audio file'), {
      target: { files: [audioFile] },
    })

    const playButton = await screen.findByRole('button', { name: 'Play audio' })
    const audio = container.querySelector('audio')
    expect(audio).not.toBeNull()
    let isPaused = true
    Object.defineProperty(audio, 'paused', {
      configurable: true,
      get: () => isPaused,
    })

    await userEvent.click(playButton)
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce()
    isPaused = false
    fireEvent.play(audio)
    expect(screen.getByRole('button', { name: 'Pause audio' }).getAttribute('aria-pressed')).toBe('true')

    await userEvent.click(screen.getByRole('button', { name: 'Pause audio' }))
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalledOnce()

    Object.defineProperty(audio, 'duration', { configurable: true, value: 120 })
    let currentTime = 0
    Object.defineProperty(audio, 'currentTime', {
      configurable: true,
      get: () => currentTime,
      set: (value) => { currentTime = value },
    })
    fireEvent.loadedMetadata(audio)

    const seek = screen.getByRole('slider', { name: 'Seek through audio' })
    expect(seek.getAttribute('aria-valuetext')).toBe('0:00 of 2:00')
    fireEvent.change(seek, { target: { value: '61' } })
    expect(audio.currentTime).toBe(61)
    expect(seek.getAttribute('aria-valuetext')).toBe('1:01 of 2:00')
  })

  it('shows saving feedback while a transcript request is pending', async () => {
    let resolveSave
    const pendingSave = new Promise((resolve) => { resolveSave = resolve })
    let transcriptSaved = false
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.endsWith('/reports')) return jsonResponse([])
      if (url.endsWith('/transcripts') && options.method === 'POST') {
        return pendingSave.then(() => {
          transcriptSaved = true
          return { ok: true, json: () => Promise.resolve({ id: 7, session_number: 1, message: 'Transcript saved.' }) }
        })
      }
      if (url.endsWith('/transcripts')) {
        return jsonResponse(transcriptSaved
          ? [{ id: 7, session_number: 1, transcript: 'We agreed to review the plan.', created_at: '2026-10-17T00:00:00Z' }]
          : [])
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    stubAuthenticatedFetch(fetchMock)

    render(<App />)
    await screen.findByText('No saved sessions yet')
    await userEvent.type(screen.getByLabelText('Meeting transcript'), 'We agreed to review the plan.')
    await userEvent.click(screen.getByRole('button', { name: 'Save transcript' }))

    const saveButton = screen.getByRole('button', { name: 'Saving transcript...' })
    expect(saveButton.disabled).toBe(true)
    resolveSave()

    await screen.findByText('We agreed to review the plan.')
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Saving transcript...' })).toBeNull())
  })

  it('navigates between Home, AI, Notes, and Profile and marks the current area', async () => {
    stubAuthenticatedFetch((url) => {
      if (url.endsWith('/transcripts')) return jsonResponse([])
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })

    render(<App />)
    await screen.findByText('Signed in as Test User')
    const desktopNav = screen.getAllByRole('navigation', { name: 'Main navigation' })[0]
    expect(desktopNav.querySelector('[aria-current="page"]').textContent).toContain('Home')

    await userEvent.click(within(desktopNav).getByRole('button', { name: 'AI' }))
    expect(screen.getByRole('heading', { name: 'AI workspace' })).toBeTruthy()
    expect(desktopNav.querySelector('[aria-current="page"]').textContent).toContain('AI')

    await userEvent.click(within(desktopNav).getByRole('button', { name: 'Notes' }))
    expect(screen.getByRole('heading', { name: 'Notes & transcripts' })).toBeTruthy()
    expect(desktopNav.querySelector('[aria-current="page"]').textContent).toContain('Notes')

    await userEvent.click(within(desktopNav).getByRole('button', { name: 'Profile' }))
    expect(screen.getByRole('heading', { name: 'Profile' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'test@example.com' }).getAttribute('href')).toBe('mailto:test@example.com')

    await userEvent.click(within(desktopNav).getByRole('button', { name: 'Home' }))
    expect(screen.getByRole('heading', { name: /Meeting transcripts/ })).toBeTruthy()
  })

  it('shows an empty search state and restores meetings when the query is cleared', async () => {
    stubAuthenticatedFetch((url) => {
      if (url.endsWith('/transcripts')) {
        return jsonResponse([{ id: 12, session_number: 3, transcript: 'We agreed to review the launch plan.', created_at: '2026-10-17T00:00:00Z' }])
      }
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })

    render(<App />)
    await screen.findByRole('article', { name: 'Session 3' })
    const search = screen.getByRole('searchbox', { name: /Search meeting sessions/i })

    await userEvent.type(search, 'Session 3')
    expect(screen.getByRole('heading', { name: 'Session 3' })).toBeTruthy()
    await userEvent.clear(search)

    await userEvent.type(search, 'missing phrase')
    expect(screen.getByRole('heading', { name: 'No sessions match your search or filter' })).toBeTruthy()

    await userEvent.clear(search)
    expect(screen.getByRole('article', { name: 'Session 3' })).toBeTruthy()
  })

  it('filters saved sessions by today and explains that upcoming scheduling is unavailable', async () => {
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)
    stubAuthenticatedFetch((url) => {
      if (url.endsWith('/transcripts')) {
        return jsonResponse([
          { id: 1, session_number: 1, transcript: 'Today session transcript.', created_at: new Date().toISOString() },
          { id: 2, session_number: 2, transcript: 'Yesterday session transcript.', created_at: yesterday.toISOString() },
        ])
      }
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })

    render(<App />)
    await screen.findByRole('article', { name: 'Session 1' })
    const home = screen.getByRole('main')
    await userEvent.click(within(home).getByRole('button', { name: 'Today' }))
    expect(screen.getByRole('article', { name: 'Session 1' })).toBeTruthy()
    expect(screen.queryByRole('article', { name: 'Session 2' })).toBeNull()

    await userEvent.click(within(home).getByRole('button', { name: 'Upcoming' }))
    expect(screen.getByRole('heading', { name: 'Upcoming meetings are not connected' })).toBeTruthy()
    expect(screen.getByText(/no scheduling data/i)).toBeTruthy()

    await userEvent.click(within(home).getByRole('button', { name: 'All meetings' }))
    expect(screen.getByRole('article', { name: 'Session 1' })).toBeTruthy()
    expect(screen.getByRole('article', { name: 'Session 2' })).toBeTruthy()
  })

  it('generates and reviews a report against the selected saved transcript', async () => {
    const sourceTranscript = 'We reviewed the launch plan. The team chose Tuesday for the review. Priya will send the agenda.'
    stubAuthenticatedFetch((url, options = {}) => {
      if (url.endsWith('/transcripts')) {
        return jsonResponse([{ id: 31, session_number: 4, transcript: sourceTranscript, created_at: '2026-10-18T12:00:00Z' }])
      }
      if (url.endsWith('/reports')) return jsonResponse([])
      if (url.endsWith('/transcripts/31/report') && options.method === 'POST') {
        return jsonResponse({
          meeting_id: 31,
          summary: 'We reviewed the launch plan.',
          decisions: ['The team chose Tuesday for the review.'],
          tasks: ['Priya will send the agenda.'],
          generator: 'Ollama llama3.2:3b',
          generated_at: '2026-10-18T12:05:00Z',
        })
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    render(<App />)
    await screen.findByRole('article', { name: 'Session 4' })
    await userEvent.click(screen.getAllByRole('button', { name: 'AI' })[0])
    expect(screen.getByRole('heading', { name: 'Create a meeting report' })).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Generate report' }))

    expect(await screen.findByText('We reviewed the launch plan.')).toBeTruthy()
    expect(screen.getByText('The team chose Tuesday for the review.')).toBeTruthy()
    expect(screen.getByText('Priya will send the agenda.')).toBeTruthy()
    await userEvent.click(screen.getByText('View source transcript'))
    expect(screen.getByText(sourceTranscript)).toBeTruthy()
  })

  it('shows an actionable error and recovers when sessions can be reloaded', async () => {
    let transcriptRequests = 0
    stubAuthenticatedFetch((url) => {
      if (url.endsWith('/transcripts')) {
        transcriptRequests += 1
        if (transcriptRequests === 1) {
          return Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({ detail: 'Database unavailable.' }) })
        }
        return jsonResponse([])
      }
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })

    render(<App />)
    expect((await screen.findAllByRole('alert')).length).toBeGreaterThan(0)
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No saved sessions yet')).toBeTruthy()
    expect(transcriptRequests).toBe(2)
  })

  it('announces the saved-session loading state before showing the empty state', async () => {
    let finishLoading
    const pendingMeetings = new Promise((resolve) => { finishLoading = resolve })
    stubAuthenticatedFetch((url) => {
      if (url.endsWith('/transcripts')) return pendingMeetings
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })

    render(<App />)
    expect(await screen.findByText('Signed in as Test User')).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('Loading your saved sessions...')
    finishLoading(jsonResponse([]))
    expect(await screen.findByText('No saved sessions yet')).toBeTruthy()
  })

  it('states what Notes stores and presents the true empty state', async () => {
    stubAuthenticatedFetch((url) => {
      if (url.endsWith('/transcripts')) return jsonResponse([])
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })

    render(<App />)
    await screen.findByText('No saved sessions yet')
    await userEvent.click(screen.getAllByRole('button', { name: 'Notes' })[0])
    expect(screen.getByText(/Separate personal notes and speaker-labeled transcripts are not supported/i)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'No Meeting Sessions yet.' })).toBeTruthy()
  })

  it('filters Notes by saved date while keeping session search available', async () => {
    const older = new Date()
    older.setDate(older.getDate() - 10)
    stubAuthenticatedFetch((url) => {
      if (url.endsWith('/transcripts')) {
        return jsonResponse([
          { id: 1, session_number: 1, transcript: 'Today planning session.', created_at: new Date().toISOString() },
          { id: 2, session_number: 2, transcript: 'Older planning session.', created_at: older.toISOString() },
        ])
      }
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })

    render(<App />)
    await screen.findByRole('article', { name: 'Session 1' })
    await userEvent.click(screen.getAllByRole('button', { name: 'Notes' })[0])
    const dateFilter = screen.getByLabelText('Filter by date')

    await userEvent.selectOptions(dateFilter, 'today')
    expect(screen.getByRole('article', { name: 'Session 1' })).toBeTruthy()
    expect(screen.queryByRole('article', { name: 'Session 2' })).toBeNull()

    await userEvent.selectOptions(dateFilter, 'older')
    expect(screen.queryByRole('article', { name: 'Session 1' })).toBeNull()
    expect(screen.getByRole('article', { name: 'Session 2' })).toBeTruthy()

    await userEvent.type(screen.getByRole('searchbox', { name: /Search Meeting Sessions/i }), 'Session 2')
    expect(screen.getByRole('article', { name: 'Session 2' })).toBeTruthy()
    expect(screen.queryByRole('article', { name: 'Session 1' })).toBeNull()
  })

  it('registers a user and opens the protected meeting dashboard', async () => {
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url.endsWith('/auth/csrf')) return jsonResponse({ csrf_token: 'csrf-test' })
      if (url.endsWith('/auth/me')) {
        return Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({ detail: 'Authentication required.' }) })
      }
      if (url.endsWith('/auth/register')) {
        expect(options.headers['X-CSRF-Token']).toBe('csrf-test')
        expect(JSON.parse(options.body)).toEqual({ name: 'Priya Shah', email: 'priya@example.com' })
        return jsonResponse({
          verification_required: true,
          email: 'priya@example.com',
          message: 'Enter the verification code sent to your email.',
        })
      }
      if (url.endsWith('/auth/verify-email')) {
        expect(JSON.parse(options.body)).toEqual({ email: 'priya@example.com', code: '12345678', password: 'secure-pass-123' })
        return jsonResponse({
          user: { id: 8, name: 'Priya Shah', email: 'priya@example.com' },
          csrf_token: 'csrf-session',
        })
      }
      if (url.endsWith('/transcripts')) return jsonResponse([])
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    }))

    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Create an account' }))
    await userEvent.type(screen.getByLabelText('Name'), 'Priya Shah')
    await userEvent.type(screen.getByLabelText('Email'), 'priya@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('heading', { name: 'Verify your email' })).toBeTruthy()
    await userEvent.type(screen.getByLabelText('Verification code'), '12345678')
    await userEvent.type(screen.getByLabelText('Choose a password'), 'secure-pass-123')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'secure-pass-123')
    await userEvent.click(screen.getByRole('button', { name: 'Verify email' }))

    expect(await screen.findByText('Signed in as Priya Shah')).toBeTruthy()
  })

  it('requests a password reset code and lets the user set a new password', async () => {
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url.endsWith('/auth/csrf')) return jsonResponse({ csrf_token: 'csrf-test' })
      if (url.endsWith('/auth/me')) {
        return Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({ detail: 'Authentication required.' }) })
      }
      if (url.endsWith('/auth/request-password-reset')) {
        expect(options.headers['X-CSRF-Token']).toBe('csrf-test')
        expect(JSON.parse(options.body)).toEqual({ email: 'priya@example.com' })
        return jsonResponse({ message: 'If a verified account exists for that email, a password reset code has been sent.' })
      }
      if (url.endsWith('/auth/reset-password')) {
        expect(JSON.parse(options.body)).toEqual({
          email: 'priya@example.com',
          code: '12345678',
          password: 'new-secure-pass-456',
        })
        return jsonResponse({ message: 'Password reset. Sign in with your new password.' })
      }
      throw new Error(`Unexpected request: ${url}`)
    }))

    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Forgot password?' }))
    await userEvent.type(screen.getByLabelText('Email'), 'priya@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send reset code' }))
    expect(await screen.findByRole('heading', { name: 'Choose a new password' })).toBeTruthy()
    await userEvent.type(screen.getByLabelText('Verification code'), '12345678')
    await userEvent.type(screen.getByLabelText('New password'), 'new-secure-pass-456')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'new-secure-pass-456')
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }))

    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeTruthy()
    expect(await screen.findByText('Password reset. Sign in with your new password.')).toBeTruthy()
  })

  it('reports a sign-in setup error after logout instead of staying in a loading state', async () => {
    let csrfRequests = 0
    vi.stubGlobal('fetch', vi.fn((url) => {
      if (url.endsWith('/auth/csrf')) {
        csrfRequests += 1
        return csrfRequests === 1
          ? jsonResponse({ csrf_token: 'csrf-test' })
          : Promise.resolve({ ok: false, json: () => Promise.resolve({}) })
      }
      if (url.endsWith('/auth/me')) {
        return jsonResponse({
          user: { id: 1, name: 'Test User', email: 'test@example.com' },
          csrf_token: 'csrf-test',
        })
      }
      if (url.endsWith('/transcripts')) return jsonResponse([])
      if (url.endsWith('/reports')) return jsonResponse([])
      if (url.endsWith('/auth/logout')) return jsonResponse({ message: 'Signed out.' })
      throw new Error(`Unexpected request: ${url}`)
    }))

    render(<App />)
    await screen.findByText('Signed in as Test User')
    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign-in is unavailable' })).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toMatch(/prepare the sign-in form/i)
  })

  it('allows renaming a session title in Notes and persists the change', async () => {
    let meetings = [
      { id: 10, session_number: 1, title: 'Session 1', transcript: 'Initial discussion.', created_at: '2026-10-20T10:00:00Z' },
    ]
    stubAuthenticatedFetch((url, options = {}) => {
      if (url.endsWith('/transcripts') && (!options.method || options.method === 'GET')) {
        return jsonResponse(meetings)
      }
      if (url.endsWith('/transcripts/10/title') && options.method === 'PATCH') {
        const body = JSON.parse(options.body)
        meetings = [{ ...meetings[0], title: body.title }]
        return jsonResponse({ message: 'Session title updated', id: 10, title: body.title })
      }
      if (url.endsWith('/reports')) return jsonResponse([])
      throw new Error(`Unexpected request: ${url}`)
    })

    render(<App />)
    await screen.findByText('Signed in as Test User')

    const desktopNav = screen.getAllByRole('navigation', { name: 'Main navigation' })[0]
    await userEvent.click(within(desktopNav).getByRole('button', { name: 'Notes' }))
    expect(await screen.findByRole('heading', { name: 'Session 1' })).toBeTruthy()

    const renameButton = screen.getByRole('button', { name: /Rename session Session 1/i })
    await userEvent.click(renameButton)

    const titleInput = screen.getByRole('textbox', { name: 'Session title' })
    await userEvent.clear(titleInput)
    await userEvent.type(titleInput, 'Sprint 42 Kickoff')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('heading', { name: 'Sprint 42 Kickoff' })).toBeTruthy()
  })
})
