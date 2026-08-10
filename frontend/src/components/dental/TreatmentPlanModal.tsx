import React, { useState, useEffect } from 'react';
import { X, Activity, CheckCircle2, Loader2 } from 'lucide-react';
import { api } from '../../services/api';

interface TreatmentPlanModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const TreatmentPlanModal: React.FC<TreatmentPlanModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [patients, setPatients] = useState<any[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [treatmentName, setTreatmentName] = useState('Root Canal Therapy (RCT)');
  const [category, setCategory] = useState('Endodontics');
  const [totalCost, setTotalCost] = useState<number>(12000);
  const [doctorName, setDoctorName] = useState('Dr. Priya Sharma');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadPatients();
    }
  }, [isOpen]);

  const loadPatients = async () => {
    try {
      const res = await api.get('/contacts/?limit=100');
      const list = res.data?.items || res.data || [];
      setPatients(list);
      if (list.length > 0) setSelectedPatientId(list[0].id);
    } catch (e) {
      console.error(e);
    }
  };

  if (!isOpen) return null;

  const handleTreatmentChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setTreatmentName(val);
    if (val.includes('Root Canal')) { setCategory('Endodontics'); setTotalCost(12000); setDoctorName('Dr. Priya Sharma'); }
    else if (val.includes('Implant')) { setCategory('Implantology'); setTotalCost(45000); setDoctorName('Dr. Vikram Rao'); }
    else if (val.includes('Invisalign')) { setCategory('Orthodontics'); setTotalCost(95000); setDoctorName('Dr. Arvind Mehta'); }
    else if (val.includes('Braces')) { setCategory('Orthodontics'); setTotalCost(60000); setDoctorName('Dr. Arvind Mehta'); }
    else if (val.includes('Crown')) { setCategory('Prosthodontics'); setTotalCost(15000); setDoctorName('Dr. Priya Sharma'); }
    else if (val.includes('Whitening')) { setCategory('Cosmetic'); setTotalCost(9500); setDoctorName('Dr. Priya Sharma'); }
    else if (val.includes('Cleaning')) { setCategory('Preventive'); setTotalCost(2500); setDoctorName('Dr. Johnson Dev'); }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      // Find company
      const compRes = await api.get('/companies/?limit=1');
      const comp = (compRes.data?.items || compRes.data || [])[0];
      const companyId = comp?.id || selectedPatientId;

      await api.post('/customers/orders', {
        company_id: companyId,
        contact_id: selectedPatientId,
        order_number: `TRT-${Date.now().toString().slice(-6)}`,
        status: 'Confirmed',
        currency: 'INR',
        order_date: new Date().toISOString(),
        items: [{
          description: treatmentName,
          category: category,
          doctor: doctorName,
          current_step: 'Step 1: Diagnostics & Procedure Initiation',
          progress_percent: 25,
          quantity: 1,
          unit_price: totalCost,
          amount: totalCost
        }],
        subtotal: totalCost,
        total_amount: totalCost,
        notes: notes || `Treatment planned for patient under ${doctorName}`
      });

      alert('Treatment plan registered successfully!');
      if (onSuccess) onSuccess();
      onClose();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create treatment plan');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        <div className="p-5 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-500/25 flex items-center justify-center text-brand-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100">Create Treatment Plan</h3>
              <p className="text-xs text-slate-400">Prescribe dental procedure & protocol</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Patient</label>
            <select
              value={selectedPatientId}
              onChange={(e) => setSelectedPatientId(e.target.value)}
              required
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
            >
              {patients.map(p => (
                <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Treatment Procedure</label>
            <select
              value={treatmentName}
              onChange={handleTreatmentChange}
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
            >
              <option value="Root Canal Therapy (RCT)">Root Canal Therapy (RCT)</option>
              <option value="Titanium Dental Implant">Titanium Dental Implant</option>
              <option value="Invisalign / Clear Aligners">Invisalign / Clear Aligners</option>
              <option value="Ceramic Braces Treatment">Ceramic Braces Treatment</option>
              <option value="Zirconia Crown & Bridge">Zirconia Crown & Bridge</option>
              <option value="Laser Teeth Whitening">Laser Teeth Whitening</option>
              <option value="Deep Ultrasonic Cleaning">Deep Ultrasonic Cleaning</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Treating Doctor</label>
              <input
                type="text"
                value={doctorName}
                onChange={(e) => setDoctorName(e.target.value)}
                required
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Estimated Cost (INR)</label>
              <input
                type="number"
                value={totalCost}
                onChange={(e) => setTotalCost(Number(e.target.value))}
                required
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500 font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Clinical Protocol Notes</label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Tooth #36 RCT. Single sitting planned. Recommend post-core."
              className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-xl"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white font-semibold rounded-xl flex items-center gap-2 shadow-lg shadow-brand-500/20 disabled:opacity-50"
            >
              {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Save Treatment Plan
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
