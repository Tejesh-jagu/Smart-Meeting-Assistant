from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile

from .. import runtime

router = APIRouter(tags=["meetings"])


@router.get("/")
def home():
    return {"message": "Smart Meeting Assistant backend is running"}


@router.post("/transcripts")
def receive_transcript(
    http_request: Request,
    request: runtime.TranscriptRequest,
    x_csrf_token: str = Header(),
    user: dict = Depends(runtime.get_current_user),
):
    runtime.require_csrf(http_request, x_csrf_token)
    with runtime.psycopg.connect(**runtime.DB_CONFIG) as connection:
        row = runtime.save_meeting(connection, user["id"], request.transcript)

    return {
        "message": "Transcript saved in PostgreSQL",
        "id": row[0],
        "session_number": row[1],
    }


@router.put("/transcripts/{meeting_id}")
def update_transcript(
    meeting_id: int,
    request: runtime.TranscriptRequest,
    http_request: Request,
    x_csrf_token: str = Header(),
    user: dict = Depends(runtime.get_current_user),
):
    runtime.require_csrf(http_request, x_csrf_token)
    with runtime.psycopg.connect(**runtime.DB_CONFIG) as connection:
        row = connection.execute(
            """
            UPDATE meetings
            SET transcript = %s
            WHERE id = %s AND user_id = %s
            RETURNING id
            """,
            (request.transcript, meeting_id, user["id"]),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Meeting not found")

        connection.execute(
            "DELETE FROM meeting_reports WHERE meeting_id = %s",
            (meeting_id,),
        )

    return {
        "message": "Transcript updated. Generate a new report when ready.",
        "id": row[0],
    }


@router.delete("/transcripts/{meeting_id}")
def delete_transcript(
    meeting_id: int,
    request: Request,
    x_csrf_token: str = Header(),
    user: dict = Depends(runtime.get_current_user),
):
    runtime.require_csrf(request, x_csrf_token)
    with runtime.psycopg.connect(**runtime.DB_CONFIG) as connection:
        row = connection.execute(
            """
            DELETE FROM meetings
            WHERE id = %s AND user_id = %s
            RETURNING id
            """,
            (meeting_id, user["id"]),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Meeting not found")

    return {
        "message": "Meeting and its report deleted",
        "id": row[0],
    }


@router.post("/transcripts/upload")
def upload_audio(
    request: Request,
    file: UploadFile = File(...),
    x_csrf_token: str = Header(),
    user: dict = Depends(runtime.get_current_user),
):
    runtime.require_csrf(request, x_csrf_token)
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Please choose an audio file.",
        )

    suffix = runtime.Path(file.filename).suffix.lower()
    if suffix not in runtime.ALLOWED_AUDIO_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio format. Choose WAV, MP3, M4A, MP4, OGG, FLAC, WEBM, MPEG, or WMA.",
        )

    audio_path = None

    try:
        with runtime.psycopg.connect(**runtime.DB_CONFIG) as connection:
            transcription_allowed = runtime.consume_rate_limit(
                connection,
                f"transcription:{user['id']}",
                runtime.AI_REQUESTS_PER_HOUR,
                60 * 60,
                runtime.AI_REQUEST_COOLDOWN_SECONDS,
            )
        if not transcription_allowed:
            raise HTTPException(
                status_code=429,
                detail="Audio transcription is temporarily limited. Wait before trying again.",
            )

        with runtime.tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
            audio_path = runtime.Path(temp_audio.name)
            total_bytes = 0
            while chunk := file.file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > runtime.MAX_AUDIO_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Audio upload is too large. The maximum file size is 25 MB.",
                    )
                temp_audio.write(chunk)
        model = runtime.get_whisper_model()

        # Turn VAD off because it can filter out quiet or short recordings.
        segments, _ = model.transcribe(
            str(audio_path),
            language="en",
            beam_size=5,
            vad_filter=False,
        )

        transcript = " ".join(
            segment.text.strip() for segment in segments
        ).strip()

        if not transcript:
            raise HTTPException(
                status_code=422,
                detail="No speech was recognized. Please check that your voice is audible in the recording.",
            )

        if len(transcript) > runtime.MAX_TRANSCRIPT_CHARACTERS:
            raise HTTPException(
                status_code=413,
                detail="Transcript is too long to save. The maximum length is 200,000 characters.",
            )

        with runtime.psycopg.connect(**runtime.DB_CONFIG) as connection:
            row = runtime.save_meeting(connection, user["id"], transcript)

        return {
            "message": "Audio transcribed and saved",
            "id": row[0],
            "session_number": row[1],
            "transcript": transcript,
        }

    finally:
        if audio_path is not None:
            audio_path.unlink(missing_ok=True)
        file.file.close()


@router.get("/transcripts")
def list_transcripts(user: dict = Depends(runtime.get_current_user)):
    with runtime.psycopg.connect(**runtime.DB_CONFIG, row_factory=runtime.dict_row) as connection:
        rows = connection.execute(
            "SELECT id, session_number, transcript, created_at FROM meetings WHERE user_id = %s ORDER BY id DESC",
            (user["id"],),
        ).fetchall()

    return rows


