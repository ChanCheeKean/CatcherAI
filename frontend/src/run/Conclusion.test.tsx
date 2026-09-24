import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Conclusion } from './Conclusion'
import { event, panels, report } from './fixtures'
import { RunPanelsContext } from './RunContext'

function renderWith(events: ReturnType<typeof event>[]) {
  render(
    <RunPanelsContext.Provider value={panels(events)}>
      <Conclusion />
    </RunPanelsContext.Provider>,
  )
}

describe('Conclusion', () => {
  it('shows live status and open plan items before the decision', () => {
    renderWith([
      event('plan_updated', 'triage', {
        plan: [{ id: 'P1', question: 'Who used the card?', status: 'open', evidence_refs: [], waiver_reason: null }],
      }),
      event('supervisor_turn', 'supervisor', {}, { turn: 3 }),
    ])
    expect(screen.getByRole('status')).toHaveTextContent('Supervisor turn 3; 1 of 1 plan items still open')
    expect(screen.getByText('Who used the card?')).toBeInTheDocument()
  })

  it('shows the verdict, category and headline once decided', () => {
    renderWith([event('decision', 'adjudicator', { report: { ...report, verdict: 'goodwill_credit' } })])
    expect(screen.getByText('Goodwill credit')).toBeInTheDocument()
    expect(screen.getByText('OVR · Overcharged')).toBeInTheDocument()
    expect(screen.getByText(report.headline)).toBeInTheDocument()
  })

  it('reports a failed run', () => {
    renderWith([event('error', 'runtime', { error: 'boom' })])
    expect(screen.getByRole('status')).toHaveTextContent('The run failed: boom')
  })
})
