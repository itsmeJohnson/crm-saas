// Per-stage email automation config for the sales pipeline.
//
// Dragging a lead into a stage opens a confirmation dialog pre-filled from the
// matching config. Stages with `fields` prompt the agent for the details that
// stage needs; those values flow into a branded, professional HTML email.
// Matching is by a normalized substring of the stage name, so it survives
// renames/verticals.

export interface StageField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'datetime-local' | 'date' | 'select' | 'textarea';
  placeholder?: string;
  required?: boolean;
  options?: string[];
}

export interface DetailRow { label: string; key: string; }

export interface StageEmailConfig {
  match: string;            // lowercase substring matched against the stage name
  label: string;           // friendly action name shown in the dialog
  sendsEmail: boolean;
  subject?: string;        // {{token}} templated
  intro?: string;          // the editable, human paragraph(s) — {{token}} templated
  detailsTitle?: string;   // heading of the details card
  detailRows?: DetailRow[];// which fields appear in the details card
  signatureName?: string;  // sender line
  fields?: StageField[];   // manual inputs shown in the dialog
}

// ── Branding ──
export const AGENCY = 'Skyline Realty';
export const AGENCY_TAGLINE = 'Luxury Homes & Investment Advisory';
const ACCENT = '#0e7490';         // deep cyan — matches the CRM brand
const INK = '#1f2937';
const MUTED = '#6b7280';
const LINE = '#e5e7eb';
const CARD = '#f8fafc';

const CONFIGS: StageEmailConfig[] = [
  {
    match: 'site visit',
    label: 'Schedule site visit',
    sendsEmail: true,
    fields: [
      { key: 'visit_datetime', label: 'Visit date & time', type: 'datetime-local', required: true },
      { key: 'meeting_point', label: 'Meeting point / property address', type: 'text', required: true, placeholder: 'e.g. Emerald Valley Villa, Gate 2' },
      { key: 'chauffeur', label: 'Chauffeur pickup', type: 'select', options: ['Not required', 'Confirmed — pickup arranged'] },
    ],
    subject: 'Your site visit is confirmed — {{property}}',
    intro: `Your private site visit for {{property}} has been officially confirmed. Our senior advisor will meet you at the property with floor plans, pricing, and all relevant documents.`,
    detailsTitle: 'Visit Details & Logistics',
    detailRows: [
      { label: 'Scheduled time', key: 'visit_datetime' },
      { label: 'Meeting point', key: 'meeting_point' },
      { label: 'Chauffeur', key: 'chauffeur' },
      { label: 'Property', key: 'property' },
    ],
    signatureName: 'Client Relations Desk',
  },
  {
    match: 'quotation',
    label: 'Send quotation',
    sendsEmail: true,
    fields: [
      { key: 'quote_amount', label: 'Quoted price (₹)', type: 'text', required: true, placeholder: 'e.g. 2.4 Cr' },
      { key: 'valid_till', label: 'Offer valid till', type: 'date', required: true },
      { key: 'notes', label: 'Inclusions / notes', type: 'textarea', placeholder: 'Payment plan, parking, registration…' },
    ],
    subject: 'Your quotation for {{property}} — {{agency}}',
    intro: `Thank you for your interest in {{property}}. We're pleased to share our best offer below. Our team can also arrange financing assistance and a personalised payment plan.`,
    detailsTitle: 'Quotation Summary',
    detailRows: [
      { label: 'Property', key: 'property' },
      { label: 'Price', key: 'quote_amount' },
      { label: 'Valid till', key: 'valid_till' },
      { label: 'Inclusions', key: 'notes' },
    ],
    signatureName: 'Sales Advisory Team',
  },
  {
    match: 'booking',
    label: 'Record booking token',
    sendsEmail: true,
    fields: [
      { key: 'token_amount', label: 'Token / EOI amount (₹)', type: 'text', required: true, placeholder: 'e.g. 5,00,000' },
      { key: 'payment_ref', label: 'Payment reference', type: 'text', placeholder: 'UTR / receipt no.' },
      { key: 'next_step_date', label: 'Agreement date', type: 'date' },
    ],
    subject: 'Booking token received for {{property}} — {{agency}}',
    intro: `We're delighted to confirm your booking token for {{property}}. This secures the unit in your name while we prepare the agreement and next steps.`,
    detailsTitle: 'Booking Confirmation',
    detailRows: [
      { label: 'Property', key: 'property' },
      { label: 'Token amount', key: 'token_amount' },
      { label: 'Payment reference', key: 'payment_ref' },
      { label: 'Agreement date', key: 'next_step_date' },
    ],
    signatureName: 'Bookings & Documentation Desk',
  },
  {
    match: 'won',
    label: 'Confirm booking / welcome',
    sendsEmail: true,
    fields: [
      { key: 'handover_date', label: 'Handover / possession date', type: 'date' },
    ],
    subject: 'Welcome home, {{name}}! — {{agency}}',
    intro: `Congratulations and welcome to the {{agency}} family! Your booking for {{property}} is confirmed. Our team will guide you through the agreement and a smooth handover.`,
    detailsTitle: 'Your New Home',
    detailRows: [
      { label: 'Property', key: 'property' },
      { label: 'Possession', key: 'handover_date' },
    ],
    signatureName: 'Client Success Team',
  },
  {
    match: 'contacted',
    label: 'Send callback confirmation',
    sendsEmail: true,
    subject: 'Thank you for your enquiry, {{name}} — {{agency}}',
    intro: `Thank you for reaching out to {{agency}} regarding {{property}}. One of our property advisors will call you back shortly to understand your requirements and share matching options.`,
    signatureName: 'Client Relations Desk',
  },
  {
    match: 'qualified',
    label: 'Send callback confirmation',
    sendsEmail: true,
    subject: 'Thank you for your enquiry, {{name}} — {{agency}}',
    intro: `Thank you for reaching out to {{agency}} regarding {{property}}. One of our advisors will call you back shortly with matching options.`,
    signatureName: 'Client Relations Desk',
  },
];

