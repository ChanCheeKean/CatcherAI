import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunLauncher } from './RunLauncher'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigateMock }
})

vi.mock('../../api/client', () => ({
  api: {
    meta: vi.fn().mockResolvedValue({
      adapters: { fake: true, openai: false },
      model: 'fake',
      virtual_clock: '2026-01-01T00:00:00Z',
      feature_flags: {},
    }),
    startRun: vi.fn().mockResolvedValue({
      run_id: 'run-99',
      case_id: 'DSP-2026-90002',
      status: 'running',
      events_url: '/api/v1/runs/run-99/events',
      stream_url: '/api/v1/runs/run-99/events/stream',
    }),
  },
}))

function renderLauncher() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RunLauncher caseId="DSP-2026-90002" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RunLauncher', () => {
  beforeEach(() => navigateMock.mockClear())

  it('starts a fake run and navigates to it', async () => {
    const { api } = await import('../../api/client')
    renderLauncher()

    await userEvent.click(screen.getByRole('button', { name: 'Run' }))

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/runs/run-99'))
    expect(api.startRun).toHaveBeenCalledWith({
      case_id: 'DSP-2026-90002',
      adapter: 'fake',
      auto_resume: true,
    })
  })
})
