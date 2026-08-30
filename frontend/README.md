# AI Codebase Engineer — Frontend

React + TypeScript + Vite + Tailwind frontend for the existing FastAPI backend under `backend/`.

## Install & run

```bash
cd frontend
npm install
cp .env.example .env   # defaults to http://localhost:8000
npm run dev
```

Make sure the backend is running separately (`uvicorn app.main:app --reload` from `backend/`, or via Docker) —
this app only talks to it over HTTP, it doesn't start it.

## Commands

| Command           | Purpose                                  |
|--------------------|-------------------------------------------|
| `npm run dev`      | Start the Vite dev server (port 5173)    |
| `npm run build`    | Type-check (`tsc -b`) then production build to `dist/` |
| `npm run preview`  | Serve the production build locally       |
| `npm run lint`     | Type-check only, no build                |

## Environment variables

| Variable        | Default                 | Purpose                        |
|-----------------|--------------------------|---------------------------------|
| `VITE_API_URL`  | `http://localhost:8000` | Base URL of the FastAPI backend |

No secrets live in the frontend — the Gemini API key stays server-side (`backend/.env`), never referenced here.

## Structure

```
src/
  api/            One module per backend domain (client.ts + repository/chat/investigation/planning/changes/tests)
  types/api.ts    TypeScript types mirroring the actual backend request/response schemas
  state/          RepositoryContext — the only global state (connected repo + pipeline stage)
  components/     layout/ (shell, nav, topbar) · ui/ (badges, cards, states) · code/ (code+diff viewers, evidence)
  pages/          One file per primary screen
  lib/            Pure helpers: highlighting, diff/test-output parsing, section parsing, stat derivation
```

See the project chat/PR description for the full mapping of backend endpoints to screens and the list of
frontend features that are placeholders because the backend doesn't support them yet.
