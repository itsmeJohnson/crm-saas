// Legal document content — TEMPLATE. Have qualified legal counsel review and
// adapt (entity name, governing-law jurisdiction, contact details) before you
// rely on this in production. Framed for both India (TRAI/DLT, DPDP Act 2023)
// and the US (TCPA, A2P 10DLC, CCPA). Placeholders in [brackets] must be filled.

export type LegalSection = { h: string; p: string[] };
export type LegalDoc = { key: string; label: string; title: string; updated: string; intro: string; sections: LegalSection[] };

const COMPANY = 'Johnson Softwares';           // [Registered Entity Name]
const PLATFORM = 'the CRM Platform';
const CONTACT = 'contact@support.johnsonsoftwares.com';

const TERMS: LegalDoc = {
  key: 'terms',
  label: 'Terms of Service',
  title: 'Terms of Service',
  updated: '2026-07-28',
  intro: `These Terms of Service ("Terms") govern your access to and use of ${PLATFORM} operated by ${COMPANY} ("we", "us"). By creating an account or using the service, you ("Customer", "you") agree to these Terms.`,
  sections: [
    {
      h: '1. The service is a software layer only (BYOK)',
      p: [
        `${PLATFORM} is a multi-tenant software interface for managing sales, contacts and communications. It follows a "Bring Your Own Key" (BYOK) model: you connect your own third-party provider accounts (e.g. Meta WhatsApp Cloud API, Twilio, Exotel, Plivo, MSG91, Fast2SMS) using credentials you obtain and control.`,
        `We do not originate, transmit, or terminate voice calls, SMS, or WhatsApp messages ourselves and we are not a telecom operator, carrier, aggregator, or reseller. When you trigger a message or call, it is executed through your own provider account using your credentials.`,
      ],
    },
    {
      h: '2. Third-party charges are billed directly to you',
      p: [
        `All messaging, voice-calling, WhatsApp, and voice-note usage is billed to you directly by the third-party provider you configure (Meta, Twilio, Exotel, MSG91, etc.) under your agreement with that provider. Our subscription fee for ${PLATFORM} is separate and covers only the software.`,
        `We are not responsible for third-party pricing, billing disputes, service outages, deprecations, rate limits, or account suspensions imposed by those providers.`,
      ],
    },
    {
      h: '3. Your compliance & anti-spam responsibility',
      p: [
        `You are solely responsible for obtaining valid, documented consent/opt-in from every recipient before sending any message or placing any call, and for complying with all applicable laws and provider policies, including without limitation:`,
        `• India — TRAI TCCCPR / DLT registration (Entity ID, Header/Sender ID, and approved templates), and the Digital Personal Data Protection Act, 2023 (DPDP).`,
        `• United States — the Telephone Consumer Protection Act (TCPA), A2P 10DLC campaign registration, and applicable state privacy laws (e.g. CCPA/CPRA).`,
        `• Meta WhatsApp Business Messaging Policy and Commerce Policy, and the terms of every other provider you connect.`,
        `${COMPANY} holds zero liability for account bans, message blocking, fines, or legal penalties resulting from spam, missing consent, unapproved templates, or unsolicited messaging sent through your connected accounts. You will indemnify us against claims arising from your messaging.`,
      ],
    },
    {
      h: '4. Acceptable use',
      p: [
        `You will not use ${PLATFORM} to send unlawful, deceptive, harassing, or unsolicited content; to violate any provider policy; to attempt to overload, probe, or disrupt the platform (including automated scraping or denial-of-service); or to circumvent security or access controls.`,
      ],
    },
    {
      h: '5. Accounts, tenants & credentials',
      p: [
        `You are responsible for the security of your account, your users' access, and the third-party credentials you store. Credentials are encrypted at rest (see the Privacy Policy), but you remain responsible for provider-side permissions, secret rotation, and revocation.`,
      ],
    },
    {
      h: '6. Subscription & fees',
      p: [
        `Software subscription fees, if any, are described at sign-up or in your order. Fees are exclusive of third-party provider charges and applicable taxes. Non-payment may result in suspension of the software service.`,
      ],
    },
    {
      h: '7. Warranties & liability',
      p: [
        `The software is provided "AS IS" and "AS AVAILABLE" without warranties of any kind. To the maximum extent permitted by law, ${COMPANY}'s aggregate liability arising out of or relating to the service is limited to the software fees you paid in the twelve (12) months preceding the claim, and we are not liable for indirect, incidental, or consequential damages, or for third-party provider charges, outages, or penalties.`,
      ],
    },
    {
      h: '8. Termination',
      p: [
        `You may stop using the service at any time. We may suspend or terminate access for breach of these Terms or applicable law. On termination you may export your data for a limited period, after which it may be deleted per our retention practices.`,
      ],
    },
    {
      h: '9. Governing law & changes',
      p: [
        `These Terms are governed by the laws of [Governing-Law Jurisdiction], without regard to conflict-of-laws rules, and the courts of [Jurisdiction/City] have exclusive jurisdiction. We may update these Terms; material changes will be notified in-app or by email, and continued use constitutes acceptance.`,
        `Questions: ${CONTACT}.`,
      ],
    },
  ],
};

