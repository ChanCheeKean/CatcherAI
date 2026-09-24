import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Fields, Prose } from './Fields'

describe('Prose', () => {
  it('turns graph ids into chips and leaves ordinary hyphenated words alone', () => {
    const { container } = render(
      <p>
        <Prose>CHG-C10 was paid with CRD-C10 through E-0507431, an Card-based check for a Merchant.</Prose>
      </p>,
    )
    const chips = [...container.querySelectorAll('.ref')].map((el) => el.textContent)
    expect(chips).toEqual(['CHG-C10', 'CRD-C10', 'E-0507431'])
    expect(screen.getByText(/Card-based check for a Merchant/)).toBeTruthy()
  })
})

describe('Fields', () => {
  it('formats money-valued properties and leaves other numbers alone', () => {
    render(<Fields value={{ amount: 1300, unit_price: '12.5', quantity: 2 }} />)
    expect(screen.getByText('$1,300.00')).toBeTruthy()
    expect(screen.getByText('$12.50')).toBeTruthy()
    expect(screen.getByText('2')).toBeTruthy()
  })
})
