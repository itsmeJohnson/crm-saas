import { test, expect } from '@playwright/test';

test.describe('Phase 4: Global Design System & Unified Theming', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate and clear initial crm_theme once
    await page.goto('/login');
    await page.evaluate(() => localStorage.removeItem('crm_theme'));
  });

  test('TC-TH-01: Defaults to Light Theme and sets html.light class', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');

    // Document element should have 'light' class by default
    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('light');
    expect(htmlClass).not.toContain('dark');

    // Theme store should have initialized localStorage or default
    const themeInStorage = await page.evaluate(() => localStorage.getItem('crm_theme'));
    expect(themeInStorage === null || themeInStorage === 'light').toBeTruthy();
  });

  test('TC-TH-02: Toggles theme between Light and Dark with persistent localStorage & Anti-FOUC', async ({ page }) => {
    // Mock authenticated session
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-telecaller-token-12345');
      localStorage.setItem('refresh_token', 'mock-telecaller-refresh-12345');
      localStorage.setItem('user', JSON.stringify({
        id: '11111111-2222-3333-4444-555555555555',
        email: 'telecaller.agent@johnsonsoftwares.com',
        first_name: 'Alex',
        last_name: 'Caller',
        role: 'Employee',
        is_team_leader: false,
        organization_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
      }));
      localStorage.setItem('organization', JSON.stringify({
        id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
        name: 'Johnson Softwares CRM',
        subscription_status: 'active',
        crm_config: {
          industry: 'telecalling',
          template: 'telecalling',
          enabled_modules: ['dashboard', 'admin_core', 'platform_core', 'leads'],
        },
      }));
      localStorage.setItem('features', JSON.stringify(['all', 'telephony']));
    });

    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: {
            id: '11111111-2222-3333-4444-555555555555',
            email: 'telecaller.agent@johnsonsoftwares.com',
            first_name: 'Alex',
            last_name: 'Caller',
            role: 'Employee',
            is_team_leader: false,
            organization_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
          },
        }),
      });
    });

    await page.route('**/api/v1/attendance/today', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          record: { id: 'att-1', clock_in_at: '2026-10-24T09:00:00Z', clock_out_at: null },
          on_break: false,
        }),
      });
    });

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Initial state: Light theme
    let htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('light');

    // Click theme toggle button in header
    const toggleButton = page.locator('#theme-toggle-button');
    await expect(toggleButton).toBeVisible();
    await toggleButton.click();

    // Now state: Dark theme
    htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('dark');
    expect(htmlClass).not.toContain('light');

    // Verify localStorage persistence
    let savedTheme = await page.evaluate(() => localStorage.getItem('crm_theme'));
    expect(savedTheme).toBe('dark');

    // Reload page to test Anti-FOUC & persistence
    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    // After reload, document element must immediately remain dark
    htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('dark');

    // Toggle back to light
    const toggleButtonAfterReload = page.locator('#theme-toggle-button');
    await expect(toggleButtonAfterReload).toBeVisible();
    await toggleButtonAfterReload.click();

    htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('light');
    expect(htmlClass).not.toContain('dark');

    savedTheme = await page.evaluate(() => localStorage.getItem('crm_theme'));
    expect(savedTheme).toBe('light');
  });

  test('TC-TH-03: Inverts semantic CSS tokens accurately between Light and Dark themes', async ({ page }) => {
    await page.goto('/login');

    // In Light mode:
    const lightTokens = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        bgApp: style.getPropertyValue('--bg-app').trim(),
        textPrimary: style.getPropertyValue('--text-primary').trim(),
      };
    });

    // Toggle to Dark
    await page.evaluate(() => {
      document.documentElement.classList.remove('light');
      document.documentElement.classList.add('dark');
    });

    const darkTokens = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        bgApp: style.getPropertyValue('--bg-app').trim(),
        textPrimary: style.getPropertyValue('--text-primary').trim(),
      };
    });

    // Ensure tokens cleanly inverted
    expect(lightTokens.bgApp).not.toBe(darkTokens.bgApp);
    expect(lightTokens.textPrimary).not.toBe(darkTokens.textPrimary);
  });
});
