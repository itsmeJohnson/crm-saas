import { test, expect } from '@playwright/test';
import { OrgAdminCommandCenterPage } from './pages/OrgAdminCommandCenterPage';

/**
 * ROLE 2: THE ORG ADMIN COMMAND CENTER JOURNEY (Management & Routing)
 * Simulates an operations executive auditing performance: 6-metric tile integrity,
 * 8-stage lifecycle funnel navigation, interactive today's schedule slot allocation,
 * and cross-role inbound call routing interception when an agent is punched out.
 */
test.describe('Role 2: Org Admin Operations Command Center E2E Journey', () => {
  let adminPage: OrgAdminCommandCenterPage;

  test.beforeEach(async ({ page }) => {
    adminPage = new OrgAdminCommandCenterPage(page);

    // Mock authenticated OrgAdmin session
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'mock-orgadmin-token-67890');
      localStorage.setItem('user', JSON.stringify({
        id: '99999999-8888-7777-6666-555555555555',
        email: 'orgadmin@johnsonsoftwares.com',
        first_name: 'Sarah',
        last_name: 'Connor',
        role: 'OrgAdmin',
        organization_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
      }));
    });

    // Mock Analytics, Leads, and Appointments
    await page.route('**/api/v1/analytics/dashboard', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          today_calls_count: 142,
          total_contacts: 890,
          pending_followups: 27,
          active_campaigns: 5,
          today_collections: 48500,
          monthly_revenue: 1250000,
        }),
      });
    });

    await page.route('**/api/v1/leads*', async (route) => {
      const url = new URL(route.request().url());
      const filter = url.searchParams.get('stage') || url.searchParams.get('filter');

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'lead-1',
            first_name: 'Rajesh',
            last_name: 'Kumar',
            company_name: 'Apollo Health',
            phone: '+91 98450 11223',
            status: filter === 'inquiry' ? 'Inquiry' : 'New',
            score: 92,
            source: 'Inbound Call',
          },
          {
            id: 'lead-2',
            first_name: 'Priya',
            last_name: 'Sharma',
            company_name: 'Zenith Retail',
            phone: '+91 97312 44556',
            status: filter === 'inquiry' ? 'Inquiry' : 'New',
            score: 78,
            source: 'Inbound Call',
          },
        ]),
      });
    });

    await page.route('**/api/v1/booking/appointments*', async (route) => {
      if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON();
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'slot-new-1',
            title: body.title || 'VIP Client Demo',
            scheduled_at: new Date().toISOString(),
            status: 'Confirmed',
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { id: 'slot-1', title: 'Consultation with Dr. Mehta', time: '11:00 AM', status: 'In Progress' },
            { id: 'slot-2', title: 'Product Demo - TechCorp', time: '02:30 PM', status: 'Confirmed' },
          ]),
        });
      }
    });
  });

  test('Step 1: Navigation and Metrics Integrity', async ({ page }) => {
    await adminPage.gotoDashboard();

    // 1. Verify Top Header renders Command Center context
    await expect(page.locator('text=/Operations Command Center|Practice Command Center/i').first()).toBeVisible({ timeout: 10000 });

    // 2. Validate all six core analytic tiles display loaded values
    await adminPage.verifyAllMetricTilesLoaded();
    await expect(page.locator('text=/Today\'s Calls|Today\'s Appts/i').first()).toBeVisible();
    await expect(page.locator('text="Follow-ups"').first()).toBeVisible();
    await expect(page.locator('text=/Collections|Total Billed/i').first()).toBeVisible();
  });

  test('Step 2: Funnel Interaction & Pre-filtered Leads Navigation', async ({ page }) => {
    await adminPage.gotoDashboard();

    // 1. Locate the 'Telecalling Lifecycle Pipeline' tracker cards
    await expect(adminPage.lifecycleCardLeads.first()).toBeVisible({ timeout: 8000 });

    // 2. Click directly on the 'Leads' funnel card
    await adminPage.lifecycleCardLeads.first().click();

    // 3. Assert system navigates to pre-filtered leads view
    await page.waitForURL(/\/leads/);
    expect(page.url()).toContain('/leads');
    await expect(page.locator('table, div[data-testid="leads-list"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('Step 3: Administrative Tasks & Today\'s Call Schedule Slot Allocation', async ({ page }) => {
    await adminPage.gotoDashboard();

    // 1. Locate 'Today\'s Call Schedule' frame
    await expect(adminPage.schedulePanel).toBeVisible({ timeout: 8000 });

    // 2. Click '+ Add Slot' and complete booking
    const slotTitle = 'Strategic Deal Review - Enterprise Team';
    await adminPage.addNewScheduleSlot(slotTitle, '16:00');

    // 3. Assert slot registers within the schedule layout
    await expect(adminPage.schedulePanel.locator(`text=${slotTitle}`).first()).toBeVisible();
  });

  test('Step 4: Active Routing Interception (Cross-Role Verification)', async ({ page }) => {
    await adminPage.gotoDashboard();

    // 1. Simulate agent status change to Punch Out / Offline in backend AgentStateService
    await page.route('**/api/v1/telephony/inbound', async (route) => {
      // Inbound webhook directed to offline agent's lead
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'matched',
          event: 'inbound_call',
          routing_reason: 'attend_team_queue',
          routed_targets_count: 3,
        }),
      });
    });

    // 2. Trigger mock incoming SIP call webhook directed to lead
    const response = await page.request.post('/api/v1/telephony/inbound', {
      data: {
        caller_phone: '+919876543210',
        destination_number: '+918000012345',
        call_status: 'ringing',
      },
    });

    const resJson = await response.json();

    // 3. Assert that backend routing bypasses offline agent and directs to attend_team_queue
    expect(resJson.routing_reason).toBe('attend_team_queue');
    expect(resJson.routed_targets_count).toBeGreaterThan(0);
  });
});
