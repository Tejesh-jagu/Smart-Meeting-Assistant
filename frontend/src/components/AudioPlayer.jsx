import { useRef, useState } from 'react'
import { formatAudioTime } from '../utils/audio.js'

export default function AudioPlayer({ src, recordedDuration = 0 }) {
  const audioRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const [duration, setDuration] = useState(recordedDuration)
  const [error, setError] = useState('')

  async function togglePlay() {
    const audio = audioRef.current
    if (!audio) return

    try {
      if (audio.paused) await audio.play()
      else audio.pause()
      setError('')
    } catch {
      setError('Could not play this audio. Please record again.')
    }
  }

  function updateDuration(audio) {
    if (Number.isFinite(audio.duration) && audio.duration > 0) {
      setDuration(audio.duration)
    }
  }

  function seekAudio(event) {
    const audio = audioRef.current
    if (!audio || !Number.isFinite(audio.duration)) return

    const nextTime = Number(event.target.value)
    audio.currentTime = nextTime
    setTime(nextTime)
  }

  const progress = duration > 0 ? Math.min((time / duration) * 100, 100) : 0

  return (
    <div className="audio-player">
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onLoadedMetadata={(event) => updateDuration(event.currentTarget)}
        onDurationChange={(event) => updateDuration(event.currentTarget)}
        onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false)
          setTime(0)
        }}
        onError={() => setError('Could not load this audio preview.')}
      />

      <button
        type="button"
        onClick={togglePlay}
        aria-label={playing ? 'Pause audio' : 'Play audio'}
        aria-pressed={playing}
        className="audio-player__toggle"
      >
        {playing ? (
          <svg aria-hidden="true" width="19" height="19" viewBox="0 0 20 20" fill="currentColor">
            <rect x="4" y="3" width="4" height="14" rx="1" />
            <rect x="12" y="3" width="4" height="14" rx="1" />
          </svg>
        ) : (
          <svg aria-hidden="true" width="19" height="19" viewBox="0 0 20 20" fill="currentColor">
            <path d="M6 3.8a1 1 0 0 1 1.5-.86l9 5.2a2.15 2.15 0 0 1 0 3.72l-9 5.2A1 1 0 0 1 6 16.2V3.8Z" />
          </svg>
        )}
      </button>

      <div className="audio-player__timeline">
        <div className="audio-player__seek-wrap">
          <span
            className="audio-player__progress"
            style={{ width: `${progress}%` }}
            aria-hidden="true"
          />
          <input
            className="audio-player__seek"
            type="range"
            min="0"
            max={duration || 1}
            step="0.1"
            value={Math.min(time, duration || 0)}
            disabled={!duration}
            onChange={seekAudio}
            aria-label="Seek through audio"
            aria-valuetext={`${formatAudioTime(time)} of ${formatAudioTime(duration)}`}
          />
        </div>
        <div className="audio-player__labels">
          <span>Audio preview</span>
          <span>{formatAudioTime(time)} elapsed</span>
        </div>
      </div>

      <span className="audio-player__duration" aria-label={`Duration ${formatAudioTime(duration)}`}>
        {formatAudioTime(time)} <span>/</span> {formatAudioTime(duration)}
      </span>

      {error && (
        <span className="audio-player__error" role="alert">
          {error}
        </span>
      )}
    </div>
  )
}