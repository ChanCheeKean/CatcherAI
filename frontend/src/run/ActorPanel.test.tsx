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

  it('switches an output to the raw JSON the agent produced', async () => {
    render(<ActorPanel name="supervisor" flow={flow} />)
    await userEvent.click(screen.getAllByRole('button', { name: 'Raw JSON' })[1])
    expect(screen.getByText(/"key_facts"/)).toBeInTheDocument()
  })
})
