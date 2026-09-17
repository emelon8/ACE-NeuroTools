import { test, expect } from './fixtures';

test('renders the real IDE shell and local Monaco workers', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/#token=browser-test-session');
  await expect(page.getByRole('navigation', { name: 'Workbench views' })).toBeVisible();
  await expect(page.locator('.monaco-editor')).toBeVisible();
  await expect(page.getByLabel('Selected experiment')).toHaveValue(/.+/);
  await expect(page.getByRole('log')).toContainText('Connected to local EVC');
  await expect(page).toHaveURL('http://127.0.0.1:8766/');
  await page.screenshot({ path: 'test-results/workbench-desktop.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('edits real parameters, records history and retains state after reload', async ({ page }) => {
  await page.goto('/#token=browser-test-session');
  await page.getByRole('button', { name: 'Parameters', exact: true }).click();
  await page.getByRole('spinbutton', { name: 'min_corr', exact: true }).fill('0.92');
  await page.getByRole('spinbutton', { name: 'min_corr', exact: true }).press('Tab');
  await expect(page.locator('.document-footer')).toContainText('Unsaved');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('log')).toContainText('Saved parameters/analysis.cnmfe.json');
  await page.getByRole('button', { name: 'Experiment changes', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'params.min_corr', exact: true })).toBeVisible();
  await page.getByLabel('Revision message').fill('Browser-verified correlation threshold');
  await page.getByRole('button', { name: 'Record revision', exact: true }).click();
  await expect(page.getByRole('log')).toContainText('Recorded revision');
  await page.getByRole('navigation').getByRole('button', { name: 'History', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Browser-verified correlation threshold', exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Parameters', exact: true }).click();
  await expect(page.getByRole('spinbutton', { name: 'min_corr', exact: true })).toHaveValue('0.92');
});

test('keyboard palette and experiment switch work', async ({ page }) => {
  await page.goto('/#token=browser-test-session');
  await page.getByRole('button', { name: 'Search commands' }).click();
  await expect(page.getByRole('dialog', { name: 'Command palette' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Find command' }).fill('recovery');
  await page.getByRole('textbox', { name: 'Find command' }).press('Enter');
  await expect(page.getByRole('heading', { name: 'Recovery journal' })).toBeVisible();
  const options = await page.getByLabel('Selected experiment').locator('option').all();
  await page.getByLabel('Selected experiment').selectOption(await options[1].getAttribute('value') as string);
  await expect(page.getByRole('heading', { name: '02-paired-recording-demo', exact: true })).toBeVisible();
});
