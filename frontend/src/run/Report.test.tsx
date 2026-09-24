import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { CaseReport, GraphNode } from '../api/types'
import { comparedClauses, decidingSentence } from './clauses'
import { evidence, panels, report } from './fixtures'
import { Report } from './Report'
import { RunPanelsContext, type RunPanels } from './RunContext'

function renderReport(value: CaseReport, overrides: Partial<RunPanels> = {}) {
  const showEvidence = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RunPanelsContext.Provider value={panels([], { showEvidence, ...overrides })}>
        <Report report={value} />
      </RunPanelsContext.Provider>
    </QueryClientProvider>,
  )
  return showEvidence
}

const clause = (id: string, text: string): GraphNode => ({ id, label: 'Clause', properties: { number: id.slice(-1), heading: `Heading ${id}`, text } })
const amexClause = clause('CLS-A-1', 'A property must honour the rate confirmed at booking.')
const merchantClause = clause('CLS-M-7', 'The rate applies only with a Platinum Card. Folios settled with any other card are re-rated.')
const conflict: CaseReport = {
  ...report,
  policy_basis: [
    { document_id: amexClause.id, why: 'Binds the hotel to the booked rate.' },
    { document_id: merchantClause.id, why: 'The hotel re-rated under it.' },
  ],
  system_improvements: [{
    target: 'merchant_policy',
    issue: 'Clause 7 adds a condition.',
    suggestion: 'Remove it.',
    evidence: [{ claim: 'Clause 7 conflicts with the rate-honour Clause.', node_ids: [amexClause.id, merchantClause.id, 'ORD-1'], edge_ids: [], source_excerpt: 'Folios settled with any other card are re-rated.' }],
  }],
}

afterEach(() => vi.restoreAllMocks())

describe('Report', () => {
  it('lights up a claim in the graph and stays on screen', async () => {
    const showEvidence = renderReport(report)
    expect(screen.getAllByText('$120.50')).toHaveLength(2)
    expect(screen.getByText(/Dear Card Member/)).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: evidence.claim })[0])
    expect(showEvidence).toHaveBeenCalledWith(evidence)
    expect(screen.getByText(/Dear Card Member/)).toBeInTheDocument()
  })

  it('marks the claim the graph is showing', () => {
    renderReport(report, { highlight: { nodeIds: new Set(evidence.node_ids), edgeIds: new Set(evidence.edge_ids) } })
    for (const button of screen.getAllByRole('button', { name: evidence.claim })) expect(button).toHaveAttribute('aria-pressed', 'true')
  })

  it('ties each ruled-out decoy to the records it names', async () => {
    const edge = { id: 'E-0000009', type: 'FOR_ORDER', src: 'CHG-2', dst: 'ORD-2', properties: {} }
    const showEvidence = renderReport(
      { ...report, decoys_ruled_out: ['ORD-2/CHG-2 via E-0000009 is another order.', 'Nothing else explains it.'] },
      { graph: { nodes: new Map(), edges: new Map([[edge.id, edge]]), expand: vi.fn(), expanded: new Set() } },
    )
    await userEvent.click(screen.getByRole('button', { name: /is another order/ }))
    expect(showEvidence).toHaveBeenCalledWith({ node_ids: ['ORD-2', 'CHG-2'], edge_ids: ['E-0000009'] })
    expect(screen.queryByRole('button', { name: /Nothing else/ })).not.toBeInTheDocument()
  })

  it('sets Amex and Merchant Clauses side by side with the deciding line marked', async () => {
    const owner = { 'CLS-A-1': ['POL-A', 'amex', 'Participation Terms'], 'CLS-M-7': ['POL-M', 'merchant', 'Folio Terms'] } as const
    vi.spyOn(api, 'neighbors').mockImplementation(async (id) => {
      const [docId, docOwner, title] = owner[id as keyof typeof owner]
      return {
        neighbors: [{ type: 'HAS_CLAUSE', direction: 'in', edge: { id: 'E-1', _type: 'HAS_CLAUSE' }, node: { id: docId, _label: 'PolicyDocument', owner: docOwner, title } }],
        truncated: false,
      }
    })
    const showEvidence = renderReport(conflict, {
      graph: { nodes: new Map([amexClause, merchantClause].map((n) => [n.id, n])), edges: new Map(), expand: vi.fn(), expanded: new Set() },
    })
    const comparison = (await screen.findByRole('heading', { name: 'Amex Policy vs Merchant Policy' })).parentElement!
    expect(within(comparison).getByText('Participation Terms')).toBeInTheDocument()
    expect(within(comparison).getByText('Folio Terms')).toBeInTheDocument()
    expect(comparison.querySelector('mark')).toBeTruthy()
    expect([...comparison.querySelectorAll('mark')].map((m) => m.textContent)).toContain('Folios settled with any other card are re-rated.')
    await userEvent.click(within(comparison).getByRole('button', { name: /Folio Terms/ }))
    expect(showEvidence).toHaveBeenCalledWith({ node_ids: ['CLS-M-7'], edge_ids: [] })
  })

  it('draws no comparison when the Clauses come from one side', async () => {
    vi.spyOn(api, 'neighbors').mockResolvedValue({
      neighbors: [{ type: 'HAS_CLAUSE', direction: 'in', edge: { id: 'E-1' }, node: { id: 'POL-M', _label: 'PolicyDocument', owner: 'merchant' } }],
      truncated: false,
    })
    renderReport(conflict, {
      graph: { nodes: new Map([amexClause, merchantClause].map((n) => [n.id, n])), edges: new Map(), expand: vi.fn(), expanded: new Set() },
    })
    await screen.findByText('Clause 7 adds a condition.')
    expect(screen.queryByRole('heading', { name: 'Amex Policy vs Merchant Policy' })).not.toBeInTheDocument()
  })
})

describe('clauses', () => {
  it('compares the policy-basis Clauses a policy System Improvement cites', () => {
    expect(comparedClauses(conflict)).toEqual(['CLS-A-1', 'CLS-M-7'])
    expect(comparedClauses({ ...conflict, system_improvements: [{ ...conflict.system_improvements[0], target: 'process' }] })).toEqual([])
  })

  it('picks the quoted sentence, else the one sharing most words', () => {
    const text = String(merchantClause.properties.text)
    expect(decidingSentence(text, ['Folios settled with any other card are re-rated.'])).toBe('Folios settled with any other card are re-rated.')
    expect(decidingSentence(text, ['Only a Platinum Card gets the rate'])).toBe('The rate applies only with a Platinum Card.')
    expect(decidingSentence('See Terms 4.3 for custom pieces.', [])).toBe('See Terms 4.3 for custom pieces.')
  })
})
