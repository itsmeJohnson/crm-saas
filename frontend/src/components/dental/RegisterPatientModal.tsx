import React, { useEffect, useState } from 'react';
import { UserPlus, X } from 'lucide-react';
import { api } from '../../services/api';
import { contactApi } from '../../services/contactApi';
import { useAuthStore } from '../../store/authStore';

interface RegisterPatientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (patient?: any) => void;
}

const COUNTRY_CODES = ['+91', '+1', '+44', '+971', '+61', '+65', '+60'];
const GENDERS = ['Male', 'Female', 'Other'];
const REFERRALS = ['Walk-in', 'Google', 'Facebook', 'Instagram', 'Friend / Family', 'Existing Patient', 'Doctor Referral', 'Other'];
const REASONS = ['Consultation', 'Tooth Pain', 'Cleaning / Scaling', 'Follow-up', 'Orthodontic', 'Root Canal', 'Emergency', 'Other'];

export const RegisterPatientModal: React.FC<RegisterPatientModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const organization = useAuthStore((s) => s.organization);

  const [isNew, setIsNew] = useState(true);
  const [doctors, setDoctors] = useState<any[]>([]);
  const [patients, setPatients] = useState<any[]>([]);

  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('Male');
  const [countryCode, setCountryCode] = useState('+91');
  const [mobile, setMobile] = useState('');
  const [altCountryCode, setAltCountryCode] = useState('+91');
  const [altMobile, setAltMobile] = useState('');
  const [clinic, setClinic] = useState('');
  const [consultantId, setConsultantId] = useState('');
  const [referral, setReferral] = useState('');
  const [reason, setReason] = useState('');
  const [existingId, setExistingId] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setClinic(organization?.name || '');
    (async () => {
      try {
        const [uRes, cRes] = await Promise.all([
          api.get('/users/?limit=50'),
          api.get('/contacts/?limit=100'),
        ]);
        const users = (uRes.data || []);
        const docs = users.filter((u: any) => /doctor|dentist|surgeon/i.test(u.role || '') || /doctor|dentist|surgeon/i.test((u.custom_role_name || '')));
        setDoctors(docs.length > 0 ? docs : users);
        setPatients(cRes.data || []);
      } catch {
        /* non-fatal */
      }
    })();
  }, [isOpen, organization]);

  if (!isOpen) return null;

  const reset = () => {
    setIsNew(true); setName(''); setAge(''); setGender('Male'); setCountryCode('+91'); setMobile('');
    setAltCountryCode('+91'); setAltMobile(''); setConsultantId(''); setReferral(''); setReason(''); setExistingId('');
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!isNew) {
      const existing = patients.find((p) => p.id === existingId);
      if (!existing) { setError('Please select an existing patient.'); return; }
      onSuccess?.(existing);
      reset();
      onClose();
      return;
    }

    if (!name.trim()) { setError('Patient name is required.'); return; }
    if (!mobile.trim()) { setError('Mobile number is required.'); return; }
    if (!consultantId) { setError('Please select a consultant.'); return; }

    const parts = name.trim().split(/\s+/);
    const first_name = parts[0];
    const last_name = parts.slice(1).join(' ') || '-';
    const consultant = doctors.find((d) => d.id === consultantId);
    const consultantName = consultant ? `${consultant.first_name || ''} ${consultant.last_name || ''}`.trim() : '';

    setSubmitting(true);
    try {
      const patient = await contactApi.createContact({
        first_name,
        last_name,
        phone: `${countryCode} ${mobile}`.trim(),
        assigned_user_id: consultantId || null,
        custom_fields: {
          age: age ? Number(age) : null,
          gender,
          country_code: countryCode,
          alternate_phone: altMobile ? `${altCountryCode} ${altMobile}`.trim() : null,
          clinic: clinic || null,
          consultant_id: consultantId || null,
          consultant_name: consultantName || null,
          primary_doctor: consultantName || null,
          referral: referral || null,
          reason: reason || null,
          patient_category: 'New Patient',
        },
      });
      onSuccess?.(patient);
      reset();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to register the patient.');
    } finally {
      setSubmitting(false);
    }
  };

  const labelCls = 'block text-[11px] font-semibold text-slate-300 mb-1.5';
  const inputCls = 'w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        <div className="p-5 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-500/25 flex items-center justify-center text-brand-400">
              <UserPlus className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-100">Register / Walk-In</h3>
              <p className="text-xs text-slate-400">Register a new patient or check in an existing one</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto">
          {/* New patient toggle */}
          <label className="flex items-center gap-2.5 cursor-pointer select-none w-max">
            <button
              type="button"
              onClick={() => setIsNew((v) => !v)}
              className={`relative w-10 h-5 rounded-full transition-colors ${isNew ? 'bg-brand-500' : 'bg-slate-700'}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${isNew ? 'translate-x-5' : ''}`} />
            </button>
            <span className="text-xs font-semibold text-brand-400">New Patient</span>
          </label>

          {!isNew ? (
            <div>
              <label className={labelCls}>Select Existing Patient <span className="text-rose-400">*</span></label>
              <select value={existingId} onChange={(e) => setExistingId(e.target.value)} className={inputCls}>
                <option value="">Search or select a patient…</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>{p.first_name} {p.last_name} — {p.phone || 'no phone'}</option>
                ))}
              </select>
            </div>
          ) : (
            <>
              {/* Name / Age / Gender */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                <div className="sm:col-span-2">
                  <label className={labelCls}>Name <span className="text-rose-400">*</span></label>
                  <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="Patient full name" />
                </div>
                <div>
                  <label className={labelCls}>Age <span className="text-rose-400">*</span></label>
                  <input type="number" min={0} value={age} onChange={(e) => setAge(e.target.value)} className={inputCls} placeholder="e.g. 32" />
                </div>
                <div>
                  <label className={labelCls}>Gender</label>
                  <select value={gender} onChange={(e) => setGender(e.target.value)} className={inputCls}>
                    {GENDERS.map((g) => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>
              </div>

              {/* Mobile */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Mobile <span className="text-rose-400">*</span></label>
                  <div className="flex gap-2">
                    <select value={countryCode} onChange={(e) => setCountryCode(e.target.value)} className={`${inputCls} w-24`}>
                      {COUNTRY_CODES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <input value={mobile} onChange={(e) => setMobile(e.target.value)} className={inputCls} placeholder="Mobile number" />
                  </div>
                </div>
                <div>
                  <label className={labelCls}>Alternate Mobile</label>
                  <div className="flex gap-2">
                    <select value={altCountryCode} onChange={(e) => setAltCountryCode(e.target.value)} className={`${inputCls} w-24`}>
                      {COUNTRY_CODES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <input value={altMobile} onChange={(e) => setAltMobile(e.target.value)} className={inputCls} placeholder="Optional" />
                  </div>
                </div>
              </div>

              {/* Clinic / Consultant */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Clinic</label>
                  <input value={clinic} onChange={(e) => setClinic(e.target.value)} className={inputCls} placeholder="Clinic / branch" />
                </div>
                <div>
                  <label className={labelCls}>Consultant <span className="text-rose-400">*</span></label>
                  <select value={consultantId} onChange={(e) => setConsultantId(e.target.value)} className={inputCls}>
                    <option value="">Search or select a doctor…</option>
                    {doctors.map((d) => (
                      <option key={d.id} value={d.id}>{d.first_name} {d.last_name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Referral / Reason */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Referral</label>
                  <select value={referral} onChange={(e) => setReferral(e.target.value)} className={inputCls}>
                    <option value="">Select referral…</option>
                    {REFERRALS.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                <div>
                  <label className={labelCls}>Reason</label>
                  <select value={reason} onChange={(e) => setReason(e.target.value)} className={inputCls}>
                    <option value="">Select reason…</option>
                    {REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
              </div>
            </>
          )}

          {error && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs font-medium">{error}</div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700/50">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="px-5 py-2 rounded-xl text-xs font-bold text-white bg-brand-500 hover:bg-brand-600 disabled:opacity-50 flex items-center gap-2">
              <UserPlus className="w-4 h-4" />
              {isNew ? (submitting ? 'Registering…' : 'Register Patient') : 'Check In'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
