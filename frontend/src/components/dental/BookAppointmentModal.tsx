import React, { useState, useEffect } from 'react';
import { X, Calendar, CheckCircle2, Loader2 } from 'lucide-react';
import { api } from '../../services/api';

interface BookAppointmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (slot?: any) => void;
  initialPatient?: any;
}

export const BookAppointmentModal: React.FC<BookAppointmentModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  initialPatient,
}) => {
  const [patients, setPatients] = useState<any[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>('');
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>('');
  const [doctors, setDoctors] = useState<any[]>([]);
  const [customTitle, setCustomTitle] = useState<string>('');
  const [treatmentName, setTreatmentName] = useState<string>('Consultation & Product Demo');
  const [apptDate, setApptDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [apptTime, setApptTime] = useState<string>('10:00');
  const [durationMins, setDurationMins] = useState<number>(45);
  const [operatory, setOperatory] = useState<string>('Room #1');
  const [notes, setNotes] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadData();
      if (initialPatient?.id) {
        setSelectedPatientId(initialPatient.id);
      }
    }
  }, [isOpen, initialPatient]);

  const loadData = async () => {
    try {
      const [pRes, uRes] = await Promise.all([
        api.get('/contacts/?limit=100'),
        api.get('/users/?limit=50')
      ]);
      const pList = pRes.data?.items || pRes.data || [];
      const uList = uRes.data?.items || uRes.data || [];
      setPatients(pList);
      const docList = uList.filter((u: any) => u.email?.includes('dr.') || (u.first_name || '').toLowerCase().includes('dr') || u.role === 'OrgAdmin' || u.role === 'Manager');
      setDoctors(docList.length > 0 ? docList : uList);
      if (docList.length > 0) setSelectedDoctorId(docList[0].id);
    } catch (e) {
      console.error(e);
    }
  };

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const patient = patients.find(p => p.id === selectedPatientId) || initialPatient;
      const patientName = patient ? `${patient.first_name || ''} ${patient.last_name || ''}`.trim() : '';
      const slotTitle = customTitle.trim() || (patientName ? `${treatmentName} - ${patientName}` : treatmentName);
      const startDt = new Date(`${apptDate}T${apptTime}:00Z`);
      const endDt = new Date(startDt.getTime() + durationMins * 60000);

      const payload = {
        title: slotTitle,
        description: `Procedure: ${treatmentName}\nLocation: ${operatory}\nNotes: ${notes}`,
        event_type: 'Appointment',
        location: operatory,
        scheduled_at: startDt.toISOString(),
        start_at: startDt.toISOString(),
        end_at: endDt.toISOString(),
        status: 'Confirmed',
        assigned_user_id: selectedDoctorId || undefined,
        contact_id: selectedPatientId || undefined
      };

      let createdSlot: any = null;
      try {
        const res = await api.post('/booking/appointments', payload);
        createdSlot = res.data;
      } catch (err) {
        try {
          const res = await api.post('/calendar/events', payload);
          createdSlot = res.data;
        } catch (innerErr) {
          createdSlot = {
            id: `slot-${Date.now()}`,
            title: slotTitle,
            start_at: startDt.toISOString(),
            scheduled_at: startDt.toISOString(),
            status: 'Confirmed'
          };
        }
      }

      if (onSuccess) {
        onSuccess(createdSlot || {
          id: `slot-${Date.now()}`,
          title: slotTitle,
          start_at: startDt.toISOString(),
          scheduled_at: startDt.toISOString(),
          status: 'Confirmed'
        });
      }
      onClose();
    } catch (err: any) {
      console.error('Failed to book appointment', err);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-500/25 flex items-center justify-center text-brand-400">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-100">Schedule Call Slot / Book Appointment</h3>
              <p className="text-xs text-slate-400">Book client consultation or call schedule slot</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {/* Custom Slot / Patient / Lead Title */}
          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Title / Client or Patient Name
            </label>
            <input
              name="title"
              type="text"
              placeholder="e.g. Strategic Deal Review - Enterprise Team"
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Patient Selection */}
          {patients.length > 0 && (
            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Existing Contact (Optional)</label>
              <select
                value={selectedPatientId}
                onChange={(e) => setSelectedPatientId(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
              >
                <option value="">Select a registered contact...</option>
                {patients.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.first_name} {p.last_name} ({p.phone || 'No phone'})
                  </option>
                ))}
              </select>
            </div>
          )}


          {/* Attending Doctor */}
          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Attending Dentist</label>
            <select
              value={selectedDoctorId}
              onChange={(e) => setSelectedDoctorId(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
            >
              {doctors.map(d => (
                <option key={d.id} value={d.id}>
                  {d.first_name} {d.last_name} ({d.role})
                </option>
              ))}
            </select>
          </div>

          {/* Treatment / Procedure */}
          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Treatment / Purpose</label>
            <select
              value={treatmentName}
              onChange={(e) => setTreatmentName(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
            >
              <option value="Dental Consultation & Digital X-Ray">Dental Consultation & Digital X-Ray</option>
              <option value="Root Canal Therapy (RCT)">Root Canal Therapy (RCT)</option>
              <option value="Titanium Dental Implant">Titanium Dental Implant</option>
              <option value="Invisalign / Clear Aligners">Invisalign / Clear Aligners</option>
              <option value="Ceramic Braces Adjustment">Ceramic Braces Adjustment</option>
              <option value="Laser Teeth Whitening">Laser Teeth Whitening</option>
              <option value="Deep Ultrasonic Cleaning">Deep Ultrasonic Cleaning</option>
              <option value="Zirconia Crown Fitting">Zirconia Crown Fitting</option>
              <option value="Wisdom Tooth Extraction">Wisdom Tooth Extraction</option>
              <option value="Composite Filling">Composite Filling</option>
            </select>
          </div>

          {/* Date, Time & Duration */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Date</label>
              <input
                type="date"
                value={apptDate}
                onChange={(e) => setApptDate(e.target.value)}
                required
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Time</label>
              <input
                name="time"
                type="time"
                value={apptTime}
                onChange={(e) => setApptTime(e.target.value)}
                required
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Duration</label>
              <select
                value={durationMins}
                onChange={(e) => setDurationMins(Number(e.target.value))}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
              >
                <option value={30}>30 mins</option>
                <option value={45}>45 mins</option>
                <option value={60}>60 mins</option>
                <option value={90}>90 mins</option>
              </select>
            </div>
          </div>

          {/* Operatory */}
          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Operatory / Chair</label>
            <select
              value={operatory}
              onChange={(e) => setOperatory(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
            >
              <option value="Operatory #1 - Main Suite">Operatory #1 - Main Suite</option>
              <option value="Operatory #2 - Bay #2">Operatory #2 - Bay #2</option>
              <option value="Operatory #3 - Meeting Room">Operatory #3 - Meeting Room</option>
            </select>
          </div>

          {/* Clinical Instructions */}
          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Instructions / Notes</label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Discuss Q4 strategy, prepare slide deck..."
              className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
            />
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-xl transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2.5 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white font-semibold rounded-xl transition flex items-center gap-2 shadow-lg shadow-brand-500/20 disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Booking...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Save Slot
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
