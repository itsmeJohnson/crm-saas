import React, { useState, useEffect } from 'react';
import { X, Calendar, CheckCircle2, Loader2 } from 'lucide-react';
import { api } from '../../services/api';

interface BookAppointmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
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
  const [treatmentName, setTreatmentName] = useState<string>('Dental Consultation & Digital X-Ray');
  const [apptDate, setApptDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [apptTime, setApptTime] = useState<string>('10:00');
  const [durationMins, setDurationMins] = useState<number>(45);
  const [operatory, setOperatory] = useState<string>('Operatory #1');
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
      const patientName = patient ? `${patient.first_name} ${patient.last_name}` : 'Patient';
      const startDt = new Date(`${apptDate}T${apptTime}:00Z`);
      const endDt = new Date(startDt.getTime() + durationMins * 60000);

      await api.post('/calendar/events', {
        title: `${treatmentName} - ${patientName}`,
        description: `Procedure: ${treatmentName}\nOperatory: ${operatory}\nNotes: ${notes}`,
        event_type: 'Appointment',
        location: operatory,
        start_at: startDt.toISOString(),
        end_at: endDt.toISOString(),
        status: 'Scheduled',
        assigned_user_id: selectedDoctorId || undefined,
        contact_id: selectedPatientId || undefined
      });

      alert('Appointment booked successfully!');
      if (onSuccess) onSuccess();
      onClose();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to book appointment');
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
              <h3 className="text-lg font-bold text-slate-100">Schedule Dental Appointment</h3>
              <p className="text-xs text-slate-400">Book patient consultation or treatment session</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {/* Patient Selection */}
          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Patient</label>
            <select
              value={selectedPatientId}
              onChange={(e) => setSelectedPatientId(e.target.value)}
              required
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-brand-500"
            >
              <option value="">Select a registered patient...</option>
              {patients.map(p => (
                <option key={p.id} value={p.id}>
                  {p.first_name} {p.last_name} ({p.phone || 'No phone'})
                </option>
              ))}
            </select>
          </div>

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
              <option value="Operatory #1 - Main Dental Suite">Operatory #1 - Main Dental Suite</option>
              <option value="Operatory #2 - Orthodontic Bay">Operatory #2 - Orthodontic Bay</option>
              <option value="Operatory #3 - Surgical & Implant O.T.">Operatory #3 - Surgical & Implant O.T.</option>
            </select>
          </div>

          {/* Clinical Instructions */}
          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Clinical Instructions / Notes</label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Keep intra-oral camera ready, patient sensitive to cold..."
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
                  Confirm Booking
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
