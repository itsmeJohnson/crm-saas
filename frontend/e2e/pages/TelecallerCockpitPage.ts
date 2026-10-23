import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the Telecaller Agent Cockpit.
 * Encapsulates attendance controls, dialer console configuration,
 * active WebRTC call states, disposition modals, and omnichannel messaging.
 */
export class TelecallerCockpitPage {
  readonly page: Page;

  // Header Attendance Elements
  readonly punchInHeaderBtn: Locator;
  readonly punchOutHeaderBtn: Locator;
  readonly resumeShiftHeaderBtn: Locator;
  readonly attendanceStatusBadge: Locator;

  // Agent Hero Metric Ribbon
  readonly callsTodayMetric: Locator;
  readonly followupsTodayMetric: Locator;
  readonly overdueFollowupsMetric: Locator;
  readonly newLeadsMetric: Locator;
  readonly heroStatusBadge: Locator;

  // Dialer Console Controls
  readonly dialerConsoleCard: Locator;
  readonly collectivePoolingCheckbox: Locator;
  readonly powerDialerCheckbox: Locator;
  readonly powerDialerDelaySelect: Locator;
  readonly startDialingSessionBtn: Locator;
  readonly powerDialerCountdownBanner: Locator;
  readonly agentStateBadge: Locator;

  // Active Call & Post-Call Disposition Modal
  readonly activeCallCard: Locator;
  readonly endCallBtn: Locator;
  readonly dispositionModal: Locator;
  readonly dispositionStatusSelect: Locator;
  readonly dispositionRemarksTextarea: Locator;
  readonly saveDispositionBtn: Locator;
  readonly leadTimeline: Locator;

  // Omnichannel Chat Drawer
  readonly openChatDrawerBtn: Locator;
  readonly chatDrawer: Locator;
  readonly chatMessageInput: Locator;
  readonly sendChatBtn: Locator;
  readonly chatMessageList: Locator;

  constructor(page: Page) {
    this.page = page;

    // Header Selectors
    this.punchInHeaderBtn = page.locator('button:has-text("Punch In")');
    this.punchOutHeaderBtn = page.locator('button:has-text("Punch Out")');
    this.resumeShiftHeaderBtn = page.locator('button:has-text("Resume Shift")');
    this.attendanceStatusBadge = page.locator('text=/On Duty|On Break|Shift Ended|Off Duty/i').first();

    // Hero Metric Ribbon Selectors
    this.callsTodayMetric = page.locator('text=Calls Today').locator('xpath=following-sibling::p').first();
    this.followupsTodayMetric = page.locator("text=Today's Follow-ups").locator('xpath=following-sibling::p').first();
    this.overdueFollowupsMetric = page.locator('text=Overdue Follow-ups').locator('xpath=following-sibling::p').first();
    this.newLeadsMetric = page.locator('text=New Leads').locator('xpath=following-sibling::p').first();
    this.heroStatusBadge = page.locator('text=/Punched In • On Duty|Punched Out • Shift Ended|Not Punched In/i').first();

    // Dialer Console Selectors
    this.dialerConsoleCard = page.locator('h2:has-text("Agent Console")').locator('xpath=ancestor::div[contains(@class, "bg-slate-900")]').first();
    this.collectivePoolingCheckbox = page.locator('#collective-pooling');
    this.powerDialerCheckbox = page.locator('#auto-dial');
    this.powerDialerDelaySelect = page.locator('select[aria-label="Power dialer delay"]');
    this.startDialingSessionBtn = page.locator('button:has-text("Start Dialing Session")');
    this.powerDialerCountdownBanner = page.locator('text=/Power dialer: next call in \\d+s/i');
    this.agentStateBadge = page.locator('text=/IDLE|ACTIVE_CALLING|BREAK/i').first();

    // Call Lifecycle & Disposition Selectors
    this.activeCallCard = page.locator('text=/Connected|In Call|Active Calling|Outbound Call/i').first();
    this.endCallBtn = page.locator('button:has-text("End Call"), button:has-text("Hangup"), button[title*="Hangup"]');
    this.dispositionModal = page.locator('text=/Call Disposition|Wrap-up Notes/i').locator('xpath=ancestor::div[contains(@class, "fixed")]').first();
    this.dispositionStatusSelect = page.locator('button:has-text("Interested"), select[name="status"]');
    this.dispositionRemarksTextarea = page.locator('textarea[placeholder*="notes" i], textarea');
    this.saveDispositionBtn = page.locator('button:has-text("Save Call Disposition"), button:has-text("Submit Disposition")');
    this.leadTimeline = page.locator('text=/Lead Activity Timeline|Call History/i').locator('xpath=ancestor::div').first();

    // Omnichannel Chat Selectors
    this.openChatDrawerBtn = page.locator('button[title*="Chat" i], button:has-text("WhatsApp"), button:has-text("Chat")');
    this.chatDrawer = page.locator('text=/WhatsApp Conversation|Live Chat/i').locator('xpath=ancestor::div[contains(@class, "fixed")]').first();
    this.chatMessageInput = page.locator('input[placeholder*="Type a message" i], textarea[placeholder*="message" i]');
    this.sendChatBtn = page.locator('button[title*="Send" i], button:has-text("Send")');
    this.chatMessageList = page.locator('div[data-testid="chat-stream"], div[class*="overflow-y-auto"]');
  }

