import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { Notebook } from './Notebook'
import { event } from './fixtures'
import { deriveFlow } from './flow'
import { graphModel } from './graphModel'
import { RunPanelsContext, type RunPanels } from './RunContext'
import { emptyRun, reduceEvent } from './store'

it('shows ordered entries and opens cited graph ids', async () => {
  const entry = { entry_id: 'NBK-1', seq: 1, author: 'policy_analyst', kind: 'policy_reading', text: 'The accepted Clause applies.', node_ids: ['CLS-1'], edge_ids: ['E-1'] }
  const events = [event('notebook_write', 'notebook_write', { entry, node_ids: entry.node_ids, edge_ids: entry.edge_ids })]
  const showEvidence = vi.fn()
  const panels: RunPanels = {
    view: events.reduce(reduceEvent, emptyRun()), flow: deriveFlow(events),
    selection: null, select: vi.fn(), highlight: { nodeIds: new Set(), edgeIds: new Set() },
    clearHighlight: vi.fn(), cited: { nodeIds: new Set(), edgeIds: new Set() },
    graph: { nodes: new Map(), edges: new Map(), expand: vi.fn() },
    graphModel: graphModel({ groups: { case: { title: 'Case', description: '' } }, labels: {}, edges: {} }),
    showEvidence, tab: 'notebook', setTab: vi.fn(),
  }
  render(<RunPanelsContext.Provider value={panels}><Notebook /></RunPanelsContext.Provider>)
  expect(screen.getByText('The accepted Clause applies.')).toBeInTheDocument()
  expect(screen.getByText('policy analyst')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'CLS-1' }))
  expect(showEvidence).toHaveBeenCalledWith({ node_ids: ['CLS-1'], edge_ids: [] })
})
