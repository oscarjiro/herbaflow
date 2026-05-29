import { test, expect } from '@playwright/test'

/**
 * Stage result visibility regression tests.
 *
 * Tests that stage results remain visible when navigating between stages
 * and when loading a previously completed analysis.
 *
 * Requires a completed analysis in the database.
 * Set COMPLETED_ANALYSIS_ID env var, or update the fixture below.
 */

const COMPLETED_ANALYSIS_ID =
  process.env['COMPLETED_ANALYSIS_ID'] ?? 'replace-with-seeded-analysis-id'

test.describe('Stage result visibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/analysis/${COMPLETED_ANALYSIS_ID}`)
    // Wait for pipeline page to load
    await page.waitForSelector('[data-testid="pipeline-sidebar"]', {
      timeout: 30_000,
    })
  })

  test('all stage results remain visible after load', async ({ page }) => {
    for (let stage = 1; stage <= 8; stage++) {
      await page.getByTestId(`stage-nav-${stage}`).click()
      await expect(
        page.getByText(/results not available/i)
      ).not.toBeVisible({ timeout: 5_000 })
      await expect(
        page.getByTestId(`stage-${stage}-content`)
      ).toBeVisible({ timeout: 5_000 })
    }
  })

  test('stage results remain visible after navigating away and back', async ({ page }) => {
    // Navigate to stage 8
    await page.getByTestId('stage-nav-8').click()
    await expect(page.getByTestId('stage-8-content')).toBeVisible()

    // Navigate to stage 1
    await page.getByTestId('stage-nav-1').click()
    await expect(page.getByTestId('stage-1-content')).toBeVisible()
    await expect(page.getByText(/results not available/i)).not.toBeVisible()

    // Navigate back to stage 8
    await page.getByTestId('stage-nav-8').click()
    await expect(page.getByTestId('stage-8-content')).toBeVisible()
  })

  test('stage 2 ADME table shows numeric values not dashes', async ({ page }) => {
    await page.getByTestId('stage-nav-2').click()
    await expect(page.getByTestId('stage-2-content')).toBeVisible()

    // First result row must show numeric MW, not empty dash
    const firstRow = page.getByTestId('adme-table').getByRole('row').nth(1)
    const mwCell = firstRow.getByTestId('cell-molecular_weight')
    await expect(mwCell).not.toHaveText('-')
    await expect(mwCell).toHaveText(/\d+\.?\d*/)
  })

  test('stage 7 hub gene table renders centrality scores', async ({ page }) => {
    await page.getByTestId('stage-nav-7').click()
    await expect(page.getByTestId('stage-7-content')).toBeVisible()

    // Hub gene table must have degree centrality column
    await expect(
      page.getByRole('columnheader', { name: /degree/i })
    ).toBeVisible()

    // First gene must have a score between 0 and 1 (normalized)
    const firstRow = page.getByRole('row').nth(1)
    const degreeCell = firstRow.getByTestId('cell-degree_centrality')
    await expect(degreeCell).toHaveText(/^0\.\d+$|^1(\.0+)?$/)
  })

  test('stage 8 enrichment shows global tab by default', async ({ page }) => {
    await page.getByTestId('stage-nav-8').click()
    await expect(page.getByTestId('stage-8-content')).toBeVisible()

    // Global tab should be active / visible
    await expect(
      page.getByRole('tab', { name: /global/i })
    ).toBeVisible()
    await expect(
      page.getByRole('tabpanel')
    ).toBeVisible()
  })
})
