# Smart Meeting Assistant frontend

The React/Vite frontend provides transcript entry, audio recording/upload, saved meetings, and meeting reports.

## Run locally

From this directory:

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

In development, Vite proxies `/auth`, `/transcripts`, `/reports`, and `/health` to `127.0.0.1:VITE_API_PORT` (`8000` by default). Browser requests stay same-origin, preserving session cookies and CSRF behavior on `localhost` and `127.0.0.1`. Set `VITE_API_PORT` in `.env.local` if FastAPI uses a different port. `VITE_API_URL` overrides the proxy; leave it unset for local use and ngrok. Vite reads environment values at startup, so restart it after changes.

## Verify changes

```powershell
npm test
npm run test:browser
npm run lint
npm run build
```

The Vitest suite checks audio play/pause, seeking, duration display, and transcript-save feedback in jsdom. `npm run test:browser` runs Chromium checks with a generated WAV fixture and mocked API responses; it verifies media playback/seek/duration plus transcript save, report generation, progress feedback, and result rendering.

Install the browser once with `npx playwright install chromium` if Playwright reports that its browser is missing. The test runner starts and stops its own temporary Vite server.

For deployment, set `VITE_API_URL` to the HTTPS API origin at build time. The backend must include the exact frontend origin in `FRONTEND_ORIGINS`.

## Controlled ngrok demo

The tunnel should point only to Vite on `localhost:5173`. Vite proxies the API paths above to FastAPI on loopback; do not tunnel port `8000`, PostgreSQL, or Ollama. See the repository README's [controlled ngrok demo guide](../README.md#controlled-ngrok-demo-local-only) for hostname, cookie, and PowerShell setup.
