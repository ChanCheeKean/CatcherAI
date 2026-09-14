import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { CaseFilters, EMPTY_FILTERS, type CaseFilterState } from './CaseFilters'

function ControlledFilters({ onChange }: { onChange: (next: CaseFilterState) => void }) {
  const [value, setValue] = useState(EMPTY_FILTERS)
  return (
    <CaseFilters
      value={value}
      onChange={(next) => {
        setValue(next)
        onChange(next)
      }}
    />
  )
}

describe('CaseFilters', () => {
  it('reports a search term without touching other filters', async () => {
    const onChange = vi.fn()
    render(<ControlledFilters onChange={onChange} />)

    await userEvent.type(screen.getByLabelText('Search'), 'DSP-2026')

    const lastCall = onChange.mock.calls.at(-1)?.[0]
    expect(lastCall).toEqual({ ...EMPTY_FILTERS, q: 'DSP-2026' })
  })

  it('reports a regime selection', async () => {
    const onChange = vi.fn()
    render(<CaseFilters value={EMPTY_FILTERS} onChange={onChange} />)

    await userEvent.selectOptions(screen.getByLabelText('Regime'), 'reg_e')

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_FILTERS, regime: 'reg_e' })
  })
})
