import React, { useState, useEffect } from 'react';
import {
  Stethoscope, Phone, Mail, Clock, Activity, RefreshCw
} from 'lucide-react';
import { api } from '../../services/api';

export const DoctorsPage: React.FC = () => {
  const [doctors, setDoctors] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchDoctors();
  }, []);

  const fetchDoctors = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/users/?limit=50');
      const list = res.data?.items || res.data || [];
      const docs = list.filter((u: any) => u.email?.includes('dr.') || (u.first_name || '').toLowerCase().includes('dr') || u.role === 'OrgAdmin' || u.role === 'Manager');
      setDoctors(docs.length > 0 ? docs : list.slice(0, 3));
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const doctorSpecializations: Record<string, { spec: string, exp: string, hours: string, cases: number }> = {
    'dr.arvind@smilecaredental.com': { spec: 'Chief Orthodontist & Clear Aligner Specialist', exp: '14+ yrs', hours: 'Mon - Sat: 09:00 AM - 02:00 PM', cases: 142 },
    'dr.priya@smilecaredental.com': { spec: 'Senior Endodontist & Microscopic RCT Specialist', exp: '11+ yrs', hours: 'Mon - Sat: 10:00 AM - 06:00 PM', cases: 218 },
    'dr.vikram@smilecaredental.com': { spec: 'Consultant Implantologist & Maxillofacial Surgeon', exp: '16+ yrs', hours: 'Tue, Thu, Sat: 02:00 PM - 08:00 PM', cases: 95 },
    'johnsondev02@gmail.com': { spec: 'Clinical Director & Aesthetic Dentist', exp: '12+ yrs', hours: 'Mon - Fri: 09:00 AM - 05:00 PM', cases: 180 }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
            <Stethoscope className="w-6 h-6 text-brand-400" />
            Dental Surgeons & Specialists Directory
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Clinic doctors, clinical specializations, OPD chair schedules & patient consultation loads.
          </p>
        </div>
      </div>

      {/* Doctors Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {isLoading ? (
          <div className="col-span-full glass-panel p-12 text-center rounded-2xl border border-slate-800 text-slate-400 text-xs">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-brand-400 mb-2" />
            Loading doctors directory...
          </div>
        ) : (
          doctors.map((doc) => {
            const meta = doctorSpecializations[doc.email] || {
              spec: 'Consultant Dental Surgeon',
              exp: '8+ yrs',
              hours: 'Mon - Sat: 09:00 AM - 05:00 PM',
              cases: 120
            };

            return (
              <div
                key={doc.id}
                className="glass-panel p-6 rounded-2xl border border-slate-800/80 hover:border-slate-700 transition shadow-xl space-y-4 flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-start gap-3.5">
                    <div className="w-12 h-12 rounded-2xl bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-brand-400 font-bold text-lg flex-shrink-0">
                      {doc.first_name?.[0]}{doc.last_name?.[0]}
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-slate-100">{doc.first_name} {doc.last_name}</h3>
                      <span className="text-xs font-semibold text-brand-400 block mt-0.5">{meta.spec}</span>
                      <span className="text-[11px] text-slate-400 mt-0.5 block">{doc.role} • Experience: {meta.exp}</span>
                    </div>
                  </div>

                  <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/60 space-y-2 text-xs">
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="text-slate-400 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-slate-500" /> OPD Hours</span>
                      <span className="font-semibold text-[11px]">{meta.hours}</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="text-slate-400 flex items-center gap-1.5"><Activity className="w-3.5 h-3.5 text-slate-500" /> Clinical Cases</span>
                      <span className="font-bold text-emerald-400">{meta.cases}+ Patients</span>
                    </div>
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-300">
                    <div className="flex items-center gap-2">
                      <Phone className="w-3.5 h-3.5 text-slate-500" />
                      <span>{doc.phone || '+91 9820112233'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Mail className="w-3.5 h-3.5 text-slate-500" />
                      <span className="truncate">{doc.email}</span>
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-800/70 flex items-center justify-between">
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                    Active & Available
                  </span>
                  <a
                    href={`tel:${doc.phone}`}
                    className="text-xs text-brand-400 hover:text-brand-300 font-semibold flex items-center gap-1"
                  >
                    Contact Doctor
                  </a>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
