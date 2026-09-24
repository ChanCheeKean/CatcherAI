import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { event, panels } from './fixtures'
import { RunPanelsContext } from './RunContext'
import { Swimlanes } from './Swimlanes'

it('draws a lane per agent; lanes select the agent and Notebook marks show their evidence', async () => {
  const entry = { entry_id: 'NBK-1', seq: 1, author: 'critic', kind: 'conflict', text: 'Clause 7 conflicts.', node_ids: ['CLS-7'], edge_ids: [] }
  const events = [
    event('node_entered', 'supervisor', {}, { ts_wall: '2026-09-24T10:00:00Z' }),
    event('edge_taken', 'supervisor', { source: 'supervisor', target: 'supervisor', reason: 'Decide rejected' }, { ts_wall: '2026-09-24T10:00:30Z' }),
    event('node_entered', 'critic', {}, { ts_wall: '2026-09-24T10:01:00Z' }),
    event('notebook_write', 'notebook_write', { entry }, { ts_wall: '2026-09-24T10:01:30Z' }),
  ]
  const select = vi.fn()
  const showEvidence = vi.fn()
  render(
    <RunPanelsContext.Provider value={panels(events, { select, showEvidence, runLength: 180_000 })}>
      <Swimlanes />
    </RunPanelsContext.Provider>,
  )
  expect(screen.getByText('↻ sent back')).toBeInTheDocument()
  expect(screen.getByText('3:00')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'critic' }))
  expect(select).toHaveBeenCalledWith({ kind: 'actor', name: 'critic' })
  await userEvent.click(screen.getByRole('button', { name: 'Notebook conflict by critic' }))
  expect(showEvidence).toHaveBeenCalledWith(entry)
})
