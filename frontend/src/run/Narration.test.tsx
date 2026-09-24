import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { event, panels } from './fixtures'
import { Narration } from './Narration'
import { RunPanelsContext } from './RunContext'

const plan = [
  { id: 'P1', question: 'Who used the card?', status: 'open', evidence_refs: [], waiver_reason: null },
  { id: 'P2', question: 'Was it refunded?', status: 'done', evidence_refs: [], waiver_reason: null },
]
const entry = { entry_id: 'NBK-2', seq: 2, author: 'policy_analyst', kind: 'conflict', text: 'Clause 7 contradicts 3.2.', node_ids: ['CLS-7'], edge_ids: [] }

function renderWith(events: ReturnType<typeof event>[]) {
  const showEvidence = vi.fn()
  render(
    <RunPanelsContext.Provider value={panels(events, { showEvidence })}>
      <Narration />
    </RunPanelsContext.Provider>,
  )
  return showEvidence
}

it('narrates who works, the latest reasoning, the newest finding and the open plan items', async () => {
  const showEvidence = renderWith([
    event('plan_updated', 'supervisor', { plan }),
    event('supervisor_turn', 'supervisor', { reasoning: 'Delegate the first round.' }, { turn: 1 }),
    event('supervisor_turn', 'supervisor', { reasoning: 'Ask the critic.' }, { turn: 2 }),
    event('node_entered', 'critic', { input: {} }, { turn: 2 }),
    event('notebook_write', 'notebook_write', { entry: { ...entry, seq: 1, entry_id: 'NBK-1', text: 'Older.' } }),
    event('notebook_write', 'notebook_write', { entry }),
  ])
  expect(screen.getByRole('status')).toHaveTextContent('Supervisor turn 2; 1 of 2 plan items still open')
  expect(screen.getByText('critic')).toBeInTheDocument()
  expect(screen.getByText('Ask the critic.')).toBeInTheDocument()
  expect(screen.queryByText('Delegate the first round.')).not.toBeInTheDocument()
  expect(screen.getByText('Clause 7 contradicts 3.2.')).toBeInTheDocument()
  expect(screen.queryByText('Older.')).not.toBeInTheDocument()
  expect(screen.getByText('Who used the card?')).toBeInTheDocument()
  expect(screen.queryByText('Was it refunded?')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'CLS-7' }))
  expect(showEvidence).toHaveBeenCalledWith(entry)
})

it('reports a failed run', () => {
  renderWith([event('error', 'runtime', { error: 'boom' })])
  expect(screen.getByRole('status')).toHaveTextContent('The run failed: boom')
})
