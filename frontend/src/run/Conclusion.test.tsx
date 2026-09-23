import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Conclusion } from './Conclusion'
import { evidence, event, report } from './fixtures'
import { deriveFlow } from './flow'
import { graphModel } from './graphModel'
import { emptyRun, reduceEvent } from './store'
import { RunPanelsContext, type RunPanels } from './RunContext'

function renderWith(events: ReturnType<typeof event>[], showEvidence = vi.fn()) {
  const panels: RunPanels = {
    view: events.reduce(reduceEvent, emptyRun()),
    flow: deriveFlow(events),
    selection: null,
    select: vi.fn(),
    highlight: { nodeIds: new Set(), edgeIds: new Set() },
    clearHighlight: vi.fn(),
    cited: { nodeIds: new Set(), edgeIds: new Set() },
    graph: { nodes: new Map(), edges: new Map(), expand: vi.fn() },
    graphModel: graphModel({ groups: { case: { title: 'Case', description: '' } }, labels: {}, edges: {} }),
    showEvidence,
    tab: 'flow',
    setTab: vi.fn(),
  }
  render(
    <RunPanelsContext.Provider value={panels}>
      <Conclusion />
    </RunPanelsContext.Provider>,
  )
  return showEvidence
}

describe('Conclusion', () => {
  // The panel remembers its height in localStorage, so each test starts from the default.
  beforeEach(() => localStorage.clear())

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

  it('renders the report and passes cited evidence to the graph on click', async () => {
    const showEvidence = renderWith([event('decision', 'adjudicator', { report, reason: 'decided' })])
    expect(screen.getAllByText('Rejected').length).toBeGreaterThan(0)
    expect(screen.getByText(report.headline)).toBeInTheDocument()
    expect(screen.getAllByText('$120.50', { selector: 'td' })).toHaveLength(2)
    expect(screen.getByText('Another order was refunded')).toBeInTheDocument()
    expect(screen.getByText(/Dear Card Member/)).toBeInTheDocument()

    await userEvent.click(screen.getAllByRole('button', { name: evidence.claim })[0])
    expect(showEvidence).toHaveBeenCalledWith(evidence)
    // The report steps aside so the graph is visible, and "Show details" brings it back.
    expect(screen.queryByText(/Dear Card Member/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show details' }))
    expect(screen.getByText(/Dear Card Member/)).toBeInTheDocument()
  })

  it('shows goodwill, category and no improvements', () => {
    renderWith([event('decision', 'adjudicator', { report: { ...report, verdict: 'goodwill_credit' } })])
    expect(screen.getByText('Goodwill credit')).toBeInTheDocument()
    expect(screen.getAllByText(/OVR · Overcharged/).length).toBeGreaterThan(0)
    expect(screen.getByText('None — the policies were clear and followed.')).toBeInTheDocument()
  })

  it('resizes with the keyboard and collapses to the verdict strip', async () => {
    renderWith([event('decision', 'adjudicator', { report, reason: 'decided' })])
    const handle = screen.getByRole('separator', { name: 'Resize report' })
    const before = Number(handle.getAttribute('aria-valuenow'))
    handle.focus()
    await userEvent.keyboard('{ArrowUp}')
    expect(Number(handle.getAttribute('aria-valuenow'))).toBe(before + 40)
    await userEvent.keyboard('{ArrowDown>40/}')
    expect(handle).toHaveAttribute('aria-valuenow', '0')
    expect(screen.queryByText(/Dear Card Member/)).not.toBeInTheDocument()
  })

  it('collapses the details but keeps the verdict visible', async () => {
    renderWith([event('decision', 'adjudicator', { report, reason: 'decided' })])
    await userEvent.click(screen.getByRole('button', { name: 'Hide details' }))
    expect(screen.queryByText(/Dear Card Member/)).not.toBeInTheDocument()
    expect(screen.getByText('Rejected')).toBeInTheDocument()
  })

  it('reports a failed run', () => {
    renderWith([event('error', 'runtime', { error: 'boom' })])
    expect(screen.getByRole('status')).toHaveTextContent('The run failed: boom')
  })
})
