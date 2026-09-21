import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ModelOutput } from './ModelOutput'

describe('ModelOutput hypotheses', () => {
  it("shows the adjudicator's claim, verdict, reasoning and evidence, not only the verdict", () => {
    render(
      <ModelOutput
        schema="CaseReport"
        output={{
          hypotheses: [
            {
              hypothesis: 'The second posting is a split shipment',
              status: 'accepted',
              why: 'Both clearings belong to one order.',
              evidence: [{ claim: 'Both link to ORD-C04', node_ids: ['ORD-C04'], edge_ids: ['E-0507358'] }],
            },
          ],
        }}
      />,
    )
    expect(screen.getByText('The second posting is a split shipment')).toBeTruthy()
    expect(screen.getByText('accepted')).toBeTruthy()
    expect(screen.getByText('Both clearings belong to one order.')).toBeTruthy()
    expect(screen.getByText('E-0507358')).toBeTruthy()
  })

  it('still shows a working hypothesis with its support and against lines', () => {
    render(
      <ModelOutput
        schema="Triage"
        output={{ hypotheses: [{ label: 'Descriptor confusion', status: 'plausible', support: ['Merchant is known'], against: [] }] }}
      />,
    )
    expect(screen.getByText('Descriptor confusion')).toBeTruthy()
    expect(screen.getByText('Merchant is known')).toBeTruthy()
  })
})
