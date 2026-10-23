import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the Org Admin - Telecalling Operations Command Center.
 * Encapsulates the 6-Metric Ribbon, 8-Stage Lifecycle Funnel Cards, Today's Call Schedule,
 * Follow-up Queues, and Channel Acquisition analytics.
 */
export class OrgAdminCommandCenterPage {
  readonly page: Page;

  // Header and Refresh
  readonly orgTitle: Locator;
  readonly refreshDataBtn: Locator;
  readonly newLeadQuickBtn: Locator;

  // Bento 6-Metric Tiles
  readonly metricTodayCalls: Locator;
  readonly metricContacts: Locator;
  readonly metricFollowups: Locator;
  readonly metricCampaigns: Locator;
  readonly metricCollections: Locator;
  readonly metricMonthlyRevenue: Locator;

  // 8-Stage Lifecycle Pipeline Cards
  readonly lifecycleCardMarketing: Locator;
  readonly lifecycleCardLeads: Locator;
  readonly lifecycleCardFollowup: Locator;
  readonly lifecycleCardCallsAppts: Locator;
  readonly lifecycleCardContacts: Locator;
  readonly lifecycleCardCampaigns: Locator;
  readonly lifecycleCardBilling: Locator;
  readonly lifecycleCardRetention: Locator;

  // Today's Call Schedule Panel
  readonly schedulePanel: Locator;
  readonly addSlotBtn: Locator;
  readonly addSlotModal: Locator;
  readonly slotTitleInput: Locator;
  readonly slotTimeInput: Locator;
  readonly slotSubmitBtn: Locator;

  // Inbound Call Attend Group Panel
  readonly attendTeamQueueCard: Locator;

  constructor(page: Page) {
    this.page = page;

    // Header
    this.orgTitle = page.locator('h1').first();
    this.refreshDataBtn = page.locator('button:has-text("Refresh")').first();
    this.newLeadQuickBtn = page.locator('button:has-text("New Lead"), button:has-text("New Enquiry")').first();

    // 6-Metric Tiles (matching bento-card containers)
    this.metricTodayCalls = page.locator('text=/Today\'s Calls|Today\'s Appts/i').locator('xpath=following-sibling::div').first();
    this.metricContacts = page.locator('text=/Contacts|Patients/i').locator('xpath=following-sibling::div').first();
    this.metricFollowups = page.locator('text="Follow-ups"').locator('xpath=following-sibling::div').first();
    this.metricCampaigns = page.locator('text=/Campaigns|Treatments/i').locator('xpath=following-sibling::div').first();
    this.metricCollections = page.locator('text=/Collections|Total Billed/i').locator('xpath=following-sibling::div').first();
    this.metricMonthlyRevenue = page.locator('text=/Monthly|Revenue/i').locator('xpath=following-sibling::div').first();

    // 8 Lifecycle Pipeline Cards
    this.lifecycleCardMarketing = page.locator('div.bento-card:has-text("Marketing")');
    this.lifecycleCardLeads = page.locator('div.bento-card:has-text("Leads")');
    this.lifecycleCardFollowup = page.locator('div.bento-card:has-text("Follow-up")');
    this.lifecycleCardCallsAppts = page.locator('div.bento-card:has-text("Calls / Appts"), div.bento-card:has-text("Appointments")');
    this.lifecycleCardContacts = page.locator('div.bento-card:has-text("Contacts"), div.bento-card:has-text("Patients")');
    this.lifecycleCardCampaigns = page.locator('div.bento-card:has-text("Campaigns"), div.bento-card:has-text("Treatments")');
    this.lifecycleCardBilling = page.locator('div.bento-card:has-text("Billing")');
    this.lifecycleCardRetention = page.locator('div.bento-card:has-text("Retention"), div.bento-card:has-text("Recall")');

    // Today's Call Schedule
    this.schedulePanel = page.locator('text=/Today\'s Call Schedule|Today\'s Operatory Schedule/i').locator('xpath=ancestor::div[contains(@class, "bento-card")]').first();
    this.addSlotBtn = this.schedulePanel.locator('button:has-text("Add Slot")');
    this.addSlotModal = page.locator('text=/Book Appointment|Schedule Call Slot/i').locator('xpath=ancestor::div[contains(@class, "fixed")]').first();
    this.slotTitleInput = page.locator('input[name="title"], input[placeholder*="Patient" i], input[placeholder*="Lead" i]');
    this.slotTimeInput = page.locator('input[type="time"], input[name="time"]');
    this.slotSubmitBtn = page.locator('button:has-text("Save Slot"), button:has-text("Confirm Booking"), button[type="submit"]');

    // Attend Team Queue
    this.attendTeamQueueCard = page.locator('text=/Incoming Call Attend Team|Available Agents Queue/i').locator('xpath=ancestor::div').first();
  }

  async gotoDashboard() {
    await this.page.goto('/');
    await this.page.waitForLoadState('networkidle');
  }

  async verifyAllMetricTilesLoaded() {
    await expect(this.metricTodayCalls).toBeVisible();
    await expect(this.metricContacts).toBeVisible();
    await expect(this.metricFollowups).toBeVisible();
    await expect(this.metricCampaigns).toBeVisible();
    await expect(this.metricCollections).toBeVisible();
  }

  async clickLifecycleStage(stageName: 'Marketing' | 'Leads' | 'Follow-up' | 'Billing') {
    const card = this.page.locator(`div.bento-card:has-text("${stageName}")`).first();
    await expect(card).toBeVisible();
    await card.click();
    await this.page.waitForLoadState('networkidle');
  }

  async addNewScheduleSlot(slotName: string, timeStr = '14:30') {
    await this.addSlotBtn.click();
    await expect(this.addSlotModal).toBeVisible({ timeout: 8000 });

    if (await this.slotTitleInput.isVisible()) {
      await this.slotTitleInput.fill(slotName);
    }
    if (await this.slotTimeInput.isVisible()) {
      await this.slotTimeInput.fill(timeStr);
    }

    await this.slotSubmitBtn.click();
    await expect(this.addSlotModal).toBeHidden({ timeout: 8000 });
    await expect(this.schedulePanel.locator(`text="${slotName}"`).first()).toBeVisible({ timeout: 10000 });
  }
}
