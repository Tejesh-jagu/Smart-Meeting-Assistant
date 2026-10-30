import './utils/matchMediaPolyfill.js'
import { useState } from 'react'
import { motion } from 'motion/react'
import AuthPanel from './components/AuthPanel.jsx'
import RecordingPanel from './components/RecordingPanel.jsx'
import SavedMeetings from './components/SavedMeetings.jsx'
import TranscriptForm from './components/TranscriptForm.jsx'
import useAppController from './hooks/useAppController.js'
import AnimatedHeading from './components/AnimatedHeading.jsx'
import AnimatedButton from './components/ui/AnimatedButton.jsx'
import AnimatedCard from './components/ui/AnimatedCard.jsx'
import AnimatedSelect from './components/ui/AnimatedSelect.jsx'
import GlyphBackgroundDemo from './components/GlyphBackgroundDemo.jsx'

const COPYRIGHT_YEAR = new Date().getFullYear()
const NAV_ITEMS = [
  { id: 'home', label: 'Home' },
  { id: 'ai', label: 'AI' },
  { id: 'notes', label: 'Notes' },
  { id: 'profile', label: 'Profile' },
]
const FILTERS = [
  { id: 'all', label: 'All meetings' },
  { id: 'today', label: 'Today' },
  { id: 'upcoming', label: 'Upcoming' },
]

