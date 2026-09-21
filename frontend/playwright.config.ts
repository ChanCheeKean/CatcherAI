import { defineConfig } from '@playwright/test'

const API = 'http://127.0.0.1:8100'
const APP = 'http://127.0.0.1:5273'

// A hermetic stack: a scripted backend on a tiny graph (no LLM, no generated data) behind the real frontend.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  use: { baseURL: APP, trace: 'retain-on-failure' },
  webServer: [
    {
      command: 'uv run uvicorn e2e_server:app --app-dir tests --host 127.0.0.1 --port 8100',
      cwd: '..',
      env: { PYTHONPATH: 'data/generator:tests' },
      url: `${API}/health`,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npx vite --host 127.0.0.1 --port 5273 --strictPort',
      env: { API_URL: API },
      url: APP,
      reuseExistingServer: !process.env.CI,
    },
  ],
})