export function configForStage(stageName: string): StageEmailConfig | null {
  const n = (stageName || '').toLowerCase();
  return CONFIGS.find((c) => n.includes(c.match)) || null;
}

/** Replace {{token}} in a template from a merged context. Missing → ''. */
export function fillTemplate(tpl: string, ctx: Record<string, any>): string {
  return (tpl || '').replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_m, k) => {
    const v = ctx[k];
    return v === undefined || v === null ? '' : String(v);
  });
}

/** Humanize a field value for display — ISO datetimes become readable dates. */
export function humanize(raw: any): string {
  const v = raw == null ? '' : String(raw).trim();
  if (!v) return '';
  // datetime-local: 2026-09-03T14:51  |  date: 2026-09-03
  if (/^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$/.test(v)) {
    const d = new Date(v);
    if (!isNaN(d.getTime())) {
      const hasTime = v.includes('T');
      return d.toLocaleString(undefined, {
        weekday: 'short', year: 'numeric', month: 'short', day: 'numeric',
        ...(hasTime ? { hour: 'numeric', minute: '2-digit' } : {}),
      });
    }
  }
  return v;
}

const esc = (s: string) => (s || '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' } as any)[c]);

/**
 * Build a polished, email-client-safe HTML message: brand header, greeting,
 * the (editable) intro paragraph, an optional details card, and a signature.
 */
export function buildEmailHtml(opts: {
  name: string;
  intro: string;
  detailsTitle?: string;
  rows?: { label: string; value: string }[];
  signatureName?: string;
}): string {
  const rows = (opts.rows || []).filter((r) => r.value && r.value.trim());
  const detailsCard = rows.length ? `
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${CARD};border:1px solid ${LINE};border-radius:12px;margin:20px 0;">
      ${opts.detailsTitle ? `<tr><td colspan="2" style="padding:16px 20px 4px;font:700 12px Arial,Helvetica,sans-serif;letter-spacing:.6px;text-transform:uppercase;color:${ACCENT};">${esc(opts.detailsTitle)}</td></tr>` : ''}
      ${rows.map((r) => `
        <tr>
          <td style="padding:7px 20px;font:400 14px Arial,Helvetica,sans-serif;color:${MUTED};width:42%;vertical-align:top;">${esc(r.label)}</td>
          <td style="padding:7px 20px;font:600 14px Arial,Helvetica,sans-serif;color:${INK};vertical-align:top;">${esc(r.value)}</td>
        </tr>`).join('')}
      <tr><td colspan="2" style="height:10px;line-height:10px;">&nbsp;</td></tr>
    </table>` : '';

  const introHtml = esc(opts.intro).split(/\n{2,}/).map((p) => `<p style="margin:0 0 14px;">${p.replace(/\n/g, '<br>')}</p>`).join('');

  return `
  <div style="background:#f1f5f9;padding:24px 0;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" align="center" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid ${LINE};">
      <tr><td style="padding:26px 32px 18px;border-bottom:3px solid ${ACCENT};">
        <div style="font:800 22px Arial,Helvetica,sans-serif;color:${ACCENT};letter-spacing:.3px;">${esc(AGENCY)}</div>
        <div style="font:600 11px Arial,Helvetica,sans-serif;color:${MUTED};letter-spacing:1.2px;text-transform:uppercase;margin-top:3px;">${esc(AGENCY_TAGLINE)}</div>
      </td></tr>
      <tr><td style="padding:26px 32px 30px;font:400 15px/1.7 Arial,Helvetica,sans-serif;color:${INK};">
        <p style="margin:0 0 14px;">Dear <b>${esc(opts.name)}</b>,</p>
        ${introHtml}
        ${detailsCard}
        <p style="margin:22px 0 0;">Warm regards,<br><b style="color:${INK};">${esc(opts.signatureName || 'Client Relations Desk')}</b><br><span style="color:${MUTED};">${esc(AGENCY)} · ${esc(AGENCY_TAGLINE)}</span></p>
      </td></tr>
      <tr><td style="padding:16px 32px;background:${CARD};border-top:1px solid ${LINE};font:400 11px Arial,Helvetica,sans-serif;color:${MUTED};">
        This message was sent by ${esc(AGENCY)}. If you weren't expecting it, please ignore this email.
      </td></tr>
    </table>
  </div>`;
}
