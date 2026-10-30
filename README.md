# Smart Meeting Assistant

A local web application for saving meeting transcripts and generating structured reports. The frontend is React/Vite, the backend is FastAPI, PostgreSQL stores transcripts and reports, and Groq's hosted Whisper and Llama APIs transcribe audio and generate reports.

This repository is configured for local use. It now has account registration, sign-in, sign-out, protected sessions, and per-account meeting access. **It is not ready for public deployment:** the custom domain is not connected and the legal pages are drafts that still need operator details and review. See [Deployment readiness](#deployment-readiness).

## What the app does

- Save, edit, search, and delete meeting transcripts.
- Review saved transcripts as numbered Meeting Sessions. Each account gets increasing session numbers; deleting a session does not reuse its number.
- Navigate Home, AI, Notes, and Profile to capture sessions, review transcript-based reports, search and edit saved sessions, and manage account/legal links. Upcoming meetings, separate personal notes, speaker labels, and live calls are not stored or connected by the current backend.
- Record audio in a supported browser or select an existing audio/video file.
- Transcribe English audio with Groq's hosted `whisper-large-v3` API and generate reports with the configured Groq model. Set `GROQ_API_KEY` in the backend environment. Audio and meeting transcripts are sent to Groq for processing; review its data-handling terms before uploading sensitive meetings.
- Reports contain a summary, decisions, and tasks; a grounding step checks report items against the transcript. Review transcripts and reports for recognition errors or omissions before relying on them.
- Store transcripts and reports in PostgreSQL. The uploaded audio is written to a temporary backend file for transcription and the application attempts to delete it after processing; it does not store the original recording in PostgreSQL.

## Requirements

- Python and pip
- Node.js and npm
- PostgreSQL, with a database and user created
- A Groq API key with access to the configured Whisper and chat-completion models
- Large audio uploads are split with the FFmpeg binary bundled by the `imageio-ffmpeg` backend dependency.

## Configure and run locally (Windows PowerShell)

### 1. Configure PostgreSQL and backend settings

Create a PostgreSQL database and a user that can access it. You can do this in pgAdmin or by connecting to PostgreSQL as an administrator and running SQL like this (replace the example password first):

```sql
CREATE ROLE smart_meeting_user WITH LOGIN PASSWORD 'replace-with-a-strong-password';
CREATE DATABASE smart_meeting_assistant OWNER smart_meeting_user;
```

Create `backend/.env` in VS Code and set the PostgreSQL values and Groq key listed below. Keep this file private; `.env` files are excluded from Git. Do not paste its contents into issues or chat.

Do not put database credentials, API tokens, or other secrets in frontend environment files: Vite embeds `VITE_*` values in public browser assets. `VITE_API_URL` is a public endpoint address only. Keep backend credentials in `backend/.env` locally and in a host secret manager for any private deployment. `.env` and `.inv` files must not be placed in `frontend/public`.

Set the required database variables in `backend/.env` to the PostgreSQL host, port, database, user, and password you created. Set `GROQ_API_KEY` for transcription and report generation. SMTP and CORS variables are optional:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PGHOST` | required | PostgreSQL server host, commonly `localhost` for local development |
| `PGPORT` | required | PostgreSQL port, commonly `5432` |
| `PGDATABASE` | required | Existing PostgreSQL database name |
| `PGUSER` | required | PostgreSQL login role |
| `PGPASSWORD` | required | Password for the PostgreSQL login role |
| `PGSSLMODE` | `require` | PostgreSQL TLS mode; set to `prefer` or `disable` only when appropriate for a local database |
| `GROQ_API_KEY` | required for transcription and report generation | Secret Groq API key; keep it in backend environment settings, never in the frontend |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq chat-completion model used for report generation |
| `OTP_HASH_SECRET` | required for registration and password reset | Stable random secret of at least 32 characters used to protect email codes |
| `SMTP_HOST` | required for registration and password reset | SMTP server used to send email codes |
| `SMTP_PORT` | `587` | SMTP TLS port; use `465` with `SMTP_USE_SSL=true` |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | optional | SMTP login; set both when the server requires authentication; use an app password where required |
| `SMTP_FROM_EMAIL` | required for registration and password reset | Sender address accepted by the SMTP server |
| `SMTP_USE_SSL` | `false` | Use implicit TLS for SMTP port 465; otherwise the app requires STARTTLS |
| `FRONTEND_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed by CORS |
| `SESSION_COOKIE_SECURE` | `false` | Set to `true` when the API is served over HTTPS |

The database itself must exist before the backend starts. On startup, the backend creates the account, session, rate-limit, email-verification, password-reset, meeting, and report tables if missing, then adds the nullable `meetings.user_id` and `meetings.session_number` columns, the per-user `app_users.next_session_number` counter, and indexes. Existing accounts are marked verified by the one-time `email_verified_at` column migration; new accounts remain unverified until their email code is confirmed. Existing owned meetings receive session numbers ordered by `created_at` and then `id`; the first verified account claims unowned legacy meetings, numbered in the same chronological order. The migration preserves transcript and report data. Session numbers advance transactionally and are not reduced when a meeting is deleted. Schema changes are applied at startup; a separate migration tool is not used in this version.

For local-only use, configure PostgreSQL to listen on `localhost` and keep `pg_hba.conf` limited to loopback clients. Setting the backend's `PGHOST=localhost` only controls its connection destination; it does not restrict the PostgreSQL server's listening interfaces.

Passwords are stored as Argon2 hashes and are set after email verification. New accounts must verify their email using an eight-digit code before a password or session is created; codes expire after 10 minutes, are stored as keyed hashes, and allow five guesses per code. Forgot-password requests send a time-limited code to the account email; a successful reset invalidates existing sessions. Verification, resend, and reset requests are rate-limited. Set `OTP_HASH_SECRET` to a stable secret (generate one with `python -c "import secrets; print(secrets.token_hex(32))"`) and configure SMTP before enabling registration or password reset. SMTP uses STARTTLS by default; use implicit TLS only with `SMTP_USE_SSL=true`. The API checks the server-side session cookie on protected requests and stores only SHA-256 hashes of session tokens in PostgreSQL. Transcript and report queries are scoped to the authenticated account. Sign-in is limited after five attempts per client address in 15 minutes; sign-up allows 10 attempts per client address per hour. Audio transcription has no per-account rate limit; report generation allows five requests per hour with a 60-second gap between accepted requests. The app currently has no admin or paid features.

### 2. Install backend dependencies and start the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`. Check `http://127.0.0.1:8000/health` to verify PostgreSQL and that `GROQ_API_KEY` is configured. The health route does not make a request to Groq.

### 3. Install and start the frontend

Open a second PowerShell terminal at the project root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open the local URL printed by Vite, usually `http://localhost:5173`. In development, Vite proxies `/auth`, `/transcripts`, `/reports`, and `/health` to FastAPI at `127.0.0.1:VITE_API_PORT` (`8000` by default). Browser requests stay same-origin, preserving authentication cookies and CSRF behavior on `localhost` and `127.0.0.1`. Set `VITE_API_PORT` in `.env.local` if FastAPI uses another port. `VITE_API_URL` overrides the proxy; leave it unset for normal local use and ngrok. If you change `.env.local`, restart Vite. For a production build, set `VITE_API_URL` before running `npm run build`; without it, the built frontend keeps the existing same-host port fallback. These are frontend settings and belong in `frontend/.env.local` or the frontend host's build environment, not `backend/.env`.

### Controlled ngrok demo (local only)

This exposes the Vite frontend through one public ngrok URL. FastAPI and PostgreSQL remain local; audio and transcript processing uses Groq's hosted API. The public URL is reachable by anyone unless you add an ngrok access policy, so use a test account and non-sensitive sample meetings. Never demo real transcripts or recordings.

Use an exact, assigned ngrok hostname if you have one. In `frontend/.env.local`, keep `VITE_API_PORT=8000`, leave `VITE_API_URL` unset, and set `NGROK_HOSTNAME` to the hostname only, for example:

```dotenv
VITE_API_PORT=8000
NGROK_HOSTNAME=your-assigned-name.ngrok-free.app
```

This hostname is allowlisted exactly by Vite; wildcard host validation is not enabled. `.env.local` is ignored by Git. Do not put your ngrok token in this file. If you use a different FastAPI port, set `VITE_API_PORT` to that port.

In `backend/.env`, add the exact HTTPS frontend origin to `FRONTEND_ORIGINS` and set `SESSION_COOKIE_SECURE=true`, then restart FastAPI. For example, include `https://your-assigned-name.ngrok-free.app` alongside the localhost origins. If the ngrok hostname changes, update both frontend and backend settings and restart both development servers.

Start the local services in separate PowerShell terminals from the repository root. PostgreSQL should be running and `GROQ_API_KEY` should be set in `backend/.env`.

**Backend terminal:**

```powershell
Set-Location .\backend
if (Test-Path .\.venv314\Scripts\Activate.ps1) { .\.venv314\Scripts\Activate.ps1 } else { .\.venv\Scripts\Activate.ps1 }
$env:FRONTEND_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,https://your-assigned-name.ngrok-free.app"
$env:SESSION_COOKIE_SECURE = "true"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The exact HTTPS frontend origin must be included because the API checks it for CSRF. Secure cookies are enabled for the HTTPS browser URL. These PowerShell environment values apply to this terminal only; local HTTP use keeps its existing `.env` defaults when started in a fresh terminal.

**Frontend terminal:**

```powershell
Set-Location .\frontend
npm run dev
```

Vite binds to its default `localhost:5173` loopback address and stops if that port is occupied, so ngrok cannot silently forward to another local service.

**ngrok terminal:**

```powershell
ngrok http --url https://your-assigned-name.ngrok-free.app 5173
```

Replace the example hostname in both the command and the two configuration values with the exact assigned hostname. Configure the ngrok auth token locally using the command shown in your ngrok dashboard; the ngrok CLI stores it in its user configuration, outside this repository. Do not paste the token into chat or commit it.

Open the HTTPS forwarding URL printed by ngrok. Verify the API proxy by opening `https://your-assigned-name.ngrok-free.app/health` and by signing in with a test account, saving a sample transcript, and confirming the report workflow. In browser developer tools, requests should go to the same ngrok hostname at `/auth`, `/transcripts`, and `/reports`; auth cookies should be `Secure`, `HttpOnly`, and `SameSite=Lax`.

If you use a temporary random ngrok hostname, start Vite and the tunnel to learn the hostname, then set that exact value in `frontend/.env.local` and set the backend terminal's `FRONTEND_ORIGINS` as shown above. Restart Vite and FastAPI while leaving ngrok running, then open the URL only after both services restart. When the tunnel ends and ngrok assigns a different hostname, update both settings again. An assigned hostname avoids that restart cycle.

Where available, add ngrok OAuth/OIDC or an IP access policy before sharing the URL. The app's own sign-in remains required, but the tunnel URL itself is public. The Vite development server is intended for this controlled demo and is not a production deployment.

## Audio and transcript behavior

- Uploads accept `.flac`, `.m4a`, `.mp3`, `.mp4`, `.mpeg`, `.mpga`, `.ogg`, `.wav`, `.webm`, and `.wma` file extensions. The maximum upload size is 200 MB. Files larger than Groq's 25 MB direct-upload limit are converted to 16 kHz mono FLAC and transcribed as five-minute chunks; their transcripts are combined in order.
- The backend sends English audio to Groq's hosted `whisper-large-v3` endpoint. Non-English speech may be transcribed incorrectly with the current fixed language setting.
- A blank result is rejected. Saved transcript text is limited to 200,000 characters.
- Browser microphone access requires permission and a secure browser context; `localhost` is treated as secure by modern browsers.
- Confirm the transcript against the recording before generating or sharing a report. Report generation uses the transcript text, not the original audio.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check PostgreSQL and that the Groq API key is configured |
| `GET` | `/auth/csrf` | Prepare the CSRF cookie and token for sign-in or registration |
| `POST` | `/auth/register` | Create a password-free pending account and send an email code |
| `POST` | `/auth/verify-email` | Verify the code, set the password, and create a session |
| `POST` | `/auth/resend-verification` | Resend a code for an unverified account |
| `POST` | `/auth/request-password-reset` | Send a time-limited reset code without revealing whether the account exists |
| `POST` | `/auth/reset-password` | Verify a reset code, change the password, and revoke existing sessions |
| `POST` | `/auth/login` | Sign in to an account |
| `GET` | `/auth/me` | Restore the current session |
| `POST` | `/auth/logout` | Revoke the current session |
| `GET` | `/transcripts` | List the signed-in user's saved transcripts, including `session_number` |
| `POST` | `/transcripts` | Save a transcript submitted as JSON and return its `session_number` |
| `POST` | `/transcripts/upload` | Transcribe an uploaded recording, save its transcript, and return its `session_number` |
| `PUT` | `/transcripts/{meeting_id}` | Edit a transcript and remove its previous report |
| `DELETE` | `/transcripts/{meeting_id}` | Delete a meeting and its linked report |
| `GET` | `/reports` | List saved reports |
| `POST` | `/transcripts/{meeting_id}/report` | Generate or regenerate a report with Groq |

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

Unit tests cover authentication, password hashing, unauthenticated access, request throttles, CSRF checks, transcript grounding, mocked Groq report/transcription calls, mocked database behavior, upload limits, and health checks. PostgreSQL integration tests also cover session numbering, deletion and concurrent saves, per-user usage limits, two-account ownership, and legacy backfill; they are skipped unless `SMART_MEETING_TEST_DATABASE_URL` is set to a dedicated test database. Its database name must contain `test`; the test creates a temporary schema and removes it afterward. Never point test commands at the database containing real meeting data.

### Live Groq report evaluation

From `backend`, set `GROQ_API_KEY` in `backend/.env` and set `SMART_MEETING_TEST_DATABASE_URL` to a dedicated PostgreSQL test database whose name contains `test`, then run:

```powershell
$env:SMART_MEETING_TEST_DATABASE_URL = "postgresql://test_user:test_password@localhost:5432/sma_test"
python evaluate_report_quality.py
```

This calls the configured Groq model against the cases in `examples/report_evaluation_cases.json`. It creates a uniquely named temporary schema in the test database and drops that schema when it finishes. The database and Groq API must be reachable. If a password has URI-reserved characters, URL-encode them in the connection URI.

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

1. Start PostgreSQL, configure `GROQ_API_KEY`, and start the backend and frontend.
2. Open `/health` and confirm it reports the database and Groq configuration.
3. Save a transcript, generate a report, edit the transcript, regenerate the report, then delete the meeting.
4. Upload a short English recording. Check the transcript against the audio before generating its report.
5. Try [`examples/sample_transcript.txt`](examples/sample_transcript.txt). It has one explicit decision and two promised follow-ups; its dashboard idea is discussion only.
6. Confirm the audio player works and review the privacy and terms pages at `/privacy.html` and `/terms.html`.

The repository includes focused backend, frontend, and live-model validation code. Re-run the relevant checks against the exact revision and machine you intend to release; do not rely on an old test count or a prior local run as current release evidence.

## Deployment readiness

**Current scope: local use. Public deployment is not ready.** Authentication and account-level meeting access are implemented, but they still need review on a private staging deployment. The custom domain is not connected, legal pages need operator details and review, and production HTTPS, secret storage, backups, monitoring, and hosting configuration remain. Keep the backend and database on the local machine or a private network.

Before any public launch, complete and verify all of the following:

- Verify on private staging that two users cannot access each other's meetings and that unauthenticated requests fail; check session, CSRF, rate-limit, and HTTPS cookie settings in the deployed topology.
- Choose and configure hosting, connect the custom domain, and serve the site and API over HTTPS.
- Keep PostgreSQL private and store credentials in the host's secret manager. Do not commit `.env` or `.inv` files or put them in the frontend public folder.
- Bind PostgreSQL only to the private interface(s) used by the API host and restrict both `pg_hba.conf` and the host firewall to those clients.
- Store `GROQ_API_KEY` in the backend host's secret manager, never in frontend build variables. Confirm the provider's data-handling terms are appropriate for meeting audio and transcripts.
- Set `VITE_API_URL` to the deployed HTTPS API URL at frontend build time. Set `FRONTEND_ORIGINS` to the exact deployed frontend origin(s); do not use `*`.
- Run the API behind a production ASGI server and HTTPS reverse proxy. Do not use `uvicorn --reload` in production. Configure request-body limits above 200 MB to allow for multipart overhead as well as the application's 200 MB file limit.
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
| `/health` reports Groq is not configured | Set `GROQ_API_KEY` in the backend environment and restart the API. |
| Transcript is empty or inaccurate | Check that the file is supported, speech is audible and in English, and the upload is within 200 MB. Review the transcript against the recording. |
| Browser cannot record | Grant microphone permission and use `localhost` or another secure browser context. |
| Transcription or report generation fails | Check the backend's Groq API key, account access, and configured model. If Groq returns an error or invalid response, the API reports a generation failure; inspect backend logs without copying transcript contents into them. |

## Project map

- `backend/main.py`: stable `uvicorn main:app` entry point and compatibility exports
- `backend/app/main.py`: FastAPI setup, middleware, request validation, and route registration
- `backend/app/config.py`: backend `.env` loading and environment-backed settings
- `backend/app/runtime.py`: database schema and shared security helpers
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
