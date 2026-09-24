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
  await expect(page.getByRole('banner').getByRole('status')).toHaveText('Decided')

  // The timeline puts each agent on its own lane.
  await page.getByRole('tab', { name: 'Timeline' }).click()
  await expect(page.getByRole('region', { name: 'Agents over time' }).getByRole('button', { name: 'graph analyst', exact: true })).toBeVisible()

  // The evidence graph opens on the evidence the verdict cites, and also holds everything the tools touched.
  await page.getByRole('tab', { name: 'Evidence graph' }).click()
  await expect(page.getByRole('button', { name: 'Cited only' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Everything touched' }).click()
  const nodes = page.locator('.react-flow__node-entity')
  await expect(nodes.first()).toBeVisible()
  await expect(page.getByText('Test Merchant')).toBeVisible()
  expect(await nodes.count()).toBeGreaterThanOrEqual(4)

  await page.getByRole('tab', { name: 'Notebook' }).click()
  await expect(page.getByText('The Card Member holds this account.')).toBeVisible()
  // Finding chips name the item by its caption, with the id on hover.
  const chip = page.getByRole('button', { name: 'Test Card Member' })
  await expect(chip).toHaveAttribute('title', /CMB-TEST-1/)
  await chip.click()
  await expect(page.getByRole('tab', { name: 'Evidence graph' })).toHaveAttribute('aria-selected', 'true')

  // The conclusion shows the verdict.
  await expect(page.getByText('Accepted', { exact: true }).first()).toBeVisible()

  // Selecting a node explains where it came from.
  await nodes.filter({ hasText: 'Test Card Member' }).click()
  await expect(page.getByRole('complementary', { name: 'Inspector' })).toContainText(/Found by graph_analyst with graph_query/)

  // The report reads beside the graph: a cited claim focuses exactly its nodes and stays on screen, pressed.
  await page.getByRole('button', { name: 'Back to the report' }).click()
  const claim = page.getByRole('button', { name: 'The charge and Card Member are linked.' }).first()
  await claim.click()
  await expect(page.getByRole('button', { name: /Showing cited evidence/ })).toBeVisible()
  await expect(claim).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.react-flow__node-entity.react-flow__node').first()).toBeVisible()
  await expect(page.locator('.react-flow__node-entity div.opacity-25').first()).toBeAttached()

  // Selecting an agent on the flow tab dims the graph to what it touched.
  await page.getByRole('button', { name: /Show everything/ }).click()
  await page.getByRole('tab', { name: 'Agent flow' }).click()
  await page.getByText('evidence analyst').click()
  await page.getByRole('tab', { name: 'Evidence graph' }).click()
  await expect(page.getByText('Showing what evidence_analyst touched')).toBeVisible()

  // A finished run can be replayed: back at the start nothing has been decided yet.
  await page.getByRole('slider', { name: 'Replay position' }).fill('0')
  const runStatus = page.getByRole('banner').getByRole('status')
  await expect(runStatus).toHaveText('Replaying')
  // With nothing selected and no verdict yet, the inspector narrates the replay.
  await page.getByRole('button', { name: 'Back to the run' }).click()
  await expect(page.getByRole('complementary', { name: 'Inspector' }).getByRole('status')).toBeVisible()
  await page.getByRole('button', { name: 'Skip to verdict' }).click()
  await expect(runStatus).toHaveText('Decided')
})
