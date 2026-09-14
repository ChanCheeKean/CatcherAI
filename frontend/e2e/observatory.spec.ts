import { expect, test } from '@playwright/test'

test('launches and observes a complete fake dispute run', async ({ page }) => {
  const browserErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text())
  })
  page.on('pageerror', (error) => browserErrors.push(error.message))

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Mission control' })).toBeVisible()
  await page.getByRole('searchbox', { name: 'Search' }).fill('DSP-2026-90002')

  const caseCard = page.locator('article').filter({ hasText: 'DSP-2026-90002' })
  await expect(caseCard).toHaveCount(1)
  await caseCard.getByRole('button', { name: 'Run', exact: true }).click()

  await expect(page).toHaveURL(/\/runs\/run-/)
  await expect(page.getByText('route_decision', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('tool_call', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Cardholder outcome', { exact: true })).toBeVisible()
  await expect(page.getByText('Network actions', { exact: true })).toBeVisible()
  await expect(page.getByText('withdrawn_after_clarification', { exact: true })).toBeVisible()

  expect(browserErrors).toEqual([])
})