const PRIVACY: LegalDoc = {
  key: 'privacy',
  label: 'Privacy Policy',
  title: 'Privacy Policy',
  updated: '2026-07-28',
  intro: `This Privacy Policy explains how ${COMPANY} handles information in ${PLATFORM}. For the contact and customer records you upload, you are the data controller/fiduciary and we act as your processor.`,
  sections: [
    {
      h: '1. Information we handle',
      p: [
        `• Account data: your name, email, organization, role, and authentication data.`,
        `• CRM data you upload: leads, contacts, notes, call/message logs and related records.`,
        `• Provider credentials: the API keys, tokens, and secrets you enter for your third-party providers.`,
        `• Usage & logs: technical logs, IP address, and audit records of configuration changes and API/webhook attempts.`,
      ],
    },
    {
      h: '2. How we handle your API keys',
      p: [
        `Provider credentials (API keys, auth tokens, app secrets, webhook secrets) are encrypted at rest using AES-256 and are never returned to the browser in plaintext after saving. They are decrypted only server-side, only to call the provider you configured, on your instruction.`,
        `We never sell credentials or use them for any purpose other than operating the integrations you enable. You are responsible for managing provider permissions, rotating secrets, and revoking access on the provider side.`,
      ],
    },
    {
      h: '3. How information is used and shared',
      p: [
        `We use information to operate and secure the service, provide support, and meet legal obligations. When you trigger a communication, the relevant data (e.g. recipient number, message content) is sent to the third-party provider you selected, under that provider's own privacy terms.`,
        `We use sub-processors for hosting and infrastructure. We do not sell personal data. We may disclose information if required by law.`,
      ],
    },
    {
      h: '4. Your rights',
      p: [
        `Depending on your jurisdiction you may have rights to access, correct, delete, or export personal data, and to withdraw consent — for example under the DPDP Act, 2023 (India) or the CCPA/CPRA (US). For CRM records you uploaded, exercise or forward end-user requests to us and we will assist as your processor.`,
      ],
    },
    {
      h: '5. Retention, security & international transfer',
      p: [
        `We retain data for as long as your account is active or as needed for legal/operational purposes, then delete or anonymize it. We apply administrative and technical safeguards (encryption, access controls, audit logging). Data may be processed in the region(s) where our infrastructure and sub-processors operate.`,
      ],
    },
    {
      h: '6. Changes & contact',
      p: [
        `We may update this Policy; material changes will be notified in-app or by email. Contact us at ${CONTACT} for privacy requests or questions.`,
      ],
    },
  ],
};

const FAIRUSE: LegalDoc = {
  key: 'fair-use',
  label: 'Fair Use & Disclaimer',
  title: 'Fair Use Policy & Third-Party Disclaimer',
  updated: '2026-07-28',
  intro: `This Fair Use Policy summarizes how ${PLATFORM} may be used. It supplements, and is subject to, the Terms of Service.`,
  sections: [
    {
      h: '1. Software layer, not a telecom service',
      p: [
        `${PLATFORM} is a management UI layer. It does not send messages or place calls on its own account. Every communication runs through your own connected third-party provider (BYOK), using your credentials, and is subject to that provider's capabilities, pricing, and policies.`,
      ],
    },
    {
      h: '2. Third-party costs',
      p: [
        `All SMS, voice, WhatsApp, and voice-note costs are billed directly to you by your chosen provider (Meta, Twilio, Exotel, Plivo, MSG91, Fast2SMS, etc.). ${COMPANY} does not resell, mark up, or intermediate those charges and is not liable for them.`,
      ],
    },
    {
      h: '3. Anti-spam & consent (your responsibility)',
      p: [
        `You must obtain explicit opt-in/consent and comply with all applicable regulations — including TRAI DLT (India), TCPA and A2P 10DLC (US), and the Meta WhatsApp Business Policies — before contacting anyone. ${COMPANY} bears zero liability for provider account bans, message blocking, fines, or legal penalties arising from spam or unsolicited messaging sent through your accounts.`,
      ],
    },
    {
      h: '4. Fair use of the platform',
      p: [
        `To keep the service reliable for all tenants, you will not abuse platform resources: no denial-of-service or excessive automated load, no scraping, and no attempts to bypass rate limits or security controls. We may apply rate limits and suspend abusive usage.`,
      ],
    },
    {
      h: '5. Key & account security',
      p: [
        `We encrypt stored credentials, but you are responsible for the security of your provider accounts, the scope of the permissions you grant, secret rotation, and prompt revocation of compromised keys.`,
      ],
    },
  ],
};

export const LEGAL_DOCS: Record<string, LegalDoc> = {
  [TERMS.key]: TERMS,
  [PRIVACY.key]: PRIVACY,
  [FAIRUSE.key]: FAIRUSE,
};

export const LEGAL_ORDER = [TERMS.key, PRIVACY.key, FAIRUSE.key];
