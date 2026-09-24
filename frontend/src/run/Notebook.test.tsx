import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { Notebook } from './Notebook'
import { event, panels } from './fixtures'
import { RunPanelsContext } from './RunContext'

it('shows ordered entries and opens cited graph ids', async () => {
  const entry = { entry_id: 'NBK-1', seq: 1, author: 'policy_analyst', kind: 'policy_reading', text: 'The accepted Clause applies.', node_ids: ['CLS-1'], edge_ids: ['E-1'] }
  const events = [event('notebook_write', 'notebook_write', { entry, node_ids: entry.node_ids, edge_ids: entry.edge_ids })]
  const showEvidence = vi.fn()
  render(<RunPanelsContext.Provider value={panels(events, { showEvidence, tab: 'notebook' })}><Notebook /></RunPanelsContext.Provider>)
  expect(screen.getByText('The accepted Clause applies.')).toBeInTheDocument()
  expect(screen.getByText('policy analyst')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'CLS-1' }))
  expect(showEvidence).toHaveBeenCalledWith({ node_ids: ['CLS-1'], edge_ids: [] })
})
