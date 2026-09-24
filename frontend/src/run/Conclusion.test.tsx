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
  it('shows the verdict, category and headline once decided', () => {
    renderWith([event('decision', 'adjudicator', { report: { ...report, verdict: 'goodwill_credit' } })])
    expect(screen.getByText('Goodwill credit')).toBeInTheDocument()
    expect(screen.getByText('OVR · Overcharged')).toBeInTheDocument()
    expect(screen.getByText(report.headline)).toBeInTheDocument()
  })

  it('shows nothing before the decision', () => {
    renderWith([event('supervisor_turn', 'supervisor', {}, { turn: 3 })])
    expect(screen.queryByRole('region', { name: 'Conclusion' })).not.toBeInTheDocument()
  })
})