function AreaIcon({ name }) {
  const paths = {
    home: <><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" /><path d="M8 21v-6h8v6" /></>,
    ai: <><path d="M12 3v3m0 12v3M4.9 4.9 7 7m10 10 2.1 2.1M3 12h3m12 0h3M4.9 19.1 7 17m10-10 2.1-2.1" /><circle cx="12" cy="12" r="4" /></>,
    notes: <><path d="M6 3h9l4 4v14H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /><path d="M14 3v5h5M8 12h8M8 16h8" /></>,
    profile: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  }

  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function meetingDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Date unavailable'
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function isToday(value) {
  const date = new Date(value)
  const now = new Date()
  return !Number.isNaN(date.getTime())
    && date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate()
}

function App() {
  const controller = useAppController()
  const {
    user, authStatus, authError, isLoggingOut, transcript, setTranscript,
    transcriptTitle, setTranscriptTitle, audioTitle, setAudioTitle,
    audioPreviewUrl, recordedDuration, setRecordedDuration, message, isSavingTranscript,
    isUploadingAudio, isRecording, audioInputRef, formattedRecordingTime, messageIsError,
    restoreAuth, handleAuthenticated, logout, submitTranscript, selectAudioFile,
    uploadAudio, startRecording, stopRecording, meetings, filteredMeetings,
    isLoadingMeetings, meetingsLoadError, loadMeetings, reports, isLoadingReports,
    generatingReportId, generateReport, downloadReport, printReport, searchTerm,
    setSearchTerm,
  } = controller
  const [activeArea, setActiveArea] = useState('home')
  const [meetingFilter, setMeetingFilter] = useState('all')
  const [selectedMeetingId, setSelectedMeetingId] = useState('')

  if (authStatus === 'checking') {
    return (
      <main className="auth-shell auth-shell--loading" role="status" aria-live="polite">
        <span className="brand-mark" aria-hidden="true"><AreaIcon name="ai" /></span>
        <span>Restoring your session...</span>
      </main>
    )
  }

  if (authStatus === 'error') {
    return (
      <main className="auth-shell">
        <section className="auth-card" aria-labelledby="auth-error-title">
          <h1 id="auth-error-title">Sign-in is unavailable</h1>
          <p className="auth-feedback auth-feedback--error" role="alert">{authError}</p>
          <button className="button button--primary" type="button" onClick={restoreAuth}>Try again</button>
        </section>
      </main>
    )
  }

  if (!user || authStatus !== 'authenticated') {
    return <AuthPanel csrfToken={controller.csrfToken} onAuthenticated={handleAuthenticated} />
  }

  const selectedMeeting = meetings.find((meeting) => String(meeting.id) === selectedMeetingId) || meetings[0]
  const homeMeetings = filteredMeetings.filter((meeting) => {
    if (meetingFilter === 'today') return isToday(meeting.created_at)
    if (meetingFilter === 'upcoming') return false
    return true
  })

  function openAi(meetingId) {
    setSelectedMeetingId(String(meetingId))
    setActiveArea('ai')
  }

  function renderHome() {
    return (
      <section className="page-view" aria-labelledby="home-title">
        <div className="home-hero">
          <GlyphBackgroundDemo
            glowColor="#2dd4bf"
            shapeColor="#38bdf8"
            fontSize={11}
            interactive={true}
          />
          <div className="home-hero__content">
            <p className="eyebrow">YOUR MEETING WORKSPACE</p>
            <h1 id="home-title">Meeting transcripts<br /><AnimatedHeading /></h1>
            <p className="home-hero__copy">Record a meeting or add a transcript. Review the words, then create a report grounded in the saved session.</p>
            <AnimatedButton asChild className="button button--accent">
              <a href="#capture-tools">Record or upload audio</a>
            </AnimatedButton>
          </div>
          <div className="hero-note" aria-label={isLoadingMeetings ? 'Loading saved sessions' : `${meetings.length} saved meeting sessions`}>
            {isLoadingMeetings ? <span>Loading saved sessions...</span> : <>
              <span className="hero-note__number">{meetings.length}</span>
              <span>{meetings.length === 1 ? 'saved session' : 'saved sessions'}</span>
            </>}
          </div>
        </div>

        <AnimatedCard as="section" className="ongoing-panel" aria-labelledby="ongoing-title" hoverLift={false}>
          <div className="section-title-row">
            <div>
              <p className="eyebrow">LIVE STATUS</p>
              <h2 id="ongoing-title">Ongoing meeting</h2>
            </div>
            <span className={`status-tag${isRecording ? ' status-tag--recording' : ''}`}>
              {isRecording ? 'Recording' : 'No active recording'}
            </span>
          </div>
          {isRecording ? (
            <div className="ongoing-detail" role="status" aria-live="polite">
              <span className="recording-dot" aria-hidden="true" />
              <span>Microphone recording in this browser</span>
              <strong>{formattedRecordingTime}</strong>
              <AnimatedButton className="button button--danger" type="button" onClick={stopRecording}>Stop recording</AnimatedButton>
            </div>
          ) : (
            <p className="muted-copy">No live call is connected. This workspace supports local microphone recording and audio upload, not hosted video meetings.</p>
          )}
        </AnimatedCard>

        <section className="home-meetings" aria-labelledby="home-meetings-title">
          <div className="section-title-row section-title-row--meetings">
            <div>
              <p className="eyebrow">YOUR LIBRARY</p>
              <h2 id="home-meetings-title">Meeting sessions</h2>
            </div>
            <button className="text-button" type="button" onClick={() => setActiveArea('notes')}>View all sessions</button>
          </div>

          <div className="meeting-controls">
            <div className="filter-pills" aria-label="Filter meeting sessions">
              {FILTERS.map((filter) => {
                const isSelected = meetingFilter === filter.id
                return (
                  <button
                    className="filter-pill"
                    key={filter.id}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => setMeetingFilter(filter.id)}
                  >
                    {isSelected && (
                      <motion.span
                        layoutId="activeFilterPill"
                        className="filter-pill__active-indicator"
                        transition={{ type: 'spring', stiffness: 450, damping: 32 }}
                      />
                    )}
                    <span className="filter-pill__label">{filter.label}</span>
                  </button>
                )
              })}
            </div>
            <label className="search-field">
              <span className="sr-only">Search meeting sessions</span>
              <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7"><circle cx="8.8" cy="8.8" r="5.8" /><path d="m13.2 13.2 4 4" /></svg>
              <input
                type="search"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Search sessions or transcript text"
              />
            </label>
          </div>

          {meetingFilter === 'upcoming' ? (
            <div className="state-card" role="status">
              <h3>Upcoming meetings are not connected</h3>
              <p>The current service saves completed transcripts and has no scheduling data to show here.</p>
            </div>
          ) : isLoadingMeetings ? (
            <p className="state-card" role="status" aria-live="polite">Loading your saved sessions...</p>
          ) : meetingsLoadError ? (
            <div className="state-card state-card--error">
              <p role="alert">Could not load sessions: {meetingsLoadError}</p>
              <AnimatedButton className="button button--secondary" type="button" onClick={() => loadMeetings()}>Try again</AnimatedButton>
            </div>
          ) : meetings.length === 0 ? (
            <div className="state-card">
              <h3>No saved sessions yet</h3>
              <p>Record or upload a meeting, or save a transcript to start your library.</p>
            </div>
          ) : homeMeetings.length === 0 ? (
            <div className="state-card">
              <h3>No sessions match your search or filter</h3>
              <p>Try another filter or clear your search.</p>
            </div>
          ) : (
            <ul className="meeting-grid">
              {homeMeetings.slice(0, 3).map((meeting, index) => {
                const report = reports[meeting.id]
                return (
                  <li key={meeting.id}>
                    <AnimatedCard
                      className="meeting-card"
                      aria-labelledby={`home-session-${meeting.id}`}
                      delay={index * 0.05}
                    >
                      <div className="meeting-card__topline">
                        <span className="session-label">{meeting.title ? meeting.title.toUpperCase() : `SESSION ${meeting.session_number}`}</span>
                        <span className={`status-tag${report ? ' status-tag--ready' : ''}`}>
                          {isLoadingReports ? 'Checking report' : report ? 'Report ready' : 'Transcript saved'}
                        </span>
                      </div>
                      <h3 id={`home-session-${meeting.id}`}>{meeting.title || `Session ${meeting.session_number}`}</h3>
                      <time dateTime={meeting.created_at}>{meetingDate(meeting.created_at)}</time>
                      <p className="meeting-card__excerpt">{meeting.transcript.slice(0, 150)}{meeting.transcript.length > 150 ? '…' : ''}</p>
                      <AnimatedButton className="button button--card" type="button" onClick={() => openAi(meeting.id)}>
                        {report ? 'Review report' : 'Open session'}
                      </AnimatedButton>
                    </AnimatedCard>
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        <div id="capture-tools" className="capture-grid">
          <RecordingPanel
            audioTitle={audioTitle}
            setAudioTitle={setAudioTitle}
            audioInputRef={audioInputRef}
            uploadAudio={uploadAudio}
            isUploadingAudio={isUploadingAudio}
            setRecordedDuration={setRecordedDuration}
            selectAudioFile={selectAudioFile}
            isRecording={isRecording}
            formattedRecordingTime={formattedRecordingTime}
            stopRecording={stopRecording}
            audioPreviewUrl={audioPreviewUrl}
            startRecording={startRecording}
            recordedDuration={recordedDuration}
          />
          <TranscriptForm
            title={transcriptTitle}
            onTitleChange={setTranscriptTitle}
            transcript={transcript}
            onChange={setTranscript}
            onSubmit={submitTranscript}
            isSaving={isSavingTranscript}
          />
        </div>
      </section>
    )
  }

  function renderAi() {
    const report = selectedMeeting ? reports[selectedMeeting.id] : null
    const isGenerating = selectedMeeting && generatingReportId === selectedMeeting.id

    return (
      <section className="page-view" aria-labelledby="ai-title">
        <div className="page-heading">
          <p className="eyebrow">TRANSCRIPT-BASED REPORTING</p>
          <h1 id="ai-title">AI workspace</h1>
          <p>Generate or review a report for a saved session. The report uses that session’s transcript; custom report instructions are not supported.</p>
        </div>

        {isLoadingMeetings ? (
          <p className="state-card" role="status">Loading saved sessions...</p>
        ) : meetingsLoadError ? (
          <div className="state-card state-card--error">
            <p role="alert">Could not load sessions: {meetingsLoadError}</p>
            <button className="button button--secondary" type="button" onClick={() => loadMeetings()}>Try again</button>
          </div>
        ) : meetings.length === 0 ? (
          <div className="state-card"><h2>No saved session to report on</h2><p>Save a transcript or transcribe an audio recording first.</p></div>
        ) : (
          <div className="ai-workspace">
            <div className="ai-session-picker">
              <label htmlFor="ai-session">Select a saved session</label>
              <AnimatedSelect
                id="ai-session"
                value={String(selectedMeeting?.id ?? '')}
                onChange={(event) => setSelectedMeetingId(event.target.value)}
              >
                {meetings.map((meeting) => (
                  <option key={meeting.id} value={String(meeting.id)}>{meeting.title || `Session ${meeting.session_number}`} · {meetingDate(meeting.created_at)}</option>
                ))}
              </AnimatedSelect>
            </div>

            {selectedMeeting && (
              <AnimatedCard as="article" className="ai-report-card" aria-labelledby="ai-report-heading">
                <header className="ai-report-card__header">
                  <div>
                    <p className="eyebrow">{selectedMeeting.title ? selectedMeeting.title.toUpperCase() : `SESSION ${selectedMeeting.session_number}`}</p>
                    <h2 id="ai-report-heading">{report ? 'Meeting report' : 'Create a meeting report'}</h2>
                    <p>{meetingDate(selectedMeeting.created_at)}</p>
                  </div>
                  <div className="report-actions">
                    {report && <>
                      <AnimatedButton className="button button--secondary" type="button" onClick={() => downloadReport(selectedMeeting, report)}>Download</AnimatedButton>
                      <AnimatedButton className="button button--secondary" type="button" onClick={() => printReport(selectedMeeting, report)}>Print</AnimatedButton>
                    </>}
                    <AnimatedButton
                      className="button button--primary"
                      type="button"
                      onClick={() => generateReport(selectedMeeting.id)}
                      disabled={isLoadingReports || generatingReportId !== null}
                      aria-busy={Boolean(isGenerating)}
                    >
                      {isGenerating ? 'Generating report...' : report ? 'Regenerate report' : 'Generate report'}
                    </AnimatedButton>
                  </div>
                </header>

                {isLoadingReports ? (
                  <p className="report-state" role="status">Checking for a saved report...</p>
                ) : report ? (
                  <div className="report-content">
                    <section className="report-block report-block--summary" aria-labelledby="report-summary-title">
                      <h3 id="report-summary-title">Summary</h3>
                      <p>{report.summary || 'No summary found.'}</p>
                    </section>
                    <section className="report-block" aria-labelledby="report-decisions-title">
                      <h3 id="report-decisions-title">Decisions</h3>
                      {report.decisions?.length ? <ul>{report.decisions.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul> : <p>No decisions found.</p>}
                    </section>
                    <section className="report-block" aria-labelledby="report-tasks-title">
                      <h3 id="report-tasks-title">Tasks</h3>
                      {report.tasks?.length ? <ul>{report.tasks.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul> : <p>No tasks found.</p>}
                    </section>
                    <details className="source-transcript">
                      <summary>View source transcript</summary>
                      <p>{selectedMeeting.transcript}</p>
                    </details>
                    <p className="report-provenance">
                      {report.generator ? `Generated by ${report.generator}` : 'Generated from the saved transcript'}
                      {report.generated_at ? ` · ${meetingDate(report.generated_at)}` : ''}
                    </p>
                  </div>
                ) : (
                  <p className="report-state">No report is saved for this session yet. Generate one from its transcript.</p>
                )}
              </AnimatedCard>
            )}
          </div>
        )}
      </section>
    )
  }

  function renderNotes() {
    return (
      <section className="page-view" aria-labelledby="notes-title">
        <div className="page-heading">
          <p className="eyebrow">SAVED CONTENT</p>
          <h1 id="notes-title">Notes &amp; transcripts</h1>
          <p>Search and edit saved session transcripts, then review or regenerate their reports.</p>
        </div>
        <p className="capability-note">Sessions currently store one transcript and an optional AI report. Separate personal notes and speaker-labeled transcripts are not supported.</p>
        <SavedMeetings controller={controller} />
      </section>
    )
  }

  function renderProfile() {
    return (
      <section className="page-view" aria-labelledby="profile-title">
        <div className="page-heading">
          <p className="eyebrow">ACCOUNT</p>
          <h1 id="profile-title">Profile</h1>
          <p>Account details and the actions available in this workspace.</p>
        </div>
        <section className="profile-card" aria-labelledby="profile-account-title">
          <div className="profile-card__mark" aria-hidden="true"><AreaIcon name="profile" /></div>
          <div>
            <p className="eyebrow">SIGNED-IN ACCOUNT</p>
            <h2 id="profile-account-title">{user.name}</h2>
            <a className="profile-email" href={`mailto:${user.email}`}>{user.email}</a>
          </div>
          <dl className="profile-details">
            <div><dt>Name</dt><dd>{user.name}</dd></div>
            <div><dt>Email</dt><dd>{user.email}</dd></div>
          </dl>
          <div className="profile-actions">
            <AnimatedButton className="button button--danger" type="button" onClick={logout} disabled={isLoggingOut} aria-busy={isLoggingOut}>
              {isLoggingOut ? 'Signing out...' : 'Sign out'}
            </AnimatedButton>
          </div>
        </section>
        <section className="legal-card" aria-labelledby="legal-title">
          <h2 id="legal-title">Privacy and terms</h2>
          <p>Review how this local application handles meeting content and account data.</p>
          <nav aria-label="Legal information">
            <a href="/privacy.html">Privacy Policy</a>
            <a href="/terms.html">Terms and Conditions</a>
          </nav>
        </section>
      </section>
    )
  }

  const pages = { home: renderHome, ai: renderAi, notes: renderNotes, profile: renderProfile }

  return (
    <main className="workspace-shell">
      <GlyphBackgroundDemo
        glowColor="#2dd4bf"
        shapeColor="#38bdf8"
        fontSize={12}
        interactive={false}
        className="workspace-background-canvas"
      />
      <aside className="workspace-sidebar">
        <a className="workspace-brand" href="/" aria-label="Smart Meeting Assistant home">
          <span className="brand-mark" aria-hidden="true"><AreaIcon name="ai" /></span>
          <span className="workspace-brand__text">Smart Meeting<br />Assistant</span>
        </a>
        <p className="workspace-sidebar__label">WORKSPACE</p>
        <nav className="workspace-nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => {
            const isCurrent = activeArea === item.id
            return (
              <button
                key={item.id}
                className="workspace-nav__button"
                type="button"
                aria-current={isCurrent ? 'page' : undefined}
                onClick={() => setActiveArea(item.id)}
              >
                {isCurrent && (
                  <motion.span
                    layoutId="activeNavPill"
                    className="workspace-nav__active-indicator"
                    transition={{ type: 'spring', stiffness: 450, damping: 35 }}
                  />
                )}
                <span className="workspace-nav__content">
                  <AreaIcon name={item.id} />
                  <span>{item.label}</span>
                </span>
              </button>
            )
          })}
        </nav>
        <div className="workspace-sidebar__footer">
          <span className="user-initial" aria-hidden="true">{user.name.trim().charAt(0).toUpperCase()}</span>
          <span className="workspace-user">{user.name}</span>
        </div>
      </aside>

      <div className="workspace-main">
        <header className="workspace-topbar">
          <span className="workspace-topbar__title">Meeting workspace</span>
          <div className="workspace-topbar__account">
            <span>Signed in as {user.name}</span>
            <AnimatedButton className="button button--top-signout" type="button" onClick={logout} disabled={isLoggingOut} aria-busy={isLoggingOut}>
              {isLoggingOut ? 'Signing out...' : 'Sign out'}
            </AnimatedButton>
          </div>
        </header>

        {message && (
          <p
            className={`app-message ${messageIsError ? 'app-message--error' : 'app-message--status'}`}
            role={messageIsError ? 'alert' : 'status'}
            aria-live={messageIsError ? 'assertive' : 'polite'}
            aria-atomic="true"
          >
            {message}
          </p>
        )}

        <div className="workspace-content" key={activeArea}>
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="workspace-view-transition"
          >
            {pages[activeArea]()}
          </motion.div>
          <footer className="site-footer">
            <span>&copy; {COPYRIGHT_YEAR} Smart Meeting Assistant</span>
            <nav aria-label="Legal information">
              <a href="/privacy.html">Privacy Policy</a>
              <a href="/terms.html">Terms and Conditions</a>
            </nav>
          </footer>
        </div>
      </div>

      <nav className="mobile-nav" aria-label="Main navigation">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className="mobile-nav__button"
            type="button"
            aria-current={activeArea === item.id ? 'page' : undefined}
            onClick={() => setActiveArea(item.id)}
          >
            <AreaIcon name={item.id} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </main>
  )
}

export default App
