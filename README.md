# Smart Meeting Assistant

A local web application for saving meeting transcripts and generating structured reports. The frontend is React/Vite, the backend is FastAPI, PostgreSQL stores transcripts and reports, faster-whisper transcribes uploaded audio, and Ollama generates reports.

This repository is configured for local use. It now has account registration, sign-in, sign-out, protected sessions, and per-account meeting access. **It is not ready for public deployment:** the custom domain is not connected and the legal pages are drafts that still need operator details and review. See [Deployment readiness](#deployment-readiness).

## What the app does

- Save, edit, search, and delete meeting transcripts.
- Review saved transcripts as numbered Meeting Sessions. Each account gets increasing session numbers; deleting a session does not reuse its number.
- Navigate Home, AI, Notes, and Profile to capture sessions, review transcript-based reports, search and edit saved sessions, and manage account/legal links. Upcoming meetings, separate personal notes, speaker labels, and live calls are not stored or connected by the current backend.
- Record audio in a supported browser or select an existing audio/video file.
- Transcribe audio locally with the pretrained faster-whisper `small` model. The backend currently expects English and runs inference on CPU with `int8` computation. This is not a hosted Whisper API and requires no Whisper API key. The model is downloaded the first time it is needed if it is not already cached.
- Generate a report with the configured Ollama model. Reports contain a summary, decisions, and tasks; a grounding step checks report items against the transcript. Review transcripts and reports for recognition errors or omissions before relying on them.
- Store transcripts and reports in PostgreSQL. The uploaded audio is written to a temporary backend file for transcription and the application attempts to delete it after processing; it does not store the original recording in PostgreSQL.

## Requirements

- Python and pip
- Node.js and npm
- PostgreSQL, with a database and user created
- Ollama installed and running on the backend machine, with the configured model pulled

## Configure and run locally (Windows PowerShell)

### 1. Configure PostgreSQL and backend settings

Create a PostgreSQL database and a user that can access it. You can do this in pgAdmin or by connecting to PostgreSQL as an administrator and running SQL like this (replace the example password first):

```sql
CREATE ROLE smart_meeting_user WITH LOGIN PASSWORD 'replace-with-a-strong-password';
CREATE DATABASE smart_meeting_assistant OWNER smart_meeting_user;
```

From the project root, create the backend environment file:

```powershell
Copy-Item backend/.env.example backend/.env
```

Edit `backend/.env` and replace the PostgreSQL placeholders with your local host, port, database name, user, and password. Keep this file private; `.env` files are excluded from Git. Do not paste its contents into issues or chat.

Do not put database credentials, API tokens, or other secrets in frontend environment files: Vite embeds `VITE_*` values in public browser assets. `VITE_API_URL` is a public endpoint address only. Keep backend credentials in `backend/.env` locally and in a host secret manager for any private deployment. `.env` and `.inv` files must not be placed in `frontend/public`.

Set the required database variables in `backend/.env` to the PostgreSQL host, port, database, user, and password you created. The Ollama and CORS variables are optional:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PGHOST` | required | PostgreSQL server host, commonly `localhost` for local development |
| `PGPORT` | required | PostgreSQL port, commonly `5432` |
| `PGDATABASE` | required | Existing PostgreSQL database name |
| `PGUSER` | required | PostgreSQL login role |
| `PGPASSWORD` | required | Password for the PostgreSQL login role |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server address used for report generation |
| `OLLAMA_MODEL` | `llama3.2:3b` | Installed Ollama model name |
| `FRONTEND_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed by CORS |
| `SESSION_COOKIE_SECURE` | `false` | Set to `true` when the API is served over HTTPS |

The database itself must exist before the backend starts. On startup, the backend creates the account, session, rate-limit, meeting, and report tables if missing, then adds the nullable `meetings.user_id` and `meetings.session_number` columns, the per-user `app_users.next_session_number` counter, and indexes. Existing owned meetings receive session numbers ordered by `created_at` and then `id`; if the first account claims unowned legacy meetings, those are numbered in the same chronological order. The migration preserves transcript and report data. Session numbers advance transactionally and are not reduced when a meeting is deleted. Schema changes are applied at startup; a separate migration tool is not used in this version.

For local-only use, configure PostgreSQL to listen on `localhost` and keep `pg_hba.conf` limited to loopback clients. Setting the backend's `PGHOST=localhost` only controls its connection destination; it does not restrict the PostgreSQL server's listening interfaces.

Passwords are stored as Argon2 hashes. The API checks the server-side session cookie on protected requests and stores only SHA-256 hashes of session tokens in PostgreSQL. Transcript and report queries are scoped to the authenticated account. Sign-in is limited after five attempts per client address in 15 minutes; sign-up allows 10 attempts per client address per hour. Audio transcription and report generation are limited to five requests per account per hour with a 60-second gap between accepted requests. Password reset is not available because no email delivery service is configured. The app currently has no admin or paid features.

### 2. Install backend dependencies and start the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull llama3.2:3b
uvicorn main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`. Check `http://127.0.0.1:8000/health` to verify PostgreSQL and the configured Ollama model are reachable. The health route does not load or verify Whisper; Whisper loads on the first audio transcription.

### 3. Install and start the frontend

Open a second PowerShell terminal at the project root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open the local URL printed by Vite, usually `http://localhost:5173`. By default the frontend calls the backend on the same hostname at port `8000`. Set `VITE_API_PORT` in `.env.local` if the backend uses another local port. The same-host default keeps authentication cookies working whether you open `localhost` or `127.0.0.1`. Use `VITE_API_URL` only when you need a specific API origin. If you change `.env.local`, restart Vite. For a production build, set `VITE_API_URL` before running `npm run build`; Vite embeds it in the built frontend. These are frontend settings and belong in `frontend/.env.local` or the frontend host's build environment, not `backend/.env`.

## Audio and transcript behavior

- Uploads accept `.flac`, `.m4a`, `.mp3`, `.mp4`, `.mpeg`, `.mpga`, `.ogg`, `.wav`, `.webm`, and `.wma` file extensions. The maximum upload size is 25 MB.
- The backend transcribes English with faster-whisper `small`, CPU, `int8`, `beam_size=5`, and voice activity detection disabled. Non-English speech may be transcribed incorrectly with the current fixed language setting.
- The first transcription can take longer while the model is downloaded and loaded. The model is pretrained; the project does not fine-tune it on saved meetings.
- A blank result is rejected. Saved transcript text is limited to 200,000 characters.
- Browser microphone access requires permission and a secure browser context; `localhost` is treated as secure by modern browsers.
- Confirm the transcript against the recording before generating or sharing a report. Report generation uses the transcript text, not the original audio.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check PostgreSQL and configured Ollama model availability |
| `GET` | `/auth/csrf` | Prepare the CSRF cookie and token for sign-in or registration |
| `POST` | `/auth/register` | Create an account and sign in |
| `POST` | `/auth/login` | Sign in to an account |
| `GET` | `/auth/me` | Restore the current session |
| `POST` | `/auth/logout` | Revoke the current session |
| `GET` | `/transcripts` | List the signed-in user's saved transcripts, including `session_number` |
| `POST` | `/transcripts` | Save a transcript submitted as JSON and return its `session_number` |
| `POST` | `/transcripts/upload` | Transcribe an uploaded recording, save its transcript, and return its `session_number` |
| `PUT` | `/transcripts/{meeting_id}` | Edit a transcript and remove its previous report |
| `DELETE` | `/transcripts/{meeting_id}` | Delete a meeting and its linked report |
| `GET` | `/reports` | List saved reports |
| `POST` | `/transcripts/{meeting_id}/report` | Generate or regenerate a report with Ollama |

## Data storage, deletion, and backups

PostgreSQL stores transcript text in `meetings` and report fields in `meeting_reports`. Deleting a meeting deletes its linked report. The application does not define an automatic backup retention period, and deleted records may remain in any existing backups. Treat transcripts, reports, database credentials, and backups as sensitive information.

From the `backend` directory, create and verify a PostgreSQL custom-format backup:

```powershell
python database_backup.py backup
```

Backups are written to `backend/backups/`, which is ignored by Git. Restore only to a separate, empty database. The target name must match the confirmation argument exactly:

```powershell
$backup = Get-ChildItem .\backups\*.dump | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
python database_backup.py restore $backup --target-database sma_restore_test --confirm-target sma_restore_test
```

The backup utility refuses to overwrite the configured source database or a target with existing user tables. PostgreSQL command-line tools `pg_dump` and `pg_restore` must be installed and available on `PATH`.

## Validation

Run checks from the specified directories. A successful test run validates the checked behavior for that revision and environment; it does not establish that the application is safe for public deployment.

### Backend tests

From `backend`:

```powershell
python -m unittest discover -s tests -v
```

Unit tests cover authentication, password hashing, unauthenticated access, request throttles, CSRF checks, transcript grounding, report endpoints, credential-safe Ollama errors, mocked database behavior, upload limits, and health checks. PostgreSQL integration tests also cover session numbering, deletion and concurrent saves, per-user usage limits, two-account ownership, and legacy backfill; they are skipped unless `SMART_MEETING_TEST_DATABASE_URL` is set to a dedicated test database. Its database name must contain `test`; the test creates a temporary schema and removes it afterward. Never point test commands at the database containing real meeting data.

### Live Ollama report evaluation

From `backend`, set `SMART_MEETING_TEST_DATABASE_URL` to a dedicated PostgreSQL test database whose name contains `test`, then run:

```powershell
$env:SMART_MEETING_TEST_DATABASE_URL = "postgresql://test_user:test_password@localhost:5432/sma_test"
python evaluate_report_quality.py
```

This calls the configured Ollama model against the cases in `examples/report_evaluation_cases.json`. It creates a uniquely named temporary schema in the test database and drops that schema when it finishes. The database must be reachable, Ollama must be running, and the configured report model must be installed. If a password has URI-reserved characters, URL-encode them in the connection URI.

### Frontend tests and build

From `frontend`:

```powershell
npm test
npm run test:browser
npm run lint
npm run build
```

The Vitest suite checks frontend interactions. The Playwright browser suite uses a generated WAV fixture and mocked API responses to check audio playback, seeking, duration, transcript saving, and report UI behavior. Install Chromium once if needed:

```powershell
npx playwright install chromium
```

### Manual local smoke check

1. Start PostgreSQL, Ollama, the backend, and the frontend.
2. Open `/health` and confirm it reports both the database and Ollama as available.
3. Save a transcript, generate a report, edit the transcript, regenerate the report, then delete the meeting.
4. Upload a short English recording. Check the transcript against the audio before generating its report.
5. Try [`examples/sample_transcript.txt`](examples/sample_transcript.txt). It has one explicit decision and two promised follow-ups; its dashboard idea is discussion only.
6. Confirm the audio player works and review the privacy and terms pages at `/privacy.html` and `/terms.html`.

The repository includes focused backend, frontend, and live-model validation code. Re-run the relevant checks against the exact revision and machine you intend to release; do not rely on an old test count or a prior local run as current release evidence.

## Deployment readiness

**Current scope: local use. Public deployment is not ready.** Authentication and account-level meeting access are implemented, but they still need review on a private staging deployment. The custom domain is not connected, legal pages need operator details and review, and production HTTPS, secret storage, backups, monitoring, and hosting configuration remain. Keep the backend and database on the local machine or a private network; do not expose the API or Ollama port `11434` to the public internet.

Before any public launch, complete and verify all of the following:

- Verify on private staging that two users cannot access each other's meetings and that unauthenticated requests fail; check session, CSRF, rate-limit, and HTTPS cookie settings in the deployed topology.
- Choose and configure hosting, connect the custom domain, and serve the site and API over HTTPS.
- Keep PostgreSQL private and store credentials in the host's secret manager. Do not commit `.env` or `.inv` files or put them in the frontend public folder.
- Bind PostgreSQL only to the private interface(s) used by the API host and restrict both `pg_hba.conf` and the host firewall to those clients.
- Install Ollama and the selected report model on a backend-reachable machine, or choose and document a suitable private model service. Ensure the backend host has enough memory, CPU, and disk for Ollama and faster-whisper.
- Set `VITE_API_URL` to the deployed HTTPS API URL at frontend build time. Set `FRONTEND_ORIGINS` to the exact deployed frontend origin(s); do not use `*`.
- Run the API behind a production ASGI server and HTTPS reverse proxy. Do not use `uvicorn --reload` in production. Configure request limits at the proxy as well as the application's 25 MB upload limit.
- Configure encrypted, access-controlled PostgreSQL backups, a documented retention period, monitoring, and a tested restore procedure. Define how deletion applies to backups.
- Complete the draft [Privacy Policy](frontend/public/privacy.html) and [Terms and Conditions](frontend/public/terms.html): add the responsible operator's legal name and contact, applicable jurisdiction, backup retention details, and obtain appropriate legal review for the actual service and hosting.
- Configure the static host to serve the provided [404 page](frontend/public/404.html). Keep the provided [favicon](frontend/public/favicon.svg) in the production build and confirm the final build has no unwanted "Made with AI" label.
- Recheck access controls, privacy disclosures, mobile behavior, links, error/success messages, audio transcription, report generation, backups, and rollback on a private staging deployment before launch.

If the deployment host or model service changes, update the privacy policy, terms, and data-flow documentation to match. Meeting transcripts and reports are sensitive; decide access, retention, and deletion rules before storing real recordings.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Backend will not start | Confirm `backend/.env` exists and PostgreSQL settings are set; make sure PostgreSQL is running and the configured database/user exist. |
| `/health` reports PostgreSQL unavailable | Check PostgreSQL service, host, port, database name, username, and password. |
| `/health` reports Ollama unavailable | Start Ollama and check `OLLAMA_BASE_URL`. |
| Configured model is missing | Run `ollama list`; pull the configured model, for example `ollama pull llama3.2:3b`, and ensure `OLLAMA_MODEL` matches its installed name. |
| First audio upload is slow | faster-whisper may be downloading or loading its `small` model. Later requests reuse the model in the backend process. |
| Transcript is empty or inaccurate | Check that the file is supported, speech is audible and in English, and the upload is within 25 MB. Review the transcript against the recording. |
| Browser cannot record | Grant microphone permission and use `localhost` or another secure browser context. |
| Report generation fails | Check Ollama connectivity and the configured model. If the model returns an error or invalid response, the API reports a generation failure; inspect the backend logs without copying transcript contents into them. |

## Project map

- `backend/main.py`: stable `uvicorn main:app` entry point and compatibility exports
- `backend/app/main.py`: FastAPI setup, middleware, request validation, and route registration
- `backend/app/config.py`: backend `.env` loading and environment-backed settings
- `backend/app/runtime.py`: database schema, shared security helpers, and model resources
- `backend/app/api/`: auth, health, meetings, and reports route modules
- `backend/report_safety.py`: transcript-grounding and report sanitization
- `backend/tests/`: backend unit and optional database integration tests
- `backend/evaluate_report_quality.py`: isolated live-model quality evaluation
- `backend/database_backup.py`: PostgreSQL backup and guarded restore utility
- `frontend/src/App.jsx`: workspace areas, page composition, and top-level auth states
- `frontend/src/api/`: API origin, CSRF request handling, and response errors
- `frontend/src/hooks/useAppController.js`: application state and workflow actions
- `frontend/src/components/`: auth, transcript, recording, player, and saved-meeting UI
- `frontend/src/utils/audio.js`: browser audio formatting and WAV encoding
- `frontend/src/`: styles and frontend tests
- `frontend/browser-tests/`: Playwright browser checks
- `examples/`: sample meeting transcript and report evaluation cases

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module boundaries and change conventions.
