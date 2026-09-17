import { test as base, expect } from '@playwright/test';
export const test = base.extend({
  page: async ({ page, request }, use) => {
    const response = await request.post('/api/test/reset', { headers: { 'X-Ace-Token': 'browser-test-session' } });
    expect(response.ok()).toBeTruthy();
    await use(page);
  },
});
export { expect };
