import React, { useState } from 'react';
import {
  Settings, Building, Activity, Save, CheckCircle2
} from 'lucide-react';
import { formatMoney } from '../../utils/currency';

export const DentalSettingsPage: React.FC = () => {
  const [clinicName, setClinicName] = useState('SmileCare Dental Clinic');
  const [phone, setPhone] = useState('+91 98201 12233');
  const [email, setEmail] = useState('info@smilecaredental.com');
  const [address, setAddress] = useState('Suite 402, Dental Care Plaza, Linking Road, Bandra West, Mumbai 400050');
  const [opdHours, setOpdHours] = useState('Mon - Sat: 09:00 AM - 08:00 PM, Sun: 10:00 AM - 02:00 PM');
  const [isSaved, setIsSaved] = useState(false);

  const procedures = [
    { name: 'Root Canal Therapy (RCT)', category: 'Endodontics', cost: 12000, duration: '45 mins' },
    { name: 'Titanium Dental Implant', category: 'Implantology', cost: 45000, duration: '60 mins' },
    { name: 'Invisalign Clear Aligners', category: 'Orthodontics', cost: 95000, duration: '30 mins' },
    { name: 'Ceramic Braces Adjustment', category: 'Orthodontics', cost: 60000, duration: '30 mins' },
    { name: 'Zirconia Crown Fitting', category: 'Prosthodontics', cost: 15000, duration: '45 mins' },
    { name: 'Laser Teeth Whitening', category: 'Cosmetics', cost: 9500, duration: '45 mins' },
    { name: 'Deep Ultrasonic Cleaning', category: 'Preventive', cost: 2500, duration: '30 mins' },
    { name: 'Dental Consultation & X-Ray', category: 'Diagnostics', cost: 800, duration: '20 mins' }
  ];

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
            <Settings className="w-6 h-6 text-brand-400" />
            Dental Practice & Clinic Configuration
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Clinic profile, OPD working hours, treatment catalog with standard pricing & practice defaults.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Clinic Profile & OPD Hours */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-4">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Building className="w-4 h-4 text-brand-400" />
            Clinic Details & OPD Hours
          </h3>

          <form onSubmit={handleSave} className="space-y-3.5 text-xs">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Clinic Name</label>
              <input
                type="text"
                value={clinicName}
                onChange={(e) => setClinicName(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500 font-semibold"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Contact Phone</label>
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Clinic Address</label>
              <textarea
                rows={2}
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">OPD Hours</label>
              <input
                type="text"
                value={opdHours}
                onChange={(e) => setOpdHours(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500 font-mono text-[11px]"
              />
            </div>

            <button
              type="submit"
              className="w-full py-2.5 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white rounded-xl font-bold transition flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20 cursor-pointer"
            >
              {isSaved ? <CheckCircle2 className="w-4 h-4 text-emerald-300" /> : <Save className="w-4 h-4" />}
              {isSaved ? 'Settings Saved!' : 'Save Clinic Details'}
            </button>
          </form>
        </div>

        {/* Treatment Catalog & Pricing */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Standard Dental Procedures Catalog
              </h3>
              <p className="text-xs text-slate-400">Default chair durations & pricing in INR</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                  <th className="px-4 py-3">Procedure Name</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Standard Duration</th>
                  <th className="px-4 py-3 text-right">Standard Fee (INR)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {procedures.map((p, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30 transition">
                    <td className="px-4 py-3 font-bold text-slate-200">{p.name}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-brand-500/15 text-brand-300 border border-brand-500/30">
                        {p.category}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400">{p.duration}</td>
                    <td className="px-4 py-3 text-right font-black text-slate-100">{formatMoney(p.cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
