export default function TranscriptForm({ transcript, onChange, onSubmit, isSaving }) {
  return (
    <section id="transcript-section" className="transcript-section" aria-labelledby="transcript-title">
      <div className="section-heading">
        <div>
          <p className="section-step">Step 2</p>
          <h2 id="transcript-title">Add a transcript</h2>
          <p id="transcript-help" className="section-description">
            Paste or type an existing transcript, then save it. Audio uploads are transcribed and added directly to saved meetings.
          </p>
        </div>
        <span className="section-note">Manual entry</span>
      </div>
      <form className="transcript-form" onSubmit={onSubmit}>
        <label htmlFor="transcript">Meeting transcript</label>
        <textarea
          id="transcript"
          aria-describedby="transcript-help"
          value={transcript}
          onChange={(event) => onChange(event.target.value)}
          rows="10"
          maxLength={200000}
          required
        />
        <button className="button button--primary" type="submit" disabled={isSaving} aria-busy={isSaving}>
          {isSaving ? 'Saving transcript...' : 'Save transcript'}
        </button>
      </form>
    </section>
  )
}
