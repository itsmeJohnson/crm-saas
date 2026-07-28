import React from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { LEGAL_DOCS, LEGAL_ORDER } from './legalContent';

/** Public legal document viewer — /legal/:doc (terms | privacy | fair-use).
 *  Theme-aware (uses the app's CSS variables) and readable full-page. */
export const LegalPage: React.FC = () => {
  const { doc } = useParams<{ doc: string }>();
  const active = doc && LEGAL_DOCS[doc] ? LEGAL_DOCS[doc] : null;
  if (!active) return <Navigate to={`/legal/${LEGAL_ORDER[0]}`} replace />;

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-app)', color: 'var(--text-primary)' }}>
      <div className="max-w-3xl mx-auto px-5 py-10">
        {/* Header */}
        <div className="flex items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-brand-500 to-indigo-500 rounded-xl flex items-center justify-center shadow-md">
              <span className="font-bold text-white">C</span>
            </div>
            <span className="font-bold tracking-tight">CRM Enterprise</span>
          </div>
          <Link to="/login" className="text-sm" style={{ color: 'var(--brand-500, #6366f1)' }}>← Back to app</Link>
        </div>

        {/* Doc switcher */}
        <div className="flex flex-wrap gap-2 mb-6">
          {LEGAL_ORDER.map((k) => {
            const d = LEGAL_DOCS[k];
            const isActive = k === active.key;
            return (
              <Link
                key={k}
                to={`/legal/${k}`}
                className="px-3 py-1.5 rounded-lg text-sm border transition-colors"
                style={{
                  backgroundColor: isActive ? 'var(--brand-500, #6366f1)' : 'var(--bg-card)',
                  color: isActive ? '#fff' : 'var(--text-secondary, #94a3b8)',
                  borderColor: 'var(--border-color)',
                }}
              >
                {d.label}
              </Link>
            );
          })}
        </div>

        {/* Template banner */}
        <div
          className="rounded-xl px-4 py-3 mb-8 text-sm"
          style={{ backgroundColor: 'rgba(234,179,8,0.10)', border: '1px solid rgba(234,179,8,0.35)', color: 'var(--text-primary)' }}
        >
          <strong>Template — review required.</strong> This document is a starting template covering India (TRAI/DLT, DPDP Act) and US (TCPA, A2P 10DLC, CCPA)
          requirements. Have qualified legal counsel review and adapt it (entity name, governing-law jurisdiction, contact details) before production use.
        </div>

        {/* Document */}
        <article>
          <h1 className="text-2xl font-bold mb-1">{active.title}</h1>
          <p className="text-xs mb-6" style={{ color: 'var(--text-muted)' }}>Last updated: {active.updated}</p>
          <p className="mb-8 leading-relaxed" style={{ color: 'var(--text-secondary, #cbd5e1)' }}>{active.intro}</p>

          {active.sections.map((s, i) => (
            <section key={i} className="mb-6">
              <h2 className="text-lg font-semibold mb-2">{s.h}</h2>
              {s.p.map((para, j) => (
                <p key={j} className="mb-2 leading-relaxed" style={{ color: 'var(--text-secondary, #cbd5e1)' }}>{para}</p>
              ))}
            </section>
          ))}
        </article>

        {/* Footer */}
        <div className="mt-10 pt-6 text-xs flex flex-wrap gap-x-4 gap-y-2" style={{ borderTop: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
          {LEGAL_ORDER.map((k) => (
            <Link key={k} to={`/legal/${k}`} style={{ color: 'var(--text-muted)' }}>{LEGAL_DOCS[k].label}</Link>
          ))}
          <span>© {new Date().getFullYear()} CRM Enterprise</span>
        </div>
      </div>
    </div>
  );
};
