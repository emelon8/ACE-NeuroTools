import AxeBuilder from '@axe-core/playwright';
import { test, expect } from './fixtures';

const trace = 'time_s,signal\n0,1\n0.5,3\n1,5\n';

test('drop recording, answer only missing units, create experiment, preflight and run', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/#token=browser-test-session');
  await page.getByRole('navigation').getByRole('button', { name: 'Import & Run', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Drop recording files or a folder here' })).toBeVisible();
  await page.evaluate(content => {
    const data = new DataTransfer();
    data.items.add(new File([content], 'recorded-traces.csv', { type: 'text/csv' }));
    document.querySelector('.recording-drop')!.dispatchEvent(new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true }));
  }, trace);
  await expect(page.getByRole('heading', { name: 'Set up this recording' })).toBeVisible();
  await expect(page.getByLabel('Time column', { exact: true })).toHaveCount(0);
  await page.getByLabel('Experiment name', { exact: true }).fill('Browser recording');
  await page.getByLabel('Signal unit', { exact: true }).fill('uV');
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(audit.violations).toEqual([]);
  await page.screenshot({ path: 'test-results/workflow-setup.png', fullPage: true });
  await page.getByRole('button', { name: 'Create experiment', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Preflight run', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Preflight run', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Review run configuration' })).toBeVisible();
  await page.screenshot({ path: 'test-results/workflow-preflight.png', fullPage: true });
  await page.getByRole('button', { name: 'Run approved configuration', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'trace-summary · succeeded' })).toBeVisible();
  await page.screenshot({ path: 'test-results/workflow-complete.png', fullPage: true });
  await page.getByRole('button', { name: 'Browse run results', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'trace-summary.json', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('file picker exposes generic timing questions and permits reconfiguration', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/#token=browser-test-session');
  await page.getByRole('navigation').getByRole('button', { name: 'Import & Run', exact: true }).click();
  await page.getByTestId('recording-files').setInputFiles({ name: 'generic.csv', mimeType: 'text/csv', buffer: Buffer.from('clock,x\n0,2\n10,4\n20,6\n') });
  await page.getByLabel('Experiment name', { exact: true }).fill('Generic timing');
  await page.getByLabel('Time column', { exact: true }).selectOption('clock');
  await page.getByLabel('Time unit', { exact: true }).selectOption('milliseconds');
  await page.getByLabel('Signal unit', { exact: true }).fill('arbitrary units');
  await page.screenshot({ path: 'test-results/workflow-compact.png', fullPage: true });
  await page.getByRole('button', { name: 'Create experiment', exact: true }).click();
  await page.getByRole('button', { name: 'Edit workflow settings', exact: true }).click();
  await expect(page.getByLabel('Time unit', { exact: true })).toHaveValue('milliseconds');
  await page.getByLabel('Signal unit', { exact: true }).fill('mV');
  await page.getByRole('button', { name: 'Save workflow settings', exact: true }).click();
  await page.getByRole('button', { name: 'Preflight run', exact: true }).click();
  await expect(page.locator('.workflow-json').first()).toContainText('mV');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test('incomplete acquisition blocks scientific setup and keeps integrity inspection explicit', async ({ page }) => {
  await page.goto('/#token=browser-test-session');
  await page.getByRole('navigation').getByRole('button', { name: 'Import & Run', exact: true }).click();
  await page.getByTestId('recording-files').setInputFiles({ name: 'metaData.json', mimeType: 'application/json', buffer: Buffer.from('{"frameRate":20}') });
  await expect(page.getByRole('button', { name: 'Create experiment', exact: true })).toBeDisabled();
  await expect(page.locator('.workflow-error')).toContainText('No AVI');
  await page.getByLabel('Operation', { exact: true }).selectOption('inventory');
  await expect(page.getByRole('button', { name: 'Create experiment', exact: true })).toBeEnabled();
  await expect(page.getByText('Hash and inventory the copied files. No signal processing or biological conclusions.', { exact: true })).toBeVisible();
});

test('multiple recordings require an explicit selection', async ({ page }) => {
  await page.goto('/#token=browser-test-session');
  await page.getByRole('navigation').getByRole('button', { name: 'Import & Run', exact: true }).click();
  await page.getByTestId('recording-files').setInputFiles([
    { name: 'first.csv', mimeType: 'text/csv', buffer: Buffer.from(trace) },
    { name: 'second.csv', mimeType: 'text/csv', buffer: Buffer.from(trace) },
  ]);
  await expect(page.getByRole('heading', { name: 'Choose a recording', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create experiment', exact: true })).toHaveCount(0);
  await page.getByLabel('Detected recording', { exact: true }).selectOption({ label: 'Trace table · second.csv · .' });
  await expect(page.getByRole('heading', { name: 'Set up this recording', exact: true })).toBeVisible();
});

test('an empty project opens directly into the recording workflow', async ({ page, request }) => {
  await request.post('/api/test/reset?empty=true', { headers: { 'X-Ace-Token': 'browser-test-session' } });
  await page.goto('/#token=browser-test-session');
  await expect(page.getByRole('heading', { name: 'Drop recording files or a folder here' })).toBeVisible();
  await expect(page.getByText('No experiments yet. Drop a recording to create your first experiment.', { exact: true })).toBeVisible();
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(audit.violations).toEqual([]);
});
