import { test, expect } from '@playwright/test'

test.describe('Setup to Pipeline', () => {
  test('complete setup form and navigate to pipeline', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: /start analysis/i }).click()
    await expect(page).toHaveURL('/analysis')

    // Analysis name (auto-filled or user-filled)
    const nameInput = page.getByLabel(/analysis name/i)
    if (await nameInput.isVisible()) {
      await nameInput.fill('Test Analysis — E2E')
    }

    // Select a plant (combobox)
    await page.getByRole('combobox').first().click()
    await page.getByRole('option').first().click()

    // Select a disease
    await page.getByRole('combobox').nth(1).click()
    await page.getByRole('option').first().click()

    // Submit
    await page.getByRole('button', { name: /start analysis/i }).click()

    // Should navigate to /analysis/:id
    await expect(page).toHaveURL(/\/analysis\/.+/)
    await expect(page.getByText(/stage/i)).toBeVisible()
  })
})
