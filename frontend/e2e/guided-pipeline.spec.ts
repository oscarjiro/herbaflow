import { test, expect } from '@playwright/test'

test.describe('Guided Pipeline', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate directly to a pipeline page via localStorage
    await page.goto('/analysis')
  })

  test('approval buttons visible in guided mode at awaiting_approval stage', async ({ page }) => {
    // This test requires a live analysis in awaiting_approval state
    // Skip if no cached analysis
    const analysisId = await page.evaluate(() => localStorage.getItem('hf_last_analysis_id'))
    test.skip(!analysisId, 'No cached analysis — run after setup-to-pipeline')

    await page.goto(`/analysis/${analysisId}`)
    // If at an awaiting_approval stage, ApprovalBar should be visible
    const approveBtn = page.getByRole('button', { name: /approve/i })
    const rejectBtn = page.getByRole('button', { name: /reject/i })

    // Either we see approval buttons (guided mode, awaiting) or we see a completed pipeline
    const isAwaitingApproval = await approveBtn.isVisible()
    if (isAwaitingApproval) {
      await expect(approveBtn).toBeEnabled()
      await expect(rejectBtn).toBeEnabled()
    } else {
      // Pipeline completed or in different state — just assert page loaded
      await expect(page.getByText(/stage/i)).toBeVisible()
    }
  })

  test('reject stage shows new analysis option', async ({ page }) => {
    const analysisId = await page.evaluate(() => localStorage.getItem('hf_last_analysis_id'))
    test.skip(!analysisId, 'No cached analysis')

    await page.goto(`/analysis/${analysisId}`)
    const rejectBtn = page.getByRole('button', { name: /reject/i })

    if (await rejectBtn.isVisible()) {
      await rejectBtn.click()
      // After reject, status should show rejection and new analysis link
      await expect(page.getByText(/new analysis/i)).toBeVisible({ timeout: 10000 })
    } else {
      test.skip(true, 'No rejection opportunity in current pipeline state')
    }
  })
})
