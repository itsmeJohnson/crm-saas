import React, { useState, useEffect } from 'react';
import {
  Activity, Plus, Search, RefreshCw, Stethoscope
} from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { api } from '../../services/api';
import { TreatmentPlanModal } from '../../components/dental/TreatmentPlanModal';
import { PatientProfileModal } from '../../components/dental/PatientProfileModal';

export const TreatmentsPage: React.FC = () => {
  const [treatments, setTreatments] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [isLoading, setIsLoading] = useState(true);

  // Modals
  const [isPlanOpen, setIsPlanOpen] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState<any | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  useEffect(() => {
    fetchTreatments();
  }, []);

  const fetchTreatments = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/customers/orders');
      setTreatments(res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredTreatments = treatments.filter((t) => {
    const item = t.items?.[0] || {};
    const name = (item.description || t.order_number || '').toLowerCase();
    const doc = (item.doctor || '').toLowerCase();
    const notes = (t.notes || '').toLowerCase();
    const matchesSearch = name.includes(search.toLowerCase()) || doc.includes(search.toLowerCase()) || notes.includes(search.toLowerCase());

    const cat = item.category || 'All';
    const matchesCat = categoryFilter === 'All' || cat === categoryFilter;

    return matchesSearch && matchesCat;
  });

  const categories = ['All', 'Endodontics', 'Implantology', 'Orthodontics', 'Prosthodontics', 'Cosmetic', 'Preventive', 'Oral Surgery'];

  return (
    <div className="space-y-6 select-none">
      {/* Header Bento */}
      <div className="bento-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-400 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-purple-500/25 flex-shrink-0">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-100">
              Dental Treatment Plans &amp; Clinical Progress
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Multi-sitting procedural steps, doctor assignments, procedure estimates &amp; completion statuses.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsPlanOpen(true)}
            className="neo-btn-primary px-4 py-2.5 text-xs flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            New Treatment Plan
          </button>
        </div>
      </div>

      {/* Filters Bar Bento */}
      <div className="bento-card p-5 space-y-4">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by procedure name, attending doctor, clinical notes..."
            className="neo-input w-full pr-4 py-2.5 text-xs"
            style={{ paddingLeft: '2.4rem' }}
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pt-1">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategoryFilter(c)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition cursor-pointer ${
                categoryFilter === c
                  ? 'neo-btn-primary'
                  : 'neo-btn text-slate-400 hover:text-slate-200'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Treatments Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {isLoading ? (
          <div className="col-span-full neo-inset p-12 text-center text-slate-400">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-cyan-400 mb-2" />
            Loading active treatment plans...
          </div>
        ) : filteredTreatments.length === 0 ? (
          <div className="col-span-full neo-inset p-12 text-center text-slate-400 space-y-2">
            <Activity className="w-8 h-8 mx-auto text-slate-600" />
            <p className="text-xs font-bold text-slate-300">No matching treatment plans found.</p>
            <p className="text-[11px] text-slate-500">Click New Treatment Plan to start a patient procedure.</p>
          </div>
        ) : (
          filteredTreatments.map((plan) => {
            const item = plan.items?.[0] || {};
            const totalSteps = item.total_steps || 3;
            const currentStep = item.current_step || 1;
            const progress = Math.min(100, Math.round((currentStep / totalSteps) * 100));
            const category = item.category || 'Endodontics';
            const doctor = item.doctor || 'Dr. Arvind Mehta';
            const stepDesc = item.step_description || `Step ${currentStep} of ${totalSteps}`;

            return (
              <div
                key={plan.id}
                className="bento-card p-5 space-y-4 hover:scale-[1.01] transition-transform duration-200"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="neo-pill text-[10px] text-purple-400 bg-purple-500/10 border-purple-500/20 font-bold mb-1.5 inline-block">
                      {category}
                    </span>
                    <h3 className="text-sm font-black text-slate-100 line-clamp-1">
                      {item.description || plan.order_number || 'Dental Procedure'}
                    </h3>
                  </div>
                  <span className="text-sm font-black text-slate-100">
                    {formatMoney(plan.total_amount || 0)}
                  </span>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400 font-medium">{stepDesc}</span>
                    <span className="font-extrabold text-cyan-400">{progress}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full neo-inset p-0.5 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-purple-500 to-cyan-400 transition-all duration-500"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-800/40 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 text-slate-400">
                    <Stethoscope className="w-3.5 h-3.5 text-cyan-400" />
                    <span className="truncate max-w-[140px]">{doctor}</span>
                  </div>
                  <span className={`neo-pill text-[10px] ${
                    progress === 100
                      ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                      : 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20'
                  }`}>
                    {progress === 100 ? 'Completed' : 'In Progress'}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Treatment Plan Modal */}
      <TreatmentPlanModal
        isOpen={isPlanOpen}
        onClose={() => setIsPlanOpen(false)}
        onSuccess={() => {
          setIsPlanOpen(false);
          fetchTreatments();
        }}
      />

      {/* Patient Profile Modal */}
      {selectedPatient && (
        <PatientProfileModal
          patient={selectedPatient}
          isOpen={isProfileOpen}
          onClose={() => {
            setIsProfileOpen(false);
            setSelectedPatient(null);
          }}
        />
      )}
    </div>
  );
};

export default TreatmentsPage;
