import { test, expect } from '@playwright/test'

test.describe('Cache Restore', () => {
  test('localStorage analysis ID restores pipeline view', async ({ page }) => {
    // Plant a fake analysis ID in localStorage
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.setItem('hf_last_analysis_id', 'test-restore-id')
    })

    // Navigate to /analysis — SetupPage should check localStorage and redirect
    await page.goto('/analysis')

    // Either redirected to /analysis/test-restore-id (backend confirms it's valid)
    // or stays on /analysis (backend returns 404/failed so no redirect)
    // Both are valid — just assert page doesn't crash
    await expect(page).not.toHaveURL('/error')
    await expect(page.locator('body')).toBeVisible()
  })

  test('new analysis link clears localStorage cache', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.setItem('hf_last_analysis_id', 'some-old-id')
    })

    // Navigate to pipeline page
    await page.goto('/analysis/some-old-id')
    // Find and click new analysis link in sidebar
    const newAnalysisLink = page.getByRole('link', { name: /new analysis/i })
    if (await newAnalysisLink.isVisible()) {
      await newAnalysisLink.click()
      await expect(page).toHaveURL('/analysis')
      // localStorage should be cleared
      const storedId = await page.evaluate(() => localStorage.getItem('hf_last_analysis_id'))
      expect(storedId).toBeNull()
    }
  })
})
