import AxeBuilder from '@axe-core/playwright';
import { test, expect } from './fixtures';

test('desktop shell and parameter form meet automated accessibility checks', async ({ page }) => {
  await page.goto('/#token=browser-test-session');
  await page.getByRole('button', { name: 'Parameters', exact: true }).click();
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(audit.violations).toEqual([]);
});

test('compact desktop keeps editor controls visible and rejects invalid arrays', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/#token=browser-test-session');
  await page.getByRole('button', { name: 'Parameters', exact: true }).click();
  await page.getByRole('textbox', { name: 'gSig', exact: true }).fill('invalid-array');
  await page.getByRole('textbox', { name: 'gSig', exact: true }).press('Tab');
  await expect(page.getByRole('textbox', { name: 'gSig', exact: true })).toHaveAttribute('aria-invalid', 'true');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.locator('.notification[role=alert]')).toContainText('Correct invalid parameter values');
  await page.getByRole('button', { name: 'Dismiss', exact: true }).click();
  await page.getByRole('textbox', { name: 'gSig', exact: true }).fill('[3, 3]');
  await page.getByRole('textbox', { name: 'gSig', exact: true }).press('Tab');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: 'test-results/workbench-compact.png', fullPage: true });
});
