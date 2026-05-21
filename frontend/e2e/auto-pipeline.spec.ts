import { test, expect } from '@playwright/test'

test.describe('Auto Pipeline', () => {
  test('auto mode runs without approval buttons', async ({ page }) => {
    await page.goto('/analysis')

    // Select plant + disease
    await page.getByRole('combobox').first().click()
    await page.getByRole('option').first().click()
    await page.getByRole('combobox').nth(1).click()
    await page.getByRole('option').first().click()

    // Switch to Auto mode
    const autoToggle = page.getByRole('radio', { name: /auto/i })
      .or(page.getByLabel(/auto/i))
      .or(page.getByText(/auto/i).first())
    if (await autoToggle.isVisible()) {
      await autoToggle.click()
    }

    await page.getByRole('button', { name: /start analysis/i }).click()
    await expect(page).toHaveURL(/\/analysis\/.+/)

    // No approval buttons should appear during auto pipeline
    await page.waitForTimeout(3000)
    const approveBtn = page.getByRole('button', { name: /approve/i })
    await expect(approveBtn).not.toBeVisible()
  })
})
