# Code structure and conventions

This document describes where to put code when extending Smart Meeting Assistant. Keep the current browser routes and API URLs stable unless an API version change is planned.

## Frontend

`frontend/src/App.jsx` composes the page and selects the sign-in, loading, and authenticated views. Put reusable visual sections in `components/`; keep audio recording, API calls, cleanup, and workflow state out of JSX.

`hooks/useAppController.js` owns the app's local state and actions. It uses React hooks, so the project does not need a separate state library for its current single-page workflow. Keep transient form state inside the component that owns the form.

`api/client.js` is the shared API boundary. It builds the API origin, sends cookies and CSRF headers, and converts JSON error bodies into readable errors. Add API calls through this module or the controller instead of scattering fetch configuration across components.

`utils/audio.js` contains browser audio helpers that do not depend on React. Keep CSS in `index.css` and `App.css`, which are loaded by `main.jsx`.

## Backend

Run the API from `backend` with `uvicorn main:app`. `backend/main.py` remains the stable import path. `backend/app/main.py` creates the FastAPI app, configures middleware and validation handling, then includes the route modules.

Each feature's HTTP endpoints belong in one module under `backend/app/api/`: `auth.py`, `health.py`, `meetings.py`, or `reports.py`. Keep request parsing and HTTP status decisions at the route boundary. Shared database, authentication, CSRF, and model resources live in `runtime.py` until a separate service or repository has a clear second caller.

Environment values are loaded from `backend/.env` by `config.py`. Keep credentials out of source files and commit only `.env.example` templates. Frontend build settings belong in `frontend/.env.local` or the hosting provider's frontend environment, not in the backend environment.

Expected errors should return a useful HTTP status and safe `detail`; request validation responses must not echo submitted values. The frontend reads both string and field-list `detail` formats and reports malformed or failed responses in the page. Preserve these behaviors when adding routes.

## Change conventions

- Use `PascalCase` for React components, `camelCase` for JavaScript functions and values, and `snake_case` for Python functions and values.
- Keep route paths, HTTP methods, authentication dependencies, ownership checks, CSRF checks, and upload limits explicit at the route boundary.
- Validate external input with Pydantic or a component's native form constraints before it reaches business logic.
- Reuse the shared API client and existing error helpers instead of adding one-off fetch or parsing behavior.
- Keep audio conversion helpers independent from React components.
- Update the relevant README, examples, tests, and scripts when moving or renaming a public import or API route.
- Prefer the existing Python and JavaScript dependencies. Add a new dependency only when the standard library and current project patterns do not cover the need.