  async gotoDashboard() {
    await this.page.goto('/');
    await this.page.waitForLoadState('networkidle');
  }

  async punchIn() {
    if (await this.punchInHeaderBtn.isVisible()) {
      await this.punchInHeaderBtn.click();
    } else if (await this.resumeShiftHeaderBtn.isVisible()) {
      await this.resumeShiftHeaderBtn.click();
    }
    // Wait for the status indicator to update reactively
    await expect(this.page.locator('text=Punched In • On Duty').first()).toBeVisible({ timeout: 10000 });
  }

  async punchOut() {
    if (await this.punchOutHeaderBtn.isVisible()) {
      await this.punchOutHeaderBtn.click();
      const confirmBtn = this.page.locator('button:has-text("Confirm Punch Out")');
      if (await confirmBtn.isVisible()) {
        await confirmBtn.click();
      }
      await expect(this.page.locator('text=/Shift Ended|Off Duty/i').first()).toBeVisible({ timeout: 10000 });
    }
  }

  async configureDialerModes(options: { collectivePooling: boolean; powerDialer: boolean; delaySeconds: number }) {
    await this.dialerConsoleCard.waitFor({ state: 'visible' });

    // Configure Collective Pooling
    const isPoolChecked = await this.collectivePoolingCheckbox.isChecked();
    if (isPoolChecked !== options.collectivePooling) {
      await this.collectivePoolingCheckbox.setChecked(options.collectivePooling);
    }

    // Configure Power Dialer
    const isPowerChecked = await this.powerDialerCheckbox.isChecked();
    if (isPowerChecked !== options.powerDialer) {
      await this.powerDialerCheckbox.setChecked(options.powerDialer);
    }

    // Select gap interval
    if (options.powerDialer) {
      await expect(this.powerDialerDelaySelect).toBeVisible();
      await this.powerDialerDelaySelect.selectOption(String(options.delaySeconds));
    }
  }

  async startDialingSession() {
    await this.startDialingSessionBtn.click();
  }

  async submitDisposition(status: string, remarks: string) {
    await expect(this.dispositionModal).toBeVisible({ timeout: 10000 });
    const targetOutcomeBtn = this.page.locator(`button:has-text("${status}")`).first();
    if (await targetOutcomeBtn.isVisible()) {
      await targetOutcomeBtn.click();
    } else {
      await this.dispositionStatusSelect.selectOption(status);
    }

    await this.dispositionRemarksTextarea.fill(remarks);
    await this.saveDispositionBtn.click();
    await expect(this.dispositionModal).toBeHidden({ timeout: 10000 });
  }

  async sendOmnichannelMessage(text: string) {
    if (await this.openChatDrawerBtn.isVisible()) {
      await this.openChatDrawerBtn.first().click();
    }
    await expect(this.chatDrawer).toBeVisible({ timeout: 8000 });
    await this.chatMessageInput.fill(text);
    await this.sendChatBtn.click();
    await expect(this.page.locator(`text="${text}"`).first()).toBeVisible({ timeout: 5000 });
  }
}
