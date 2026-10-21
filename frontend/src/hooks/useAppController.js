import { useEffect, useRef, useState } from 'react'
import { API_URL, createApiClient, readApiJson } from '../api/client.js'
import { makeWavBlob } from '../utils/audio.js'

export default function useAppController() {
  const [user, setUser] = useState(null)
  const [csrfToken, setCsrfToken] = useState('')
  const [authStatus, setAuthStatus] = useState('checking')
  const [authError, setAuthError] = useState('')
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [audioFile, setAudioFile] = useState(null)
  const [audioPreviewUrl, setAudioPreviewUrl] = useState('')
  const [recordedDuration, setRecordedDuration] = useState(0)
  const [message, setMessage] = useState('')
  const [meetings, setMeetings] = useState([])
  const [isLoadingMeetings, setIsLoadingMeetings] = useState(true)
  const [meetingsLoadError, setMeetingsLoadError] = useState('')
  const [isLoadingReports, setIsLoadingReports] = useState(true)
  const [isSavingTranscript, setIsSavingTranscript] = useState(false)
  const [isUploadingAudio, setIsUploadingAudio] = useState(false)
  const [reports, setReports] = useState({})
  const [generatingReportId, setGeneratingReportId] = useState(null)
  const [editingMeetingId, setEditingMeetingId] = useState(null)
  const [editingTranscript, setEditingTranscript] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)

  const audioContextRef = useRef(null)
  const streamRef = useRef(null)
  const sourceRef = useRef(null)
  const processorRef = useRef(null)
  const muteGainRef = useRef(null)
  const pcmChunksRef = useRef([])
  const audioInputRef = useRef(null)

  const normalizedSearchTerm = searchTerm.trim().toLowerCase()
  const filteredMeetings = meetings.filter((meeting) =>
    `session ${meeting.session_number}`.toLowerCase().includes(normalizedSearchTerm)
    || meeting.transcript.toLowerCase().includes(normalizedSearchTerm)
  )

  const formattedRecordingTime = `${String(
    Math.floor(recordingSeconds / 60)
  ).padStart(2, '0')}:${String(recordingSeconds % 60).padStart(2, '0')}`
  const messageIsError = /^(error:|could not|microphone recording is not|audio recording is not|no audio was captured|transcript cannot|choose a file or record audio first|allow pop-ups)/i.test(message)

  useEffect(() => {
    if (!audioPreviewUrl) return
    return () => URL.revokeObjectURL(audioPreviewUrl)
  }, [audioPreviewUrl])

  useEffect(() => {
    if (!isRecording) return

    const timer = window.setInterval(() => {
      setRecordingSeconds((seconds) => seconds + 1)
    }, 1000)

    return () => window.clearInterval(timer)
  }, [isRecording])

  async function restoreAuth() {
    setAuthStatus('checking')
    setAuthError('')
    try {
      const csrfResponse = await fetch(`${API_URL}/auth/csrf`, { credentials: 'include' })
      const csrfResult = await readApiJson(csrfResponse, 'Could not connect to the authentication service.')

      const response = await fetch(`${API_URL}/auth/me`, { credentials: 'include' })
      if (response.status === 401) {
        setUser(null)
        setCsrfToken(csrfResult.csrf_token)
        setAuthStatus('guest')
        return
      }
      const result = await readApiJson(response, 'Could not restore your session.')

      setUser(result.user)
      setCsrfToken(result.csrf_token)
      setAuthStatus('authenticated')
      loadMeetings(false)
      loadReports(false)
    } catch (error) {
      setAuthError(error.message || 'Could not connect to the backend.')
      setAuthStatus('error')
    }
  }

  const initialRestoreAuth = useRef(restoreAuth)
  useEffect(() => {
    initialRestoreAuth.current()
  }, [])

  const apiFetch = createApiClient(
    () => csrfToken,
    async () => {
      setUser(null)
      try {
        const csrfResponse = await fetch(`${API_URL}/auth/csrf`, { credentials: 'include' })
        const result = await readApiJson(csrfResponse, 'Could not refresh the sign-in page.')
        setCsrfToken(result.csrf_token)
        setAuthStatus('guest')
      } catch {
        setAuthStatus('error')
        setAuthError('Could not connect to the backend.')
      }
    }
  )

  function handleAuthenticated(result, registered) {
    setIsLoadingMeetings(true)
    setIsLoadingReports(true)
    setMeetingsLoadError('')
    setUser(result.user)
    setCsrfToken(result.csrf_token)
    setAuthStatus('authenticated')
    setMessage(registered ? 'Account created. You are signed in.' : '')
    loadMeetings(false)
    loadReports(false)
  }

  async function logout() {
    setIsLoggingOut(true)
    let signedOut = false
    try {
      const response = await apiFetch(`${API_URL}/auth/logout`, { method: 'POST' })
      await readApiJson(response, 'Could not sign out.')

      setAuthStatus('checking')
      setUser(null)
      signedOut = true
      setMeetings([])
      setReports({})
      setMessage('')
      const csrfResponse = await fetch(`${API_URL}/auth/csrf`, { credentials: 'include' })
      const csrfResult = await readApiJson(csrfResponse, 'Signed out, but could not prepare the sign-in form.')
      setCsrfToken(csrfResult.csrf_token)
      setAuthStatus('guest')
    } catch (error) {
      if (signedOut) {
        setAuthError(error.message)
        setAuthStatus('error')
      } else {
        setMessage(`Error: ${error.message}`)
      }
    } finally {
      setIsLoggingOut(false)
    }
  }

  async function loadMeetings(showLoading = true) {
    if (showLoading) {
      setIsLoadingMeetings(true)
      setMeetingsLoadError('')
    }
    try {
      const response = await apiFetch(`${API_URL}/transcripts`)
      setMeetings(await readApiJson(response, 'Could not load saved meetings.'))
    } catch (error) {
      setMeetingsLoadError(error.message)
      setMessage(`Error: ${error.message}`)
    } finally {
      setIsLoadingMeetings(false)
    }
  }

  async function loadReports(showLoading = true) {
    if (showLoading) setIsLoadingReports(true)
    try {
      const response = await apiFetch(`${API_URL}/reports`)
      const savedReports = await readApiJson(response, 'Could not load saved reports.')
      const reportsByMeetingId = Object.fromEntries(
        savedReports.map((report) => [report.meeting_id, report])
      )

      setReports(reportsByMeetingId)
    } catch (error) {
      setMessage(`Error: ${error.message}`)
    } finally {
      setIsLoadingReports(false)
    }
  }

  async function submitTranscript(event) {
    event.preventDefault()
    setIsSavingTranscript(true)
    setMessage('Saving transcript...')

    try {
      const response = await apiFetch(`${API_URL}/transcripts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript }),
      })

      const result = await readApiJson(response, 'Could not save the transcript.')

      setMessage(result.message)
      setTranscript('')
      await loadMeetings()
    } catch (error) {
      setMessage(`Error: ${error.message}`)
    } finally {
      setIsSavingTranscript(false)
    }
  }

  function clearAudioSelection() {
    setAudioFile(null)
    setAudioPreviewUrl('')
    setRecordedDuration(0)

    if (audioInputRef.current) {
      audioInputRef.current.value = ''
    }
  }

  function selectAudioFile(file) {
    setAudioFile(file)
    setAudioPreviewUrl(file ? URL.createObjectURL(file) : '')
  }

  async function uploadAudio(event) {
    event.preventDefault()

    if (!audioFile) {
      setMessage('Choose a file or record audio first.')
      return
    }

    const form = event.currentTarget
    const formData = new FormData()
    formData.append('file', audioFile)

    setMessage('Transcribing audio and saving transcript...')
    setIsUploadingAudio(true)

    try {
      const response = await apiFetch(`${API_URL}/transcripts/upload`, {
        method: 'POST',
        body: formData,
      })

      const result = await readApiJson(response, 'Could not transcribe the audio.')

      setMessage(result.message)
      clearAudioSelection()
      form.reset()
      await loadMeetings()
    } catch (error) {
      setMessage(`Error: ${error.message}`)
    } finally {
      setIsUploadingAudio(false)
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMessage('Microphone recording is not supported in this browser.')
      return
    }

    const AudioContextClass =
      window.AudioContext || window.webkitAudioContext

    if (!AudioContextClass) {
      setMessage('Audio recording is not supported in this browser.')
      return
    }

    let stream
    let context

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      context = new AudioContextClass()
      await context.resume()

      const source = context.createMediaStreamSource(stream)
      const processor = context.createScriptProcessor(4096, 1, 1)
      const muteGain = context.createGain()

      muteGain.gain.value = 0
      pcmChunksRef.current = []

      processor.onaudioprocess = (event) => {
        pcmChunksRef.current.push(
          new Float32Array(event.inputBuffer.getChannelData(0))
        )
      }

      source.connect(processor)
      processor.connect(muteGain)
      muteGain.connect(context.destination)

      audioContextRef.current = context
      streamRef.current = stream
      sourceRef.current = source
      processorRef.current = processor
      muteGainRef.current = muteGain

      clearAudioSelection()
      setRecordingSeconds(0)
      setIsRecording(true)
      setMessage('Recording in progress...')
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop())

      if (context && context.state !== 'closed') {
        context.close().catch(() => {})
      }

      setIsRecording(false)
      setMessage(`Could not start recording: ${error.message}`)
    }
  }

  function stopRecording() {
    const context = audioContextRef.current
    const processor = processorRef.current

    if (!context || !processor) return

    processor.onaudioprocess = null

    try {
      sourceRef.current?.disconnect()
      processor.disconnect()
      muteGainRef.current?.disconnect()
    } catch {
      // Audio nodes may already be disconnected.
    }

    const chunks = pcmChunksRef.current
    const sampleRate = context.sampleRate
    pcmChunksRef.current = []

    streamRef.current?.getTracks().forEach((track) => track.stop())

    if (context.state !== 'closed') {
      context.close().catch(() => {})
    }

    audioContextRef.current = null
    streamRef.current = null
    sourceRef.current = null
    processorRef.current = null
    muteGainRef.current = null
    setIsRecording(false)

    const wavBlob = makeWavBlob(chunks, sampleRate)

    if (wavBlob.size <= 44) {
      setMessage('No audio was captured. Please record again.')
      return
    }

    const duration = (wavBlob.size - 44) / (16000 * 2)
    const wavFile = new File(
      [wavBlob],
      `meeting-recording-${Date.now()}.wav`,
      { type: 'audio/wav' }
    )

    setRecordedDuration(duration)
    selectAudioFile(wavFile)
    setMessage('Recording ready. Play it back, then transcribe when ready.')
  }

  function startEditing(meeting) {
    setEditingMeetingId(meeting.id)
    setEditingTranscript(meeting.transcript)
  }

  function cancelEditing() {
    setEditingMeetingId(null)
    setEditingTranscript('')
  }

  async function saveTranscript(meetingId) {
    if (!editingTranscript.trim()) {
      setMessage('Transcript cannot be empty.')
      return
    }

    setMessage('Updating transcript...')

    try {
      const response = await apiFetch(`${API_URL}/transcripts/${meetingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: editingTranscript }),
      })

      const result = await readApiJson(response, 'Could not update the transcript.')

      setReports((currentReports) => {
        const updatedReports = { ...currentReports }
        delete updatedReports[meetingId]
        return updatedReports
      })

      setMessage(result.message)
      cancelEditing()
      await loadMeetings()
    } catch (error) {
      setMessage(`Error: ${error.message}`)
    }
  }

  async function deleteMeeting(meetingId) {
    const confirmed = window.confirm(
      'Delete this meeting and its report permanently?'
    )

    if (!confirmed) return

    setMessage('Deleting meeting...')

    try {
      const response = await apiFetch(`${API_URL}/transcripts/${meetingId}`, {
        method: 'DELETE',
      })

      const result = await readApiJson(response, 'Could not delete the meeting.')

      setReports((currentReports) => {
        const updatedReports = { ...currentReports }
        delete updatedReports[meetingId]
        return updatedReports
      })

      if (editingMeetingId === meetingId) {
        cancelEditing()
      }

      setMessage(result.message)
      await loadMeetings()
    } catch (error) {
      setMessage(`Error: ${error.message}`)
    }
  }

  async function generateReport(meetingId) {
    setGeneratingReportId(meetingId)
    setMessage('Generating AI report...')

    try {
      const response = await apiFetch(
        `${API_URL}/transcripts/${meetingId}/report`,
        { method: 'POST' }
      )

      const report = await readApiJson(response, 'Could not generate the report.')

      setReports((currentReports) => ({
        ...currentReports,
        [meetingId]: report,
      }))

      setMessage('AI report ready.')
    } catch (error) {
      setMessage(`Error: ${error.message}`)
    } finally {
      setGeneratingReportId(null)
    }
  }

  function printReport(meeting, report) {
    const escapeHtml = (value) =>
      String(value ?? '').replace(/[&<>"']/g, (character) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[character])

    const makeList = (items) =>
      items?.length
        ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
        : '<li>None</li>'

    const printWindow = window.open('', '_blank', 'width=800,height=600')

    if (!printWindow) {
      setMessage('Allow pop-ups for this page, then try again.')
      return
    }

    printWindow.document.write(`
      <!doctype html>
      <html>
        <head>
          <title>Meeting report ${meeting.id}</title>
          <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #1f2937; line-height: 1.6; }
            h1, h2 { color: #1e3a8a; }
            .transcript { white-space: pre-wrap; }
            @media print { body { margin: 20mm; } }
          </style>
        </head>
        <body>
          <h1>Smart Meeting Assistant</h1>
          <p>${escapeHtml(new Date(meeting.created_at).toLocaleString())}</p>
          <h2>Transcript</h2>
          <p class="transcript">${escapeHtml(meeting.transcript)}</p>
          <h2>Summary</h2>
          <p>${escapeHtml(report.summary || 'No summary available.')}</p>
          <h2>Decisions</h2>
          <ul>${makeList(report.decisions)}</ul>
          <h2>Tasks</h2>
          <ul>${makeList(report.tasks)}</ul>
        </body>
      </html>
    `)

    printWindow.document.close()
    printWindow.focus()
    setTimeout(() => printWindow.print(), 500)
  }

  function downloadReport(meeting, report) {
    const reportText = [
      'Smart Meeting Assistant - Meeting Report',
      `Date: ${new Date(meeting.created_at).toLocaleString()}`,
      '',
      'Transcript',
      meeting.transcript,
      '',
      'Summary',
      report.summary || 'No summary available.',
      '',
      'Decisions',
      ...(report.decisions?.length
        ? report.decisions.map((decision) => `- ${decision}`)
        : ['None']),
      '',
      'Tasks',
      ...(report.tasks?.length
        ? report.tasks.map((task) => `- ${task}`)
        : ['None']),
    ].join('\n')

    const file = new Blob([reportText], {
      type: 'text/plain;charset=utf-8',
    })
    const url = URL.createObjectURL(file)
    const link = document.createElement('a')

    link.href = url
    link.download = `meeting-report-${meeting.id}.txt`
    link.click()

    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }


  return {
    user, csrfToken, authStatus, authError, isLoggingOut, transcript, setTranscript, audioPreviewUrl,
    recordedDuration, setRecordedDuration, message, meetings, isLoadingMeetings,
    meetingsLoadError, isLoadingReports, isSavingTranscript, isUploadingAudio, reports,
    generatingReportId, editingMeetingId, editingTranscript, setEditingTranscript,
    searchTerm, setSearchTerm, isMenuOpen, setIsMenuOpen, isRecording, recordingSeconds,
    audioInputRef, filteredMeetings, formattedRecordingTime, messageIsError, restoreAuth,
    handleAuthenticated, logout, submitTranscript, selectAudioFile,
    uploadAudio, startRecording, stopRecording, startEditing, cancelEditing,
    saveTranscript, deleteMeeting, generateReport, printReport, downloadReport, loadMeetings,
  }
}
