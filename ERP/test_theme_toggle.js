const { test, expect } = require('@playwright/test');

test('theme toggle persists across navigation', async ({ page }) => {
  await page.goto('http://localhost:8000/');
  await page.waitForSelector('.theme-toggle');
  const toggle = page.locator('.theme-toggle');
  await toggle.click();
  const newTheme = await page.evaluate(() => document.documentElement.getAttribute('data-layout-mode'));
  await page.locator('a.nav-link').first().click();
  await expect(page.locator('html')).toHaveAttribute('data-layout-mode', newTheme);
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-layout-mode', newTheme);
});