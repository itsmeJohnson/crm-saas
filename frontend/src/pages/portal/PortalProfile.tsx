import React, { useState, useEffect } from 'react';
import { portalApi, OrgProfileDetails } from '../../services/portalApi';
import {
  User, Link2, Mail, Phone, Globe,
  Loader2, CheckCircle2, AlertTriangle, Building
} from 'lucide-react';

export const PortalProfile: React.FC = () => {
  const [profile, setProfile] = useState<OrgProfileDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form states
  const [website, setWebsite] = useState('');
  const [supportEmail, setSupportEmail] = useState('');
  const [supportPhone, setSupportPhone] = useState('');
  const [timezone, setTimezone] = useState('Asia/Kolkata');
  const [language, setLanguage] = useState('English');
  const [currency, setCurrency] = useState('INR');
  const [logoUrl, setLogoUrl] = useState('');

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      setLoading(true);
      // Fetch profile by submitting empty payload
      const data = await portalApi.updateProfile({});
      setProfile(data);
      
      // Populate fields
      setWebsite(data.website || '');
      setSupportEmail(data.support_email || '');
      setSupportPhone(data.support_phone || '');
      setTimezone(data.timezone || 'Asia/Kolkata');
      setLanguage(data.language || 'English');
      setCurrency(data.currency || 'INR');
      setLogoUrl(data.logo_url || '');
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load profile details.");
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

      const updated = await portalApi.updateProfile({
        website,
        support_email: supportEmail,
        support_phone: supportPhone,
        timezone,
        language,
        currency,
        logo_url: logoUrl
      });

      setProfile(updated);
      setSuccess("Organization profile successfully updated.");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to update profile settings.");
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
    <div className="space-y-8 text-left max-w-3xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
          Company Profile Configuration
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Customize organization support contacts, manage logo configurations, and set local timezone and currency parameters.
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

      {/* Main Profile Form */}
      <form onSubmit={handleSubmit} className="glass-panel border border-slate-900 rounded-2xl p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Org Name (Read-only) */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Organization Name</label>
            <div className="relative">
              <Building className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
              <input
                type="text"
                disabled
                value={profile?.name || ''}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-900 rounded-xl text-xs text-slate-500 focus:outline-none cursor-not-allowed"
              />
            </div>
          </div>

          {/* Org Slug (Read-only) */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Organization Slug</label>
            <div className="relative">
              <Globe className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
              <input
                type="text"
                disabled
                value={profile?.slug || ''}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-900 rounded-xl text-xs text-slate-500 focus:outline-none cursor-not-allowed"
              />
            </div>
          </div>

          {/* Logo URL */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Logo Image URL</label>
            <div className="relative">
              <Link2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="url"
                placeholder="https://example.com/logo.png"
                value={logoUrl}
                onChange={(e) => setLogoUrl(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {/* Website */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Official Website</label>
            <div className="relative">
              <Globe className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="url"
                placeholder="https://yourcompany.com"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {/* Support Email */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Support Contact Email</label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="email"
                placeholder="support@yourcompany.com"
                value={supportEmail}
                onChange={(e) => setSupportEmail(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {/* Support Phone */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Support Contact Phone</label>
            <div className="relative">
              <Phone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="tel"
                inputMode="tel"
                maxLength={20}
                placeholder="+91 99999 99999"
                value={supportPhone}
                onChange={(e) => setSupportPhone(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {/* Timezone */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Default Timezone</label>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none"
            >
              <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
              <option value="UTC">UTC / GMT</option>
              <option value="America/New_York">America/New_York (EST)</option>
              <option value="Europe/London">Europe/London (BST)</option>
              <option value="Asia/Singapore">Asia/Singapore (SGT)</option>
            </select>
          </div>

          {/* Language */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Default Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none"
            >
              <option value="English">English</option>
              <option value="Hindi">Hindi</option>
              <option value="Spanish">Spanish</option>
              <option value="German">German</option>
              <option value="French">French</option>
            </select>
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
                <User className="w-3.5 h-3.5" />
                Save Profile Configuration
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
