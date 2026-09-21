import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Prose } from './Fields'

describe('Prose', () => {
  it('turns graph ids into chips and leaves ordinary hyphenated words alone', () => {
    const { container } = render(
      <p>
        <Prose>TXN-C10 was paid with CRD-C10 through E-0507431, an IP-based check for T-Mobile.</Prose>
      </p>,
    )
    const chips = [...container.querySelectorAll('.ref')].map((el) => el.textContent)
    expect(chips).toEqual(['TXN-C10', 'CRD-C10', 'E-0507431'])
    expect(screen.getByText(/IP-based check for T-Mobile/)).toBeTruthy()
  })
})
