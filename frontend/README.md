# CatcherAI frontend

React + TypeScript + Vite. Two pages: the case list (`/`) and the run page
(`/cases/:caseId/runs/:runId`) with the agent-flow and evidence-graph canvas, the inspector and the
conclusion panel. Design: `docs/superpowers/specs/2026-09-21-agentic-graph-revamp-design.md` §7.

```bash
npm ci
npm run dev     # http://localhost:5173, proxies /api to http://127.0.0.1:8000
npm run test    # Vitest + React Testing Library
npm run build   # tsc -b && vite build
npm run lint    # oxlint
```

Run state is derived from the SSE trajectory alone: `src/run/store.ts` folds events into one view
(plan, visits per actor, touched graph ids, report) and `src/run/useRunEvents.ts` feeds it.
