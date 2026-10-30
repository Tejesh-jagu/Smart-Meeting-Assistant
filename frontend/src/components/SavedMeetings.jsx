import { useState } from 'react'
import AnimatedButton from './ui/AnimatedButton.jsx'
import AnimatedCard from './ui/AnimatedCard.jsx'
import AnimatedSelect from './ui/AnimatedSelect.jsx'

export default function SavedMeetings({ controller }) {
  const {
    searchTerm, setSearchTerm, isLoadingMeetings, meetingsLoadError, loadMeetings,
    meetings, filteredMeetings, reports, editingMeetingId, editingTranscript,
    setEditingTranscript, startEditing, saveTranscript, cancelEditing,
    generateReport, isLoadingReports, generatingReportId, deleteMeeting,
    downloadReport, printReport,
    editingTitleId, editingTitle, setEditingTitle, isSavingTitle,
    startEditingTitle, cancelEditingTitle, saveTitle,
  } = controller
  const [dateFilter, setDateFilter] = useState({ period: 'all', now: 0 })
  const visibleMeetings = filteredMeetings.filter((meeting) => {
    if (dateFilter.period === 'all') return true
    const createdAt = new Date(meeting.created_at)
    if (Number.isNaN(createdAt.getTime())) return false
    if (dateFilter.period === 'today') {
      const today = new Date(dateFilter.now)
      return createdAt.getFullYear() === today.getFullYear()
        && createdAt.getMonth() === today.getMonth()
        && createdAt.getDate() === today.getDate()
    }
    const age = dateFilter.now - createdAt.getTime()
    return dateFilter.period === 'week' ? age >= 0 && age < 7 * 24 * 60 * 60 * 1000 : age >= 7 * 24 * 60 * 60 * 1000
  })

  return (
    <section id="saved-meetings" className="saved-meetings" aria-labelledby="saved-meetings-title">
      <div className="section-heading">
        <div>
          <p className="section-step">Step 3</p>
          <h2 id="saved-meetings-title">Meeting Sessions</h2>
          <p className="section-description">
            Each saved transcript or transcription is one session. Review its transcript and report here.
          </p>
        </div>
      </div>

      <div className="notes-filter-row">
        <div>
          <label htmlFor="meeting-search">Search Meeting Sessions</label>
          <input
            id="meeting-search"
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search by session number or transcript text"
            aria-describedby="meeting-search-help"
          />
          <p id="meeting-search-help" className="field-help">
            Search session labels and saved transcript text.
          </p>
        </div>
        <div>
          <label htmlFor="meeting-date-filter">Filter by date</label>
          <AnimatedSelect id="meeting-date-filter" value={dateFilter.period} onChange={(event) => setDateFilter({ period: event.target.value, now: Date.now() })}>
            <option value="all">All dates</option>
            <option value="today">Today</option>
            <option value="week">Last 7 days</option>
            <option value="older">Older</option>
          </AnimatedSelect>
        </div>
      </div>

      {isLoadingMeetings ? (
        <p className="state-message" role="status" aria-live="polite">Loading Meeting Sessions...</p>
      ) : meetingsLoadError ? (
        <div className="state-message state-message--error">
          <p role="alert">Could not load Meeting Sessions: {meetingsLoadError}</p>
          <AnimatedButton className="button button--secondary" type="button" onClick={loadMeetings}>Try again</AnimatedButton>
        </div>
      ) : meetings.length === 0 ? (
        <div className="state-message state-message--empty">
          <h3>No Meeting Sessions yet.</h3>
          <p>Saved transcripts and transcribed recordings will appear here.</p>
        </div>
      ) : visibleMeetings.length === 0 ? (
        <div className="state-message state-message--empty">
          <h3>No sessions match these filters.</h3>
          <p>Try a session number, transcript word, or another date range.</p>
        </div>
      ) : (
        <ul className="session-list">
          {visibleMeetings.map((meeting) => {
            const report = reports[meeting.id]
            const isEditing = editingMeetingId === meeting.id
            const hasLongTranscript = meeting.transcript.length > 240
            const transcriptExcerpt = hasLongTranscript
              ? `${meeting.transcript.slice(0, 240).trimEnd()}…`
              : meeting.transcript

            return (
              <li key={meeting.id}>
                <AnimatedCard as="article" className="session-card" aria-labelledby={`session-title-${meeting.id}`}>
                  <header className="session-card__header">
                    <div className="session-card__identity">
                      {editingTitleId === meeting.id ? (
                        <form
                          className="session-title-edit-form"
                          onSubmit={(event) => {
                            event.preventDefault()
                            saveTitle(meeting.id)
                          }}
                        >
                          <label htmlFor={`edit-title-${meeting.id}`} className="sr-only">Session title</label>
                          <div className="session-title-edit-row">
                            <input
                              id={`edit-title-${meeting.id}`}
                              className="session-title-input"
                              type="text"
                              value={editingTitle}
                              onChange={(event) => setEditingTitle(event.target.value)}
                              maxLength={200}
                              placeholder="Session title"
                              autoFocus
                              disabled={isSavingTitle}
                            />
                            <AnimatedButton className="button button--primary button--small" type="submit" disabled={isSavingTitle}>
                              {isSavingTitle ? 'Saving...' : 'Save'}
                            </AnimatedButton>
                            <AnimatedButton className="button button--secondary button--small" type="button" onClick={cancelEditingTitle} disabled={isSavingTitle}>
                              Cancel
                            </AnimatedButton>
                          </div>
                        </form>
                      ) : (
                        <div className="session-card__title-row">
                          <h3 id={`session-title-${meeting.id}`}>{meeting.title || `Session ${meeting.session_number}`}</h3>
                          <button
                            type="button"
                            className="session-rename-btn"
                            onClick={() => startEditingTitle(meeting)}
                            title="Rename session"
                            aria-label={`Rename session ${meeting.title || meeting.session_number}`}
                          >
                            <svg aria-hidden="true" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
                            </svg>
                            <span>Rename</span>
                          </button>
                        </div>
                      )}
                      <time dateTime={meeting.created_at}>{new Date(meeting.created_at).toLocaleString()}</time>
                    </div>
                    <p className={`session-report-status${report ? ' is-ready' : ''}`}>
                      {isLoadingReports ? 'Checking report status' : report ? 'Report available' : 'Report not generated'}
                    </p>
                    <div className="session-card__actions">
                      <AnimatedButton
                        className="button button--primary"
                        type="button"
                        onClick={() => generateReport(meeting.id)}
                        disabled={isLoadingReports || generatingReportId !== null}
                        aria-busy={generatingReportId === meeting.id}
                      >
                        {isLoadingReports
                          ? 'Checking reports...'
                          : generatingReportId === meeting.id
                            ? 'Generating report...'
                            : report
                              ? 'Regenerate AI report'
                              : 'Generate AI report'}
                      </AnimatedButton>
                      <AnimatedButton
                        className="button button--secondary"
                        type="button"
                        onClick={() => startEditingTitle(meeting)}
                        disabled={editingTitleId === meeting.id}
                      >
                        Rename session
                      </AnimatedButton>
                      <AnimatedButton className="button button--danger-quiet" type="button" onClick={() => deleteMeeting(meeting.id)}>
                        Delete session
                      </AnimatedButton>
                    </div>
                  </header>

                  <div className="session-card__excerpt">
                    <p className="session-card__excerpt-label">Transcript excerpt</p>
                    <p>{transcriptExcerpt}</p>
                  </div>

                  <details className="session-details">
                    <summary>Open transcript and report</summary>
                    <div className="session-details__content">
                      {isEditing ? (
                        <div className="transcript-editor">
                          <label htmlFor={`edit-transcript-${meeting.id}`}>Edit transcript</label>
                          <textarea
                            id={`edit-transcript-${meeting.id}`}
                            value={editingTranscript}
                            maxLength={200000}
                            onChange={(event) => setEditingTranscript(event.target.value)}
                            rows="8"
                          />
                          <div className="session-detail-actions">
                            <AnimatedButton className="button button--primary" type="button" onClick={() => saveTranscript(meeting.id)}>
                              Save changes
                            </AnimatedButton>
                            <AnimatedButton className="button button--secondary" type="button" onClick={cancelEditing}>
                              Cancel
                            </AnimatedButton>
                          </div>
                        </div>
                      ) : (
                        <section className="session-transcript" aria-labelledby={`transcript-title-${meeting.id}`}>
                          <h4 id={`transcript-title-${meeting.id}`}>Original transcript</h4>
                          <p>{meeting.transcript}</p>
                          <AnimatedButton className="button button--secondary" type="button" onClick={() => startEditing(meeting)}>
                            Edit transcript
                          </AnimatedButton>
                        </section>
                      )}

                      {report && !isEditing ? (
                        <section className="report-panel" aria-labelledby={`report-title-${meeting.id}`}>
                          <div className="report-panel__header">
                            <div>
                              <h4 id={`report-title-${meeting.id}`}>AI report</h4>
                              <p className="report-meta">
                                Generated by {report.generator || 'AI'}
                                {report.generated_at && ` | ${new Date(report.generated_at).toLocaleString()}`}
                              </p>
                            </div>
                            <div className="report-actions">
                              <AnimatedButton className="button button--secondary" type="button" onClick={() => downloadReport(meeting, report)}>
                                Download report
                              </AnimatedButton>
                              <AnimatedButton className="button button--secondary" type="button" onClick={() => printReport(meeting, report)}>
                                Print report
                              </AnimatedButton>
                            </div>
                          </div>

                          <div className="report-content">
                            <div className="report-block report-block--summary">
                              <h5>Summary</h5>
                              <p>{report.summary || 'No summary available.'}</p>
                            </div>
                            <div className="report-block">
                              <h5>Decisions</h5>
                              {report.decisions?.length > 0 ? (
                                <ul>
                                  {report.decisions.map((decision, index) => <li key={index}>{decision}</li>)}
                                </ul>
                              ) : <p className="report-empty">No decisions found.</p>}
                            </div>
                            <div className="report-block">
                              <h5>Tasks</h5>
                              {report.tasks?.length > 0 ? (
                                <ul>
                                  {report.tasks.map((task, index) => <li key={index}>{task}</li>)}
                                </ul>
                              ) : <p className="report-empty">No tasks found.</p>}
                            </div>
                          </div>
                        </section>
                      ) : !isEditing ? (
                        <section className="session-report-pending" aria-labelledby={`report-title-${meeting.id}`}>
                          <h4 id={`report-title-${meeting.id}`}>AI report</h4>
                          <p>{isLoadingReports ? 'Checking for a saved report.' : 'No report has been generated for this session.'}</p>
                        </section>
                      ) : null}
                    </div>
                  </details>
                </AnimatedCard>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
