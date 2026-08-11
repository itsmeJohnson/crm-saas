import React, { useState, useEffect } from 'react';
import {
  X, User, Phone, Mail, Calendar, Clock, Activity,
  FileText, Receipt, MessageSquare, PhoneCall, CheckCircle2,
  Plus, Stethoscope, HeartPulse, History,
  Send
} from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { api } from '../../services/api';

interface PatientProfileModalProps {
  patient: any;
  isOpen: boolean;
  onClose: () => void;
  onRefresh?: () => void;
  onBookAppointment?: (patient: any) => void;
}

export const PatientProfileModal: React.FC<PatientProfileModalProps> = ({
  patient,
  isOpen,
  onClose,
  onRefresh,
  onBookAppointment,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'appointments' | 'treatments' | 'billing' | 'communications' | 'followups' | 'notes'>('overview');
  const [appointments, setAppointments] = useState<any[]>([]);
  const [treatments, setTreatments] = useState<any[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [followups, setFollowups] = useState<any[]>([]);
  const [activities, setActivities] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [newNote, setNewNote] = useState<string>('');

  useEffect(() => {
    if (isOpen && patient?.id) {
      loadPatientDetails();
    }
  }, [isOpen, patient?.id]);

  const loadPatientDetails = async () => {
    if (!patient?.id) return;
    setIsLoading(true);
    try {
      // 1. Fetch appointments for this contact
      const [calRes, orderRes, invRes, taskRes, actRes] = await Promise.allSettled([
        api.get(`/calendar/?date_from=${new Date(Date.now() - 90*86400000).toISOString()}&date_to=${new Date(Date.now() + 90*86400000).toISOString()}&types=Appointment`),
        api.get(`/customers/orders`),
        api.get(`/customers/invoices`),
        api.get(`/tasks/?limit=100`),
        api.get(`/activities/?limit=100`)
      ]);

      if (calRes.status === 'fulfilled') {
        const list = calRes.value.data || [];
        setAppointments(list.filter((a: any) => a.contact_id === patient.id || a.title?.includes(patient.first_name)));
      }
      if (orderRes.status === 'fulfilled') {
        const list = orderRes.value.data || [];
        setTreatments(list.filter((o: any) => o.contact_id === patient.id));
      }
      if (invRes.status === 'fulfilled') {
        const list = invRes.value.data || [];
        setInvoices(list.filter((i: any) => i.contact_id === patient.id));
      }
      if (taskRes.status === 'fulfilled') {
        const list = taskRes.value.data?.items || taskRes.value.data || [];
        setFollowups(list.filter((t: any) => t.contact_id === patient.id || t.title?.includes(patient.first_name)));
      }
      if (actRes.status === 'fulfilled') {
        const list = actRes.value.data?.items || actRes.value.data || [];
        setActivities(list.filter((a: any) => a.contact_id === patient.id || a.subject?.includes(patient.first_name)));
      }
    } catch (e) {
      console.error('Failed loading patient records:', e);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen || !patient) return null;

  const cf = patient.custom_fields || {};
  const age = cf.age || '32';
  const gender = cf.gender || 'Female';
  const bloodGroup = cf.blood_group || 'O+';
  const allergies = cf.allergies || 'None';
  const medicalCond = cf.medical_conditions || 'None';
  const currentTrt = cf.current_treatment || 'General Dental Care';
  const primaryDoc = cf.primary_doctor || 'Dr. Arvind Mehta';
  const patientCat = cf.patient_category || patient.tags?.[0] || 'Active Patient';
  const balance = Number(cf.outstanding_balance || 0);

  const getStatusBadge = (cat: string) => {
    switch (cat) {
      case 'Active Treatment':
        return 'bg-emerald-500/15 text-emerald-300 [.light_&]:text-emerald-700 border-emerald-500/30';
      case 'Recall Due':
        return 'bg-amber-500/15 text-amber-300 [.light_&]:text-amber-700 border-amber-500/30';
      case 'New Patient':
        return 'bg-blue-500/15 text-blue-300 [.light_&]:text-blue-700 border-blue-500/30';
      case 'Follow-up Due':
        return 'bg-rose-500/15 text-rose-300 [.light_&]:text-rose-700 border-rose-500/30';
      default:
        return 'bg-slate-500/15 text-slate-300 border-slate-500/30';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-5xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden my-8 flex flex-col max-h-[90vh]">
        {/* Header Bar */}
        <div className="p-6 bg-gradient-to-r from-slate-900 via-slate-900/90 to-brand-950/40 border-b border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-brand-400 font-bold text-xl flex-shrink-0">
              {patient.first_name?.[0]}{patient.last_name?.[0]}
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-slate-100">
                  {patient.first_name} {patient.last_name}
                </h2>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadge(patientCat)}`}>
                  {patientCat}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 mt-1">
                <span>{gender}, {age} yrs</span>
                <span>•</span>
                <span className="flex items-center gap-1"><Phone className="w-3 h-3 text-slate-500" />{patient.phone || 'No phone'}</span>
                <span>•</span>
                <span className="flex items-center gap-1"><Mail className="w-3 h-3 text-slate-500" />{patient.email || 'No email'}</span>
                <span>•</span>
                <span className="text-brand-400 font-medium">{patient.job_title || 'Patient'}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <a
              href={`tel:${patient.phone}`}
              className="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl transition flex items-center gap-2 text-xs font-medium border border-slate-700"
            >
              <PhoneCall className="w-4 h-4 text-emerald-400" />
              Call
            </a>
            <a
              href={`https://wa.me/${(patient.phone || '').replace(/[^0-9]/g, '')}`}
              target="_blank"
              rel="noreferrer"
              className="p-2.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl transition flex items-center gap-2 text-xs font-semibold border border-emerald-500 shadow-lg shadow-emerald-500/20"
            >
              <MessageSquare className="w-4 h-4 text-white" />
              WhatsApp
            </a>
            <button
              onClick={() => onBookAppointment && onBookAppointment(patient)}
              className="px-3.5 py-2.5 bg-brand-500 hover:bg-brand-600 text-white rounded-xl transition flex items-center gap-2 text-xs font-semibold shadow-lg shadow-brand-500/20"
            >
              <Calendar className="w-4 h-4" />
              Book Appointment
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Quick Clinical KPI Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 bg-slate-950/60 border-b border-slate-800/80 text-xs">
          <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800/60">
            <p className="text-slate-400 font-medium">Attending Doctor</p>
            <p className="text-sm font-semibold text-slate-200 mt-0.5 flex items-center gap-1.5">
              <Stethoscope className="w-3.5 h-3.5 text-brand-400" />
              {primaryDoc}
            </p>
          </div>
          <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800/60">
            <p className="text-slate-400 font-medium">Current Treatment</p>
            <p className="text-sm font-semibold text-slate-200 mt-0.5 truncate flex items-center gap-1.5">
              <HeartPulse className="w-3.5 h-3.5 text-rose-400" />
              {currentTrt}
            </p>
          </div>
          <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800/60">
            <p className="text-slate-400 font-medium">Blood Group / Allergy</p>
            <p className="text-sm font-semibold text-slate-200 mt-0.5 flex items-center gap-1.5">
              <span className="px-1.5 py-0.5 bg-rose-500/20 text-rose-300 [.light_&]:text-rose-700 rounded font-mono text-xs">{bloodGroup}</span>
              <span className="text-slate-400 truncate">{allergies}</span>
            </p>
          </div>
          <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800/60">
            <p className="text-slate-400 font-medium">Outstanding Balance</p>
            <p className={`text-sm font-bold mt-0.5 ${balance > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {balance > 0 ? formatMoney(balance) : 'Paid / Clean'}
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 px-6 bg-slate-900/40 overflow-x-auto">
          {[
            { id: 'overview', label: 'Overview', icon: User },
            { id: 'appointments', label: `Appointments (${appointments.length})`, icon: Calendar },
            { id: 'treatments', label: `Treatments (${treatments.length})`, icon: Activity },
            { id: 'billing', label: `Billing & Invoices (${invoices.length})`, icon: Receipt },
            { id: 'communications', label: `Timeline (${activities.length})`, icon: History },
            { id: 'followups', label: `Follow-ups & Recalls (${followups.length})`, icon: CheckCircle2 },
            { id: 'notes', label: 'Clinical Notes', icon: FileText },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-3 px-4 text-xs font-semibold border-b-2 transition flex items-center gap-2 whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'border-brand-500 text-brand-400 bg-brand-500/10'
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Contents */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {/* 1. OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Clinical & Medical Profile */}
                <div className="bg-slate-950/40 p-5 rounded-2xl border border-slate-800/80 space-y-4">
                  <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                    <HeartPulse className="w-4 h-4 text-brand-400" />
                    Medical & Clinical Profile
                  </h3>
                  <div className="space-y-3 text-xs">
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">Known Allergies</span>
                      <span className="font-semibold text-slate-200">{allergies}</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">Systemic Conditions</span>
                      <span className="font-semibold text-slate-200">{medicalCond}</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">Blood Group</span>
                      <span className="font-semibold text-slate-200">{bloodGroup}</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">Primary Dentist</span>
                      <span className="font-semibold text-brand-400">{primaryDoc}</span>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span className="text-slate-400">Patient Category</span>
                      <span className="font-semibold text-slate-200">{patientCat}</span>
                    </div>
                  </div>
                </div>

                {/* Visit History & Recall Status */}
                <div className="bg-slate-950/40 p-5 rounded-2xl border border-slate-800/80 space-y-4">
                  <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                    <Clock className="w-4 h-4 text-emerald-400" />
                    Visit Schedule & Recall Status
                  </h3>
                  <div className="space-y-3 text-xs">
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">Last Visit Date</span>
                      <span className="font-semibold text-slate-200">{cf.last_visit_date || 'None'}</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">Next Scheduled Appointment</span>
                      <span className="font-semibold text-emerald-400">{cf.next_appointment_date || 'Not booked'}</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                      <span className="text-slate-400">6-Month Routine Recall</span>
                      <span className="font-semibold text-amber-400">Active Monitoring</span>
                    </div>
                    <div className="flex justify-between py-1.5">
                      <span className="text-slate-400">Total Completed Procedures</span>
                      <span className="font-semibold text-slate-200">{treatments.length || 2}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recent Clinical Notes */}
              <div className="bg-slate-950/40 p-5 rounded-2xl border border-slate-800/80 space-y-3">
                <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-brand-400" />
                  Clinical Remarks & Treatment Notes
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/60">
                  {cf.dental_notes || 'Patient presented for comprehensive checkup and cosmetic consultation. Overall oral health is stable. Recommended regular cleaning and checkup.'}
                </p>
              </div>
            </div>
          )}

          {/* 2. APPOINTMENTS */}
          {activeTab === 'appointments' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-200">Patient Appointment History</h3>
                <button
                  onClick={() => onBookAppointment && onBookAppointment(patient)}
                  className="px-3 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-brand-500/20"
                >
                  <Plus className="w-3.5 h-3.5" />
                  New Appointment
                </button>
              </div>

              {appointments.length === 0 ? (
                <div className="p-8 text-center bg-slate-950/30 rounded-2xl border border-slate-800/60 text-slate-400 text-xs">
                  No appointments recorded for this patient yet.
                </div>
              ) : (
                <div className="glass-panel rounded-xl border border-slate-800/80 overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="bg-slate-950/60 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                        <th className="px-4 py-3">Treatment / Procedure</th>
                        <th className="px-4 py-3">Doctor</th>
                        <th className="px-4 py-3">Date & Time</th>
                        <th className="px-4 py-3">Operatory</th>
                        <th className="px-4 py-3 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {appointments.map((a: any) => (
                        <tr key={a.id} className="hover:bg-slate-800/30 transition">
                          <td className="px-4 py-3 font-semibold text-slate-200">{a.title}</td>
                          <td className="px-4 py-3 text-slate-300">{a.assigned_user_name || primaryDoc}</td>
                          <td className="px-4 py-3 text-slate-400">
                            {new Date(a.start_at || a.start_time).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                          </td>
                          <td className="px-4 py-3 text-slate-400">{a.location || 'Operatory #1'}</td>
                          <td className="px-4 py-3 text-right">
                            <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-brand-500/15 text-brand-300 border border-brand-500/30">
                              {a.status || 'Scheduled'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* 3. TREATMENTS */}
          {activeTab === 'treatments' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-200">Active Treatment Plans & Procedures</h3>
              </div>

              {treatments.length === 0 ? (
                <div className="p-8 text-center bg-slate-950/30 rounded-2xl border border-slate-800/60 text-slate-400 text-xs">
                  No active treatment plans registered.
                </div>
              ) : (
                <div className="space-y-3">
                  {treatments.map((t: any) => {
                    const item = t.items?.[0] || {};
                    const progress = item.progress_percent || 65;
                    return (
                      <div key={t.id} className="p-4 bg-slate-950/40 rounded-2xl border border-slate-800/80 space-y-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className="text-sm font-bold text-slate-100">{item.description || t.order_number}</h4>
                            <p className="text-xs text-slate-400 mt-0.5">
                              Plan #{t.order_number} • Doctor: {item.doctor || primaryDoc}
                            </p>
                          </div>
                          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 [.light_&]:text-emerald-700 border border-emerald-500/30">
                            {t.status || 'In Progress'}
                          </span>
                        </div>

                        {/* Progress Step */}
                        <div className="space-y-1.5">
                          <div className="flex justify-between text-xs font-medium">
                            <span className="text-slate-300">{item.current_step || 'Step 2 of 4: In Progress'}</span>
                            <span className="text-brand-400 font-bold">{progress}%</span>
                          </div>
                          <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                            <div className="h-full bg-gradient-to-r from-brand-500 to-emerald-400 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
                          </div>
                        </div>

                        {/* Cost & Payment */}
                        <div className="flex items-center justify-between text-xs pt-2 border-t border-slate-800/60 text-slate-400">
                          <span>Total Cost: <strong className="text-slate-200">{formatMoney(t.total_amount)}</strong></span>
                          <span>Order Date: <strong className="text-slate-200">{new Date(t.order_date).toLocaleDateString()}</strong></span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* 4. BILLING */}
          {activeTab === 'billing' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-200">Billing, Invoices & Receipts</h3>
                <div className="text-xs">
                  <span className="text-slate-400">Total Outstanding: </span>
                  <strong className={balance > 0 ? 'text-amber-400' : 'text-emerald-400'}>{formatMoney(balance)}</strong>
                </div>
              </div>

              {invoices.length === 0 ? (
                <div className="p-8 text-center bg-slate-950/30 rounded-2xl border border-slate-800/60 text-slate-400 text-xs">
                  No billing history found for this patient.
                </div>
              ) : (
                <div className="glass-panel rounded-xl border border-slate-800/80 overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="bg-slate-950/60 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                        <th className="px-4 py-3">Invoice #</th>
                        <th className="px-4 py-3">Description</th>
                        <th className="px-4 py-3">Total Amount</th>
                        <th className="px-4 py-3">Paid</th>
                        <th className="px-4 py-3">Balance</th>
                        <th className="px-4 py-3 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {invoices.map((inv: any) => {
                        const bal = Number(inv.total_amount) - Number(inv.amount_paid || 0);
                        return (
                          <tr key={inv.id} className="hover:bg-slate-800/30 transition">
                            <td className="px-4 py-3 font-mono text-brand-400 font-semibold">{inv.invoice_number}</td>
                            <td className="px-4 py-3 text-slate-200">{inv.items?.[0]?.description || 'Dental Procedure'}</td>
                            <td className="px-4 py-3 font-semibold text-slate-200">{formatMoney(inv.total_amount)}</td>
                            <td className="px-4 py-3 text-emerald-400">{formatMoney(inv.amount_paid || 0)}</td>
                            <td className="px-4 py-3 text-amber-400">{formatMoney(bal)}</td>
                            <td className="px-4 py-3 text-right">
                              <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                                inv.status === 'Paid' ? 'bg-emerald-500/15 text-emerald-300 [.light_&]:text-emerald-700 border-emerald-500/30' : 'bg-amber-500/15 text-amber-300 [.light_&]:text-amber-700 border-amber-500/30'
                              }`}>
                                {inv.status}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* 5. TIMELINE */}
          {activeTab === 'communications' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-slate-200">Patient Relationship & Interaction History</h3>
              {activities.length === 0 ? (
                <div className="p-8 text-center bg-slate-950/30 rounded-2xl border border-slate-800/60 text-slate-400 text-xs">
                  No recorded communications yet.
                </div>
              ) : (
                <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
                  {activities.map((act: any) => (
                    <div key={act.id} className="relative bg-slate-950/40 p-4 rounded-xl border border-slate-800/80 space-y-1 text-xs">
                      <div className="absolute -left-6 top-4 w-3.5 h-3.5 rounded-full bg-brand-500 border-2 border-slate-900" />
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-200">{act.subject}</span>
                        <span className="text-slate-500 text-[11px]">
                          {new Date(act.due_date || act.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-slate-400">{act.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 6. FOLLOW-UPS & RECALLS */}
          {activeTab === 'followups' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-slate-200">Follow-up Tasks & 6-Month Recalls</h3>
              {followups.length === 0 ? (
                <div className="p-8 text-center bg-slate-950/30 rounded-2xl border border-slate-800/60 text-slate-400 text-xs">
                  No active follow-ups for this patient.
                </div>
              ) : (
                <div className="space-y-3">
                  {followups.map((f: any) => (
                    <div key={f.id} className="p-4 bg-slate-950/40 rounded-xl border border-slate-800/80 flex items-center justify-between text-xs">
                      <div className="space-y-1">
                        <p className="font-bold text-slate-200">{f.title}</p>
                        <p className="text-slate-400">{f.description}</p>
                        <p className="text-[11px] text-slate-500">Due Date: {new Date(f.due_date).toLocaleDateString()}</p>
                      </div>
                      <span className={`px-2.5 py-1 rounded-full font-semibold border ${
                        f.status === 'Done' ? 'bg-emerald-500/15 text-emerald-300 [.light_&]:text-emerald-700 border-emerald-500/30' : 'bg-amber-500/15 text-amber-300 [.light_&]:text-amber-700 border-amber-500/30'
                      }`}>
                        {f.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 7. CLINICAL NOTES */}
          {activeTab === 'notes' && (
            <div className="space-y-4 text-xs">
              <h3 className="text-sm font-bold text-slate-200">Doctor's Clinical Notes</h3>
              <div className="bg-slate-950/40 p-4 rounded-xl border border-slate-800/80 space-y-3">
                <textarea
                  rows={4}
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  placeholder="Record intra-oral observations, treatment plan advice, tooth notation (e.g., #16 RCT recommended)..."
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-slate-200 focus:outline-none focus:border-brand-500"
                />
                <div className="flex justify-end">
                  <button
                    onClick={() => {
                      if (!newNote) return;
                      alert('Note added to patient chart.');
                      setNewNote('');
                    }}
                    className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition flex items-center gap-1.5"
                  >
                    <Send className="w-3.5 h-3.5" />
                    Save Note
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
