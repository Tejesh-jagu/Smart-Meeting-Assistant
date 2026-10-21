# Smart Meeting Assistant frontend

The React/Vite frontend provides transcript entry, audio recording/upload, saved meetings, and meeting reports.

## Run locally

From this directory:

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

Set `VITE_API_PORT` in `.env.local` if the backend uses a port other than `8000`. The frontend uses the same hostname you opened it with, so its CSRF and session cookies work with either `localhost` or `127.0.0.1`. Vite reads environment values at startup; restart it after changing them. Use `VITE_API_URL` only when you need to set a specific API origin.

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
