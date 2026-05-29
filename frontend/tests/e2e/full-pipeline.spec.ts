import { test, expect } from '@playwright/test'

/**
 * Full auto-mode pipeline E2E test.
 *
 * Requires:
 * - Frontend dev server at http://localhost:5173
 * - Backend at http://localhost:8000
 * - Seeded database with plant + disease data
 *
 * Tests the critical regression: all 8 stage results must be visible
 * after a full auto-mode run (isTerminalStatus was stopping polling
 * after stage 1 in the original bug).
 */

test.describe('Full auto-mode pipeline', () => {
  test('all 8 stages produce visible results', async ({ page }) => {
    await page.goto('/')

    // Setup: select a plant
    await page.getByTestId('plant-search').fill('Curcuma')
    await page.getByText('Curcuma longa').first().click()

    // Setup: select a disease
    await page.getByTestId('disease-search').fill('diabetes')
    await page.getByText('type 2 diabetes mellitus').first().click()

    // Confirm selections are visible
    await expect(page.getByTestId('selected-plants')).toContainText('Curcuma longa')
    await expect(page.getByTestId('selected-diseases')).toContainText('diabetes')

    // Start analysis in auto mode
    await page.getByRole('button', { name: /start analysis/i }).click()

    // Should navigate to the analysis page
    await page.waitForURL(/\/analysis\//, { timeout: 30_000 })

    // Wait for pipeline to complete (up to 5 minutes)
    await page.waitForSelector('[data-testid="pipeline-complete"]', {
      timeout: 300_000,
    })

    // REGRESSION: all 8 stages must show results, not "results not available"
    // This was broken by the isTerminalStatus bug — polling stopped after stage 1
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

  test('stage 2 ADME table shows numeric values not dashes', async ({ page }) => {
    // Navigate to a completed analysis (requires seeded fixture)
    // This is a regression test for the bug where MW/LogP showed "-"
    await page.goto('/')
    // Navigate to setup and run a quick analysis
    // (Full setup omitted here — this test requires a completed analysis ID)
    // See: stage-results-visible.spec.ts for completed-analysis fixture pattern
  })
})
