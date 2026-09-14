# Dispute Observatory frontend

React + TypeScript + Vite console for the CatcherAI dispute agent. See the repository root
[`README.md`](../README.md#dispute-observatory-frontend) for how
to run this alongside the backend API, and
[`docs/design/07-observability-console.md`](../docs/design/07-observability-console.md) for the
full product/API/staging design.

```bash
npm install
npm run dev     # http://localhost:5173, proxies /api to http://127.0.0.1:8000
npm run test    # Vitest + React Testing Library
npm run build   # tsc -b && vite build
npm run lint    # oxlint
npm run e2e     # Playwright; starts/stops the full backend + frontend launcher
```
