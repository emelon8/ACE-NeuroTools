import { test, expect } from '@playwright/test';

test('compares revisions and restores without rewinding history', async ({ page }) => {
  await page.goto('/#token=browser-test-session');
  await page.getByRole('navigation').getByRole('button', { name: 'History', exact: true }).click();
  await expect(page.locator('.history-row')).toHaveCount(3);
  await page.getByRole('button', { name: 'Compare to HEAD', exact: true }).last().click();
  await expect(page.locator('.monaco-diff-editor')).toBeVisible();
  await page.getByRole('navigation').getByRole('button', { name: 'History', exact: true }).click();
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Restore revision', exact: true }).last().click();
  await expect(page.getByRole('heading', { name: 'Experiment changes', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'params.min_corr', exact: true })).toBeVisible();
  await page.getByLabel('Revision message').fill('Retain restored baseline');
  await page.getByRole('button', { name: 'Record revision', exact: true }).click();
  await expect(page.getByRole('log')).toContainText('Recorded revision');
  await page.getByRole('navigation').getByRole('button', { name: 'History', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Retain restored baseline', exact: true })).toBeVisible();
  await expect(page.locator('.history-row')).toHaveCount(4);
  await page.getByRole('button', { name: 'Retain restored baseline', exact: true }).click();
  await page.getByLabel('Revision comment').fill('Reviewed in the browser');
  await page.getByRole('button', { name: 'Add comment', exact: true }).click();
  await expect(page.locator('.comment-thread')).toContainText('Reviewed in the browser');
  // Return tracked manifests to their original state for independent results tests.
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Restore revision', exact: true }).nth(1).click();
  await expect(page.getByRole('log')).toContainText('Restored');
});

test('verifies actual artifacts and renders data preview', async ({ page }) => {
  await page.goto('/#token=browser-test-session');
  await page.getByRole('navigation').getByRole('button', { name: 'Results', exact: true }).click();
  await page.getByRole('button', { name: 'Verify integrity', exact: true }).click();
  await expect(page.locator('.result-run')).toContainText('Verified · 1 artifact(s)');
  await page.getByRole('button', { name: 'synthetic-traces.csv', exact: true }).click();
  await expect(page.getByRole('img', { name: /Artifact preview/ })).toBeVisible();
  await expect(page.locator('.artifact-preview')).toContainText('400 rows shown');
  await page.screenshot({ path: 'test-results/workbench-results.png', fullPage: true });
});

test('protects unsaved edits and exposes schema errors', async ({ page }) => {
  await page.goto('/#token=browser-test-session');
  await page.getByRole('button', { name: 'Parameters', exact: true }).click();
  await page.getByRole('spinbutton', { name: 'min_corr', exact: true }).fill('0.99');
  await page.getByRole('spinbutton', { name: 'min_corr', exact: true }).press('Tab');
  await page.getByRole('navigation').getByRole('button', { name: 'Experiment changes', exact: true }).click();
  await page.getByLabel('Revision message').fill('Must not record unsaved buffer');
  await page.getByRole('button', { name: 'Record revision', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Save or close unsaved editor buffers');
  page.once('dialog', dialog => dialog.dismiss());
  const previous = await page.getByLabel('Selected experiment').inputValue();
  await page.getByLabel('Selected experiment').selectOption({ index: 1 });
  await expect(page.getByLabel('Selected experiment')).toHaveValue(previous);
});
