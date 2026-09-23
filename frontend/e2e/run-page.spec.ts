import { expect, test } from '@playwright/test'

test('a case run fills the agent map and the evidence graph, ends in a verdict, and evidence chips light up the graph', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Wrong amount/ }).click()
  await expect(page).toHaveURL(/\/cases\/DSP-TEST-1\/runs\/run-/)

  // The agent map shows the roles that ran.
  await expect(page.getByText('graph analyst')).toBeVisible()
  await expect(page.getByText('evidence analyst')).toBeVisible()
  await expect(page.getByRole('status')).toHaveText('Decided')

  // The evidence graph holds what the tools touched.
  await page.getByRole('tab', { name: 'Evidence graph' }).click()
  const nodes = page.locator('.react-flow__node-entity')
  await expect(nodes.first()).toBeVisible()
  await expect(page.getByText('Test Merchant')).toBeVisible()
  expect(await nodes.count()).toBeGreaterThanOrEqual(4)

  await page.getByRole('tab', { name: 'Notebook' }).click()
  await expect(page.getByText('The Card Member holds this account.')).toBeVisible()
  await page.getByRole('button', { name: 'CMB-TEST-1' }).click()
  await expect(page.getByRole('tab', { name: 'Evidence graph' })).toHaveAttribute('aria-selected', 'true')

  // The conclusion shows the verdict.
  await expect(page.getByText('Accepted', { exact: true }).first()).toBeVisible()

  // Selecting a node explains where it came from.
  await nodes.filter({ hasText: 'Test Card Member' }).click()
  await expect(page.getByRole('complementary', { name: 'Inspector' })).toContainText(/Found by graph_analyst with graph_query/)

  // An evidence chip focuses exactly the cited nodes.
  await page.getByRole('button', { name: 'The charge and Card Member are linked.' }).first().click()
  await expect(page.getByRole('button', { name: /Showing cited evidence/ })).toBeVisible()
  await expect(page.locator('.react-flow__node-entity.react-flow__node').first()).toBeVisible()
  await expect(page.locator('.react-flow__node-entity div.opacity-25').first()).toBeAttached()

  // Selecting an agent on the flow tab dims the graph to what it touched.
  await page.getByRole('button', { name: /Show everything/ }).click()
  await page.getByRole('tab', { name: 'Agent flow' }).click()
  await page.getByText('evidence analyst').click()
  await page.getByRole('tab', { name: 'Evidence graph' }).click()
  await expect(page.getByText('Showing what evidence_analyst touched')).toBeVisible()
})
