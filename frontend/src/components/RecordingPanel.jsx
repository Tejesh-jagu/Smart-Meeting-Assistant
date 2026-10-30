import AudioPlayer from './AudioPlayer.jsx'
import AnimatedButton from './ui/AnimatedButton.jsx'

export default function RecordingPanel({
  audioTitle = '',
  setAudioTitle,
  audioInputRef,
  uploadAudio,
  isUploadingAudio,
  setRecordedDuration,
  selectAudioFile,
  isRecording,
  formattedRecordingTime,
  stopRecording,
  audioPreviewUrl,
  startRecording,
  recordedDuration,
}) {
  return (
      <section id="record-audio" className="record-card" aria-labelledby="record-title">
        <div className="section-heading">
          <div>
            <p className="section-step">Step 1</p>
            <h2 id="record-title">Record or upload audio</h2>
            <p className="section-description">
              Choose Transcribe audio to save the transcript. You can preview a recording before sending it for transcription.
            </p>
          </div>
        </div>

        <form onSubmit={uploadAudio}>
          <label htmlFor="audio-title">Session title (optional)</label>
          <input
            id="audio-title"
            type="text"
            placeholder="e.g. Design Review, Team Interview (defaults to Session #)"
            value={audioTitle}
            onChange={(event) => setAudioTitle?.(event.target.value)}
            maxLength={200}
            disabled={isUploadingAudio}
          />
          <label htmlFor="audio">Choose an audio file</label>
          <input
            ref={audioInputRef}
            id="audio"
            type="file"
            accept="audio/*,video/*"
            aria-describedby="audio-file-help"
            disabled={isUploadingAudio}
            onChange={(event) => {
              setRecordedDuration(0)
              selectAudioFile(event.target.files?.[0] || null)
            }}
          />
          <p id="audio-file-help" className="field-help">
            Maximum file size: 200 MB. Files larger than 25 MB are split into chunks for transcription.
          </p>

          {isRecording ? (
            <div className="recording-status">
              <div>
                <div className="recording-status__label">
                  <span className="recording-dot" aria-hidden="true" /> Recording
                </div>

                <div className="recording-status__time">
                  {formattedRecordingTime}
                </div>
              </div>

              <AnimatedButton
                type="button"
                onClick={stopRecording}
                disabled={isUploadingAudio}
                className="button button--danger"
              >
                Stop recording
              </AnimatedButton>
            </div>
          ) : (
            <div className="audio-selection">
              {audioPreviewUrl ? (
                <div className="audio-preview-card">
                  <p className="audio-preview-card__title"><strong>Audio preview</strong></p>

                  <AudioPlayer
                    key={audioPreviewUrl}
                    src={audioPreviewUrl}
                    recordedDuration={recordedDuration}
                  />
                </div>
              ) : (
                <AnimatedButton
                  type="button"
                  onClick={startRecording}
                  disabled={isUploadingAudio}
                  className="button button--primary recording-start-button"
                >
                  <span className="recording-start-button__icon" aria-hidden="true" />
                  Start recording
                </AnimatedButton>
              )}

              {audioPreviewUrl && (
                <div className="audio-actions">
                  <AnimatedButton
                    type="button"
                    onClick={startRecording}
                    disabled={isUploadingAudio}
                    className="button button--secondary"
                  >
                    Record again
                  </AnimatedButton>

                  <AnimatedButton
                    type="submit"
                    disabled={isUploadingAudio}
                    aria-busy={isUploadingAudio}
                    className="button button--primary"
                  >
                    {isUploadingAudio ? 'Transcribing audio...' : 'Transcribe audio'}
                  </AnimatedButton>
                </div>
              )}
            </div>
          )}
        </form>
      </section>
  )
}
