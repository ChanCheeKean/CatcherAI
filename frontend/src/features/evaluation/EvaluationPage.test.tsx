import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { EvaluationPage } from './EvaluationPage'

vi.mock('../../api/client', () => ({ api: { listEvaluationReports: vi.fn(), getEvaluationReport: vi.fn() } }))

beforeEach(() => {
  vi.mocked(api.listEvaluationReports).mockResolvedValue([{ report_id: 'demo', modified_at: '2026-01-01', attempts: 1, passed: 1, cases: 1, pass_rate: 1, stable_cases: 1, reconciled_attempts: 1 }])
  vi.mocked(api.getEvaluationReport).mockResolvedValue({
    report_id: 'demo', summary: { report_id: 'demo', modified_at: '2026-01-01', attempts: 1, passed: 1, cases: 1, pass_rate: 1, stable_cases: 1, reconciled_attempts: 1 }, reliability: [], attempts: [], capability_matrix: { tool_calling: { 'CASE-1': true } }, proving_events: [{ capability: 'tool_calling', case_id: 'CASE-1', run_id: 'run-real', seq: 42, type: 'tool_call', summary: 'Recorded proof', ts_virtual: '2026-01-01' }],
  })
})

it('navigates a capability cell to its recorded proving event', async () => {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><EvaluationPage /></MemoryRouter></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: 'tool_calling CASE-1 proving event' }))
  expect(await screen.findByText('Recorded proof')).toBeInTheDocument()
  expect(screen.getByText('seq 42')).toBeInTheDocument()
})
