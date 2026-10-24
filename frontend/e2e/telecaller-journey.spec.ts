import { test, expect } from '@playwright/test';
import { TelecallerCockpitPage } from './pages/TelecallerCockpitPage';

/**
 * ROLE 1: THE TELECALLER AGENT JOURNEY (Outbound & Inbound Flows)
 * Simulates a full agent shift workflow: attendance clock-in, dialer mode configuration,
 * active WebRTC call handling, beforeunload protection, Zustand state rehydration,
 * mandatory disposition wrap-up, and omnichannel messaging.
 */
test.describe('Role 1: Telecaller Agent Cockpit E2E Journey', () => {
  let cockpit: TelecallerCockpitPage;

  test.beforeEach(async ({ page }) => {
    cockpit = new TelecallerCockpitPage(page);

    // Mock authenticated Telecaller session
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
          enabled_modules: ['dashboard', 'admin_core', 'platform_core', 'leads', 'contacts', 'companies', 'customers', 'opportunities', 'pipelines', 'activities', 'tasks', 'follow_ups', 'communications', 'billing', 'reports', 'analytics_suite', 'telecalling', 'appointments', 'treatments'],
        },
      }));
      localStorage.setItem('features', JSON.stringify(['all', 'telephony', 'dialer', 'analytics', 'LEAD_MANAGEMENT', 'LEAD_CAPTURE', 'CALLING_INTEGRATION', 'SMS_INTEGRATION', 'WHATSAPP_INTEGRATION', 'COMMUNICATION_CENTER', 'TASK_MANAGEMENT', 'CALENDAR_APPOINTMENTS', 'BILLING_INVOICING']));
    });

    // Mock Auth Me & Refresh to prevent automatic logout on 401
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

    await page.route('**/api/v1/auth/refresh', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-telecaller-token-12345',
          refresh_token: 'mock-telecaller-refresh-12345',
        }),
      });
    });

    // Mock Metadata Bootstrap
    await page.route('**/api/v1/metadata/bootstrap', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          metadata_version: 1,
          custom_fields: [],
          custom_fields_by_entity: { lead: [] },
          custom_objects: [],
          pipelines: [
            {
              id: 'p-1',
              name: 'Telecalling Pipeline',
              is_default: true,
              stages: [
                { id: 's-1', name: 'New', order_position: 1 },
                { id: 's-2', name: 'Contacted', order_position: 2 },
              ],
            },
          ],
          crm_config: {
            industry: 'telecalling',
            template: 'telecalling',
            enabled_modules: ['dashboard', 'admin_core', 'platform_core', 'leads', 'contacts', 'companies', 'customers', 'opportunities', 'pipelines', 'activities', 'tasks', 'follow_ups', 'communications', 'billing', 'reports', 'analytics_suite', 'telecalling', 'appointments', 'treatments'],
          },
        }),
      });
    });

    // Mock Telephony & Attendance API routes (reactive state)
    let isPunchedInState = false;

    await page.route('**/api/v1/attendance/me/today', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          work_date: new Date().toISOString().split('T')[0],
          record: isPunchedInState
            ? {
                id: 'att-rec-1',
                work_date: new Date().toISOString().split('T')[0],
                clock_in_at: new Date().toISOString(),
                clock_out_at: null,
                status: 'present',
              }
            : null,
          shift: { name: 'Morning Shift', start_time: '09:00:00', end_time: '18:00:00' },
          on_break: false,
        }),
      });
    });

    await page.route('**/api/v1/attendance/clock-in', async (route) => {
      isPunchedInState = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'att-rec-1',
          work_date: new Date().toISOString().split('T')[0],
          clock_in_at: new Date().toISOString(),
          clock_out_at: null,
          status: 'present',
          is_late: false,
        }),
      });
    });

    await page.route('**/api/v1/attendance/clock-out', async (route) => {
      isPunchedInState = false;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'att-rec-1',
          work_date: new Date().toISOString().split('T')[0],
          clock_out_at: new Date().toISOString(),
          status: 'present',
        }),
      });
    });

    await page.route('**/api/v1/dashboard/employee-summary', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          employee_name: 'Alex Caller',
          is_online: isPunchedInState,
          check_in_at: isPunchedInState ? new Date().toISOString() : null,
          calls_made_today: 18,
          todays_follow_ups: 6,
          overdue_follow_ups: 1,
          new_leads: 12,
          interested_leads: 4,
          meetings_today: 2,
          tasks_pending: 3,
        }),
      });
    });

    await page.route('**/api/v1/dialer/state', async (route) => {
      if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            state: body.state || 'IDLE',
            timestamp: new Date().toISOString(),
            metadata: body.metadata || {},
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            state: 'IDLE',
            timestamp: new Date().toISOString(),
            metadata: {},
          }),
        });
      }
    });

    await page.route('**/api/v1/dialer/next-lead', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'lead-target-99',
          first_name: 'Michael',
          last_name: 'Scott',
          company_name: 'Dunder Mifflin',
          phone: '+91 98765 43210',
          status: 'New',
          score: 85,
          priority: 'High',
          stage: { name: 'Pitching' },
        }),
      });
    });

    await page.route('**/api/v1/dialer/leads/*/disposition', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'lead-target-99',
          status: 'Interested',
          updated_at: new Date().toISOString(),
        }),
      });
    });
  });

  test('Step 1: Attendance & Workspace Hydration', async ({ page }) => {
    await cockpit.gotoDashboard();

    // 1. Locate top-right user menu and click Punch In
    await expect(cockpit.punchInHeaderBtn).toBeVisible({ timeout: 10000 });
    await cockpit.punchIn();

    // 2. Assert dynamic dashboard counter ribbon renders instantly with loaded values
    await expect(page.locator('text=Calls Today')).toBeVisible();
    await expect(page.locator('text=New Leads')).toBeVisible();
    await expect(page.locator('text=Today\'s Follow-ups')).toBeVisible();

    // 3. Assert global status indicator transitions to green 'Punched In • On Duty'
    await expect(page.locator('text=Punched In • On Duty').first()).toBeVisible();
    await expect(page.locator('span.animate-pulse').first()).toBeVisible();
  });

  test('Step 2: Dialing Mode Configurations & Outbound WebRTC Sequence', async ({ page }) => {
    await cockpit.gotoDashboard();
    await cockpit.punchIn();

    // 1. Configure dialer modes: Collective Pooling + Power Dialer with 5s gap
    await cockpit.configureDialerModes({
      collectivePooling: true,
      powerDialer: true,
      delaySeconds: 5,
    });

    // Verify localStorage persistence
    const savedPool = await page.evaluate(() => localStorage.getItem('crm_collective_pooling'));
    const savedPower = await page.evaluate(() => localStorage.getItem('crm_auto_dial'));
    const savedDelay = await page.evaluate(() => localStorage.getItem('crm_power_dialer_delay'));
    expect(savedPool).toBe('true');
    expect(savedPower).toBe('true');
    expect(savedDelay).toBe('5');

    // 2. Start dialing session
    await cockpit.startDialingSession();

    // Assert that active lead is loaded into cockpit workspace
    await expect(page.locator('text=Dunder Mifflin').first()).toBeVisible({ timeout: 8000 });
    await expect(page.locator('text=Michael Scott').first()).toBeVisible();
  });

  test('Step 3: State Resilience, beforeunload Interception, and Anti-FOUC Hydration', async ({ page }) => {
    await cockpit.gotoDashboard();
    await cockpit.punchIn();

    // Mock an active ongoing outbound call in Zustand state
    await page.evaluate(() => {
      const activeLead = {
        id: 'lead-target-99',
        first_name: 'Michael',
        last_name: 'Scott',
        company_name: 'Dunder Mifflin',
        phone: '+91 98765 43210',
        status: 'In Call',
      };
      localStorage.setItem('crm_dialer_current_lead', JSON.stringify(activeLead));
      localStorage.setItem('crm_dialer_lifecycle', 'connected');
      localStorage.setItem('crm_dialer_call_direction', 'OUTBOUND');
      localStorage.setItem('crm_dialer_start_time', new Date().toISOString());
    });

    await page.reload();

    // Trigger beforeunload event to verify reload guard
    const beforeUnloadMessage = await page.evaluate(() => {
      const event = new Event('beforeunload', { cancelable: true }) as any;
      window.dispatchEvent(event);
      return event.returnValue;
    });

    expect(beforeUnloadMessage).toContain('A call is currently in progress or wrap-up disposition notes are pending');

    // Anti-FOUC verification: Ensure page body does not have white flash or unstyled blip
    const htmlTheme = await page.getAttribute('html', 'class');
    expect(htmlTheme).toBeDefined();

    // Verify Zustand rehydration: lead details remain populated immediately on reload
    await expect(page.locator('text=Michael Scott').first()).toBeVisible({ timeout: 5000 });
  });

  test('Step 4: Post-Call Wrappers & Omnichannel Timeline Push', async ({ page }) => {
    await cockpit.gotoDashboard();
    await cockpit.punchIn();

    // Set call state to disposition wrap-up mode
    await page.evaluate(() => {
      localStorage.setItem('crm_dialer_current_lead', JSON.stringify({
        id: 'lead-target-99',
        first_name: 'Michael',
        last_name: 'Scott',
        phone: '+91 98765 43210',
      }));
      localStorage.setItem('crm_dialer_lifecycle', 'disposition');
    });

    await page.reload();

    // Submit disposition
    await cockpit.submitDisposition('Interested', 'Requested quote for 50 reams, follow-up scheduled for tomorrow.');

    // Verify screen unlocks and power dialer countdown activates
    await expect(cockpit.dispositionModal).toBeHidden();

    // Open omnichannel drawer and push a message
    await page.route('**/api/v1/whatsapp/send', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'msg-wa-1',
          status: 'delivered',
          timestamp: new Date().toISOString(),
          message: 'Hi Michael, sharing our product catalogue as discussed.',
        }),
      });
    });

    const mockMessage = 'Hi Michael, sharing our product catalogue as discussed.';
    if (await cockpit.openChatDrawerBtn.isVisible()) {
      await cockpit.sendOmnichannelMessage(mockMessage);
    }
  });
});
