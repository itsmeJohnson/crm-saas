import React, { useState, useEffect } from 'react';
import { portalApi, OrgProfileDetails } from '../../services/portalApi';
import {
  Building2, Mail, Phone, MapPin, Landmark, FileText,
  Loader2, CheckCircle2, AlertTriangle
} from 'lucide-react';

export const PortalBilling: React.FC = () => {
  const [_profile, setProfile] = useState<OrgProfileDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form states
  const [billingName, setBillingName] = useState('');
  const [gstNumber, setGstNumber] = useState('');
  const [pan, setPan] = useState('');
  const [billingAddress, setBillingAddress] = useState('');
  const [billingCity, setBillingCity] = useState('');
  const [billingState, setBillingState] = useState('');
  const [billingCountry, setBillingCountry] = useState('');
  const [billingPinCode, setBillingPinCode] = useState('');
  const [billingEmail, setBillingEmail] = useState('');
  const [billingPhone, setBillingPhone] = useState('');

  useEffect(() => {
    fetchBillingDetails();
  }, []);

  const fetchBillingDetails = async () => {
    try {
      setLoading(true);
      // Fetch details by submitting empty payload
      const data = await portalApi.updateBilling({});
      setProfile(data);

      setBillingName(data.billing_name || '');
      setGstNumber(data.gst_number || '');
      setPan(data.pan || '');
      setBillingAddress(data.billing_address || '');
      setBillingCity(data.billing_city || '');
      setBillingState(data.billing_state || '');
      setBillingCountry(data.billing_country || '');
      setBillingPinCode(data.billing_pin_code || '');
      setBillingEmail(data.billing_email || '');
      setBillingPhone(data.billing_phone || '');
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load billing details.");
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

      const updated = await portalApi.updateBilling({
        billing_name: billingName,
        gst_number: gstNumber,
        pan,
        billing_address: billingAddress,
        billing_city: billingCity,
        billing_state: billingState,
        billing_country: billingCountry,
        billing_pin_code: billingPinCode,
        billing_email: billingEmail,
        billing_phone: billingPhone
      });

      setProfile(updated);
      setSuccess("Organization billing configuration successfully updated.");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to save billing settings.");
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
          Billing Config & Business Details
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Maintain GST registration numbers, PAN fields, corporate billing emails, and tax invoice mailing addresses.
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

      {/* Form */}
      <form onSubmit={handleSubmit} className="glass-panel border border-slate-900 rounded-2xl p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Billing Name */}
          <div className="md:col-span-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Corporate Billing Name</label>
            <div className="relative">
              <Building2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="Google Inc."
                required
                value={billingName}
                onChange={(e) => setBillingName(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {/* GST number */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">GSTIN / VAT Number</label>
            <div className="relative">
              <Landmark className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="27AAAAA0000A1Z5"
                value={gstNumber}
                onChange={(e) => setGstNumber(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {/* PAN */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Corporate PAN</label>
            <div className="relative">
              <FileText className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="ABCDE1234F"
                value={pan}
                onChange={(e) => setPan(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {/* Billing Email */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Billing Invoice Email</label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="email"
                placeholder="billing@yourcompany.com"
                required
                value={billingEmail}
                onChange={(e) => setBillingEmail(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {/* Billing Phone */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Billing Invoice Phone</label>
            <div className="relative">
              <Phone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="tel"
                placeholder="+91 99999 99999"
                value={billingPhone}
                onChange={(e) => setBillingPhone(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>
          </div>

          {/* Billing Address */}
          <div className="md:col-span-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Billing Street Address</label>
            <div className="relative">
              <MapPin className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
              <textarea
                placeholder="Suite 101, Business Park Road"
                required
                rows={2}
                value={billingAddress}
                onChange={(e) => setBillingAddress(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none resize-none"
              />
            </div>
          </div>

          {/* City */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">City</label>
            <input
              type="text"
              placeholder="Mumbai"
              required
              value={billingCity}
              onChange={(e) => setBillingCity(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
            />
          </div>

          {/* State */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">State / Region</label>
            <input
              type="text"
              placeholder="Maharashtra"
              required
              value={billingState}
              onChange={(e) => setBillingState(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
            />
          </div>

          {/* Country */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Country</label>
            <input
              type="text"
              placeholder="India"
              required
              value={billingCountry}
              onChange={(e) => setBillingCountry(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
            />
          </div>

          {/* Pin code */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">PIN / ZIP Code</label>
            <input
              type="text"
              placeholder="400001"
              required
              value={billingPinCode}
              onChange={(e) => setBillingPinCode(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
            />
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
                <Building2 className="w-3.5 h-3.5" />
                Save Billing Configurations
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
