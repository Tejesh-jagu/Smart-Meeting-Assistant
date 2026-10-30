import subprocess
from typing import Optional

import imageio_ffmpeg
from groq import APIError, Groq
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile

from .. import runtime

router = APIRouter(tags=["meetings"])


def _transcribe_audio(client, audio_path):
    audio_paths = [audio_path]
    with runtime.tempfile.TemporaryDirectory() as chunk_directory:
        if audio_path.stat().st_size > runtime.MAX_GROQ_AUDIO_UPLOAD_BYTES:
            output_pattern = runtime.Path(chunk_directory) / "chunk-%03d.flac"
            try:
                subprocess.run(
                    [
                        imageio_ffmpeg.get_ffmpeg_exe(),
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(audio_path),
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        "16000",
                        "-c:a",
                        "flac",
                        "-f",
                        "segment",
                        "-segment_time",
                        str(runtime.AUDIO_CHUNK_SECONDS),
                        "-reset_timestamps",
                        "1",
                        str(output_pattern),
                    ],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as error:
                raise HTTPException(
                    status_code=422,
                    detail="Could not process this audio file. Check that it is valid and try again.",
                ) from error

            audio_paths = sorted(runtime.Path(chunk_directory).glob("chunk-*.flac"))
            if not audio_paths:
                raise HTTPException(
                    status_code=422,
                    detail="Could not process this audio file. Check that it is valid and try again.",
                )

        transcript_parts = []
        transcript_length = 0
        for audio_part in audio_paths:
            if audio_part.stat().st_size > runtime.MAX_GROQ_AUDIO_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=500,
                    detail="Audio processing produced a chunk that exceeds the transcription service limit.",
                )
            try:
                with audio_part.open("rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=(audio_part.name, audio_file),
                        language="en",
                    )
            except APIError as error:
                raise HTTPException(
                    status_code=502,
                    detail="Groq could not transcribe the audio. Please try again.",
                ) from error

            text = transcription.text.strip() if isinstance(transcription.text, str) else ""
            if text:
                transcript_length += len(text) + (1 if transcript_parts else 0)
                if transcript_length > runtime.MAX_TRANSCRIPT_CHARACTERS:
                    raise HTTPException(
                        status_code=413,
                        detail="Transcript is too long to save. The maximum length is 200,000 characters.",
                    )
                transcript_parts.append(text)

    return " ".join(transcript_parts)


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
        if request.title:
            row = runtime.save_meeting(connection, user["id"], request.transcript, request.title)
        else:
            row = runtime.save_meeting(connection, user["id"], request.transcript)

    return {
        "message": "Transcript saved in PostgreSQL",
        "id": row[0],
        "session_number": row[1],
        "title": row[2] if len(row) > 2 else f"Session {row[1]}",
    }


@router.patch("/transcripts/{meeting_id}/title")
@router.put("/transcripts/{meeting_id}/title")
def rename_meeting_title(
    meeting_id: int,
    request: runtime.UpdateTitleRequest,
    http_request: Request,
    x_csrf_token: str = Header(),
    user: dict = Depends(runtime.get_current_user),
):
    runtime.require_csrf(http_request, x_csrf_token)
    with runtime.psycopg.connect(**runtime.DB_CONFIG) as connection:
        row = connection.execute(
            """
            UPDATE meetings
            SET title = %s
            WHERE id = %s AND user_id = %s
            RETURNING id, session_number, title
            """,
            (request.title, meeting_id, user["id"]),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Meeting not found")

    return {
        "message": "Session title updated",
        "id": row[0],
        "session_number": row[1],
        "title": row[2] if row[2] else f"Session {row[1]}",
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
    title: Optional[str] = Form(None),
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
    if not runtime.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured.")

    audio_path = None

    try:
        with runtime.tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
            audio_path = runtime.Path(temp_audio.name)
            total_bytes = 0
            while chunk := file.file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > runtime.MAX_AUDIO_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Audio upload is too large. The maximum file size is 200 MB.",
                    )
                temp_audio.write(chunk)
        client = Groq(api_key=runtime.GROQ_API_KEY)
        transcript = _transcribe_audio(client, audio_path)

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
            if title and title.strip():
                row = runtime.save_meeting(connection, user["id"], transcript, title.strip())
            else:
                row = runtime.save_meeting(connection, user["id"], transcript)

        return {
            "message": "Audio transcribed and saved",
            "id": row[0],
            "session_number": row[1],
            "title": row[2] if len(row) > 2 else f"Session {row[1]}",
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
            "SELECT id, session_number, title, transcript, created_at FROM meetings WHERE user_id = %s ORDER BY id DESC",
            (user["id"],),
        ).fetchall()

    for row in rows:
        if not row.get("title"):
            row["title"] = f"Session {row['session_number']}"

    return rows
