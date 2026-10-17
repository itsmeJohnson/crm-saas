/**
 * Telecalling Agency Navigation Configuration
 * Defines target agency groups and route-to-group mappings for single-tenant & agency deployments.
 */

export const TELECALLING_NAV_GROUPS = [
  "Lead Management",
  "Dialer Console",
  "Campaign Analytics",
  "Follow-ups & Reminders",
  "Administration"
];

export const TELECALLING_ITEM_GROUP_MAP: Record<string, string> = {
  // Lead Management
  "Leads & Enquiries": "Lead Management",
  "Contacts Directory": "Lead Management",
  "Lead Capture": "Lead Management",
  "Websites": "Lead Management",
  "Billing & Invoices": "Lead Management",
  "Companies": "Lead Management",
  "Customers": "Lead Management",
  "Pipelines": "Lead Management",

  // Dialer Console
  "Phone Calling": "Dialer Console",
  "Voice Broadcast": "Dialer Console",
  "WhatsApp Center": "Dialer Console",
  "Communications": "Dialer Console",

  // Campaign Analytics
  "Dashboard": "Campaign Analytics",
  "Marketing ROI": "Campaign Analytics",
  "Team Analytics": "Campaign Analytics",
  "Sales Analytics": "Campaign Analytics",
  "KPIs": "Campaign Analytics",
  "Report Builder": "Campaign Analytics",
  "AI Copilot": "Campaign Analytics",
  "Call Summaries": "Campaign Analytics",

  // Follow-ups & Reminders
  "Tasks & Reminders": "Follow-ups & Reminders",
  "Booking Links": "Follow-ups & Reminders",
  "Email Sequences": "Follow-ups & Reminders",
  "Follow-ups": "Follow-ups & Reminders",

  // Administration
  "Staff & Team": "Administration",
  "Call Center Settings": "Administration",
  "Clinic Settings": "Administration",
  "Settings": "Administration",
  "Custom Objects": "Administration",
  "Dynamic Forms": "Administration",
  "Organization": "Administration",
  "API & Developer": "Administration",
  "Integrations": "Administration",
};

/**
 * Returns true if the CRM should run in Telecalling mode.
 * Defaults to true for dedicated tenant deployments.
 */
export function isTelecallingMode(): boolean {
  const mode = import.meta.env.VITE_CRM_MODE;
  if (mode) {
    return mode.toLowerCase() === 'telecalling';
  }
  return true; // Default to telecalling mode for agency deployment
}
