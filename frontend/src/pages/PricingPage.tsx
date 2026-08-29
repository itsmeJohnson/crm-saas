import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Phone, Sparkles, ArrowRight } from 'lucide-react';

/**
 * Public marketing + pricing storefront. No auth. Tiers are rendered statically
 * (they mirror seed_plans.py) so the page works before the plan catalog is
 * seeded/deployed. CTAs carry the chosen industry into /register.
 */

const INDUSTRIES = [
  { value: 'telecalling', label: 'Telecalling' },
  { value: 'healthcare_dental', label: 'Dental' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'insurance', label: 'Insurance' },
  { value: 'loan_recovery', label: 'Collections' },
  { value: 'generic', label: 'Other' },
];

type Tier = {
  name: string;
  price: string;
  cadence: string;
  tagline: string;
  features: string[];
  popular?: boolean;
  custom?: boolean;
};

const TIERS: Tier[] = [
  {
    name: 'Launch', price: '₹9,999', cadence: '/ month',
    tagline: 'Your whole team, one system.',
    features: [
      'Up to 10 users',
      'Up to 2,500 leads',
      '1 pipeline · CRM + email automation',
      'WhatsApp + SMS + calling',
      'Basic analytics · 1 website',
    ],
  },
  {
    name: 'Growth', price: '₹19,999', cadence: '/ month',
    tagline: 'Automate & attribute.', popular: true,
    features: [
      'Everything in Launch · up to 30 users',
      'Up to 10,000 leads · multiple pipelines',
      'Advanced automation & workflows',
      'UTM attribution + lead scoring',
      'Campaigns + Voice broadcast · 2 websites',
      'Advanced analytics · priority support',
    ],
  },
  {
    name: 'Scale', price: '₹34,999', cadence: '/ month',
    tagline: 'AI, API & unlimited.',
    features: [
      'Everything in Growth · unlimited users',
      'Unlimited leads',
      'AI call summaries & follow-up',
      'API access · 5+ websites',
      'White-label optional',
    ],
  },
  {
    name: 'Implementation', price: 'One-time', cadence: 'website + setup', custom: true,
    tagline: 'We build & configure it for you.',
    features: [
      'Professional lead-gen website',
      'CRM setup + pipeline configuration',
      'Automation & website integration',
      'Onboarding + training',
      'From ₹3.5L (talk to sales)',
    ],
  },
];

export const PricingPage: React.FC = () => {
  const [industry, setIndustry] = useState('telecalling');
  const signup = (extra = '') => `/register?industry=${industry}${extra}`;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Nav */}
      <header className="flex items-center justify-between px-6 md:px-12 py-5 border-b border-slate-800/60">
        <div className="flex items-center gap-2 font-bold text-lg">
          <span className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-500 to-indigo-500 flex items-center justify-center"><Phone className="w-4 h-4" /></span>
          Johnson CRM
        </div>
        <div className="flex items-center gap-3 text-sm">
          <Link to="/login" className="text-slate-300 hover:text-white px-3 py-2">Sign in</Link>
          <Link to={signup()} className="bg-brand-500 hover:bg-brand-600 text-white font-semibold px-4 py-2 rounded-xl">Start free trial</Link>
        </div>
      </header>

      {/* Hero */}
      <section className="text-center max-w-3xl mx-auto px-6 pt-16 pb-10">
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-300 bg-brand-500/10 border border-brand-500/20 rounded-full px-3 py-1 mb-5">
          <Sparkles className="w-3.5 h-3.5" /> Agency Growth Platform
        </span>
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight leading-tight">
          Your website shouldn't just look good. <span className="bg-gradient-to-r from-brand-400 to-indigo-400 bg-clip-text text-transparent">It should sell.</span>
        </h1>
        <p className="text-slate-400 mt-5 text-lg">
          Website + CRM + Automation + Analytics — one revenue system. Capture every lead, know where it came from, and automate follow-up across your pipeline. Flat monthly — no per-seat tax.
        </p>
        <div className="mt-7 flex items-center justify-center gap-3">
          <Link to={signup()} className="inline-flex items-center gap-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold px-6 py-3 rounded-xl">
            Start 14-day free trial <ArrowRight className="w-4 h-4" />
          </Link>
          <a href="#pricing" className="text-slate-300 hover:text-white font-semibold px-6 py-3">See pricing</a>
        </div>
      </section>

      {/* Industry selector */}
      <div className="flex flex-wrap items-center justify-center gap-2 px-6 pb-2">
        <span className="text-xs text-slate-500 mr-1">I run a:</span>
        {INDUSTRIES.map((i) => (
          <button key={i.value} onClick={() => setIndustry(i.value)}
            className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors cursor-pointer ${
              industry === i.value ? 'bg-brand-500/20 border-brand-500/50 text-brand-200' : 'border-slate-700/60 text-slate-400 hover:text-slate-200'}`}>
            {i.label}
          </button>
        ))}
      </div>

      {/* Pricing */}
      <section id="pricing" className="max-w-6xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {TIERS.map((t) => (
            <div key={t.name}
              className={`relative rounded-2xl border p-6 flex flex-col ${
                t.popular ? 'border-brand-500/70 bg-slate-900 shadow-xl shadow-brand-500/10' : 'border-slate-800 bg-slate-900/50'}`}>
              {t.popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-[11px] font-bold bg-gradient-to-r from-brand-500 to-indigo-500 text-white px-3 py-1 rounded-full">
                  ⭐ Most Popular
                </span>
              )}
              <h3 className="text-lg font-bold">{t.name}</h3>
              <p className="text-xs text-slate-400 mt-0.5">{t.tagline}</p>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-3xl font-extrabold">{t.price}</span>
                <span className="text-xs text-slate-500">{t.cadence}</span>
              </div>
              <ul className="mt-5 space-y-2.5 flex-1">
                {t.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <Check className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" /> {f}
                  </li>
                ))}
              </ul>
              <Link
                to={t.custom ? '/register?industry=' + industry + '&plan=Enterprise' : signup(`&plan=${t.name}`)}
                className={`mt-6 text-center font-semibold py-2.5 rounded-xl transition-colors ${
                  t.popular ? 'bg-brand-500 hover:bg-brand-600 text-white'
                  : t.custom ? 'border border-slate-700 hover:border-brand-500/60 text-slate-200'
                  : 'bg-slate-800 hover:bg-slate-700 text-white'}`}>
                {t.custom ? 'Contact sales' : 'Start free trial'}
              </Link>
            </div>
          ))}
        </div>
        <p className="text-center text-xs text-slate-500 mt-6">
          Flat monthly, no per-seat pricing. Minimum 3-month contract. Quarterly −5%, annual −15%. GST extra. One-time website + implementation setup billed separately. Cancel anytime.
        </p>
      </section>

      <footer className="border-t border-slate-800/60 text-center text-xs text-slate-500 py-8 px-6">
        © {new Date().getFullYear()} Johnson Softwares. <Link to="/legal/terms" className="text-brand-400 hover:text-brand-300">Terms</Link> · <Link to="/legal/privacy" className="text-brand-400 hover:text-brand-300">Privacy</Link>
      </footer>
    </div>
  );
};
