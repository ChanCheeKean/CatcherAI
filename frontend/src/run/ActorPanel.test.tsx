import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ActorPanel } from './ActorPanel'
import { event } from './fixtures'
import { deriveFlow } from './flow'

const at = (visit: number, turn: number) => ({ visit, turn, parent_id: null })
const supervisorVisit = (visit: number) => [
  event('node_entered', 'supervisor', { input: { latest_findings: [] } }, at(visit, visit)),
  event('node_exited', 'supervisor', { output: { summary: { key_facts: [`fact ${visit}`] } } }, at(visit, visit)),
]

describe('ActorPanel', () => {
  const flow = deriveFlow([...supervisorVisit(1), ...supervisorVisit(2)])

  it('lists every visit with its readable output', () => {
    render(<ActorPanel name="supervisor" flow={flow} />)
    expect(screen.getByText('2 visits')).toBeInTheDocument()
    expect(screen.getByText(/Visit 1/)).toBeInTheDocument()
    expect(screen.getByText('fact 2')).toBeVisible()
  })

  it('opens the exact JSON in its own capsule', async () => {
    render(<ActorPanel name="supervisor" flow={deriveFlow(supervisorVisit(1))} />)
    await userEvent.click(screen.getAllByText('Raw JSON')[0])
    expect(screen.getAllByText(/"key_facts"/)[0]).toBeVisible()
  })

  it('pulls reasoning, next step and plan out of a supervisor answer', () => {
    const answer = {
      reasoning: 'Nothing is proven yet.',
      plan_edits: [],
      summary: { key_facts: [] },
      action: { tasks: [{ role: 'graph_analyst', objective: 'Trace the shared address', plan_item_ids: ['P1'], instructions: null }] },
    }
    const rich = deriveFlow([
      event('node_entered', 'supervisor', { input: {} }, at(1, 1)),
      event('model_call', 'supervisor', { schema: 'SupervisorTurn', input_tokens: 1, output_tokens: 1 }, at(1, 1)),
      event('node_exited', 'supervisor', { output: answer }, at(1, 1)),
    ])
    render(<ActorPanel name="supervisor" flow={rich} />)
    for (const title of ['Model output', 'Reasoning', 'Next step', 'Plan edits', 'Investigation summary'])
      expect(screen.getByText(title)).toBeVisible()
    expect(screen.getByText('SupervisorTurn')).toBeVisible()
    expect(screen.getByText('Delegate 1 task')).toBeVisible()
    expect(screen.getByText('Trace the shared address')).toBeVisible()
  })
})
