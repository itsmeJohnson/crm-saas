import React, { useState, useEffect } from 'react';
import { portalApi } from '../../services/portalApi';
import { useThemeStore } from '../../store/themeStore';
import {
  Settings, Bell, Mail, Shield, CheckCircle2,
  AlertTriangle, Loader2, Sun, Moon, RefreshCw
} from 'lucide-react';

export const PortalSettings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const setTheme = useThemeStore((state) => state.setTheme);

  // Form Preferences States
  const [invoiceEmails, setInvoiceEmails] = useState(true);
  const [renewalEmails, setRenewalEmails] = useState(true);
  const [supportEmails, setSupportEmails] = useState(true);
  const [autoRenewal, setAutoRenewal] = useState(true);
  const [themeState, setThemeState] = useState<'light' | 'dark'>('dark');

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      // Fetch details by submitting empty profile payload
      const data = await portalApi.updateProfile({});
      setInvoiceEmails(data.notification_invoice_emails);
      setRenewalEmails(data.notification_renewal_emails);
      setSupportEmails(data.notification_support_emails);
      setAutoRenewal(data.auto_renewal ?? true);
      setThemeState((data.theme as 'light' | 'dark') ?? 'dark');
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load notification settings.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      const res = await portalApi.updateSettings({
        notification_invoice_emails: invoiceEmails,
        notification_renewal_emails: renewalEmails,
        notification_support_emails: supportEmails,
        auto_renewal: autoRenewal,
        theme: themeState
      });

      // Apply selected theme in local store instantly
      setTheme(themeState);

      setSuccess(res.message || "Preferences updated successfully.");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to update notification settings.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8 text-left max-w-2xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2 font-sans">
          Preferences & Settings
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Configure organization email notification toggles, billing alerts, and support status updates.
        </p>
      </div>

      {success && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {success}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="glass-panel border border-slate-900 rounded-2xl p-6 space-y-6">
        <div className="space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-2">
            <Bell className="w-4 h-4 text-indigo-400" />
            Email Notification Preferences
          </h3>

          {/* Invoice checkbox */}
          <label className="flex items-start gap-3 p-3.5 hover:bg-slate-900/20 border border-slate-900 hover:border-slate-850 rounded-xl transition-all cursor-pointer">
            <input
              type="checkbox"
              checked={invoiceEmails}
              onChange={(e) => setInvoiceEmails(e.target.checked)}
              className="mt-0.5 w-4 h-4 bg-slate-900 border-slate-800 rounded text-brand-500 focus:ring-0 focus:ring-offset-0 accent-brand-500"
            />
            <div>
              <span className="text-xs font-semibold text-slate-200 block">Billing Invoice Emails</span>
              <span className="text-[10px] text-slate-500">Receive alerts when new unpaid invoices are generated or processed.</span>
            </div>
          </label>

          {/* Renewal checkbox */}
          <label className="flex items-start gap-3 p-3.5 hover:bg-slate-900/20 border border-slate-900 hover:border-slate-850 rounded-xl transition-all cursor-pointer">
            <input
              type="checkbox"
              checked={renewalEmails}
              onChange={(e) => setRenewalEmails(e.target.checked)}
              className="mt-0.5 w-4 h-4 bg-slate-900 border-slate-800 rounded text-brand-500 focus:ring-0 focus:ring-offset-0 accent-brand-500"
            />
            <div>
              <span className="text-xs font-semibold text-slate-200 block">Renewal Reminders</span>
              <span className="text-[10px] text-slate-500">Receive reminders 7 days and 1 day prior to active subscription expiration.</span>
            </div>
          </label>

          {/* Support checkbox */}
          <label className="flex items-start gap-3 p-3.5 hover:bg-slate-900/20 border border-slate-900 hover:border-slate-850 rounded-xl transition-all cursor-pointer">
            <input
              type="checkbox"
              checked={supportEmails}
              onChange={(e) => setSupportEmails(e.target.checked)}
              className="mt-0.5 w-4 h-4 bg-slate-900 border-slate-800 rounded text-brand-500 focus:ring-0 focus:ring-offset-0 accent-brand-500"
            />
            <div>
              <span className="text-xs font-semibold text-slate-200 block">Support Thread Status Revisions</span>
              <span className="text-[10px] text-slate-500">Receive notifications on raised ticket status updates and comment thread replies.</span>
            </div>
          </label>
        </div>
 
        {/* Commercial & Visual Preferences */}
        <div className="space-y-4 pt-4 border-t border-slate-900/50">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-2">
            <RefreshCw className="w-4 h-4 text-indigo-400" />
            Billing & Portal Preferences
          </h3>

          {/* Auto Renewal checkbox */}
          <label className="flex items-start gap-3 p-3.5 hover:bg-slate-900/20 border border-slate-900 hover:border-slate-850 rounded-xl transition-all cursor-pointer">
            <input
              type="checkbox"
              checked={autoRenewal}
              onChange={(e) => setAutoRenewal(e.target.checked)}
              className="mt-0.5 w-4 h-4 bg-slate-900 border-slate-800 rounded text-brand-500 focus:ring-0 focus:ring-offset-0 accent-brand-500"
            />
            <div>
              <span className="text-xs font-semibold text-slate-200 block">Automatic Subscription Renewal</span>
              <span className="text-[10px] text-slate-500">Automatically renew subscription and process charges upon expiry.</span>
            </div>
          </label>

          {/* Theme Selector Option */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300 block">
              Active Visual Theme Mode
            </label>
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => setThemeState('dark')}
                className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                  themeState === 'dark'
                    ? 'bg-slate-900/60 border-brand-500/50 text-slate-100 shadow-md shadow-brand-500/5'
                    : 'bg-slate-950/40 border-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                <Moon className="w-4 h-4 text-indigo-400" />
                Dark Theme
              </button>
              <button
                type="button"
                onClick={() => setThemeState('light')}
                className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                  themeState === 'light'
                    ? 'bg-slate-900/60 border-brand-500/50 text-slate-100 shadow-md shadow-brand-500/5'
                    : 'bg-slate-950/40 border-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                <Sun className="w-4 h-4 text-amber-400" />
                Light Theme
              </button>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t border-slate-900/50">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-1.5 px-6 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
          >
            {saving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <>
                <Settings className="w-3.5 h-3.5" />
                Save Preferences
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
