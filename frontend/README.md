# Concours frontend

Next.js 15 (App Router), TypeScript, Tailwind 4, Recharts. Talks to the FastAPI backend over REST and
server-sent events.

```bash
pnpm install
pnpm dev          # http://localhost:3000, expects the backend on http://127.0.0.1:8000
pnpm build        # type check, lint and production build
```

Set `NEXT_PUBLIC_API_URL` (see `.env.example`) to point at a different backend.

Regenerate the API types after a backend change:

```bash
pnpm exec openapi-typescript http://127.0.0.1:8000/openapi.json -o lib/api-types.ts
```

## Layout

```
app/page.tsx                      home: templates and project list
app/projects/[id]/layout.tsx      project shell: header with template switcher, stepper
app/projects/[id]/<step>/page.tsx upload, intake, protect, arena, serve, launch
components/ProjectShell.tsx       project context, header, stepper, step guard
components/ui.tsx                 buttons, cards, alerts, tables
lib/api.ts                        typed client over lib/api-types.ts (generated)
lib/sse.ts                        EventSource wrapper for /arena/stream
lib/stages.ts                     step order and unlock rules
lib/format.ts                     number and label formatting
```

Steps unlock from `project.stage`. Finalizing the arena also unlocks Use the winner and Launch on
Apex, because the backend only advances the stage after a scoring run or a handoff download.
