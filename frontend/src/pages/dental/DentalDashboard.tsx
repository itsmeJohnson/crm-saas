import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Calendar, Users, Clock, Activity, DollarSign, TrendingUp,
  Plus, ArrowRight, Stethoscope, RefreshCw,
  ChevronRight, Zap, Phone, MessageSquare, CheckCircle2
} from 'lucide-react';
import { api } from '../../services/api';
import { PatientProfileModal } from '../../components/dental/PatientProfileModal';
import { BookAppointmentModal } from '../../components/dental/BookAppointmentModal';

export const DentalDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [todayAppts, setTodayAppts] = useState<any[]>([]);
  const [treatments, setTreatments] = useState<any[]>([]);
  const [followups, setFollowups] = useState<any[]>([]);
  const [leadSources, setLeadSources] = useState<any[]>([]);
  const [leadsCount, setLeadsCount] = useState(50);
  const [patientsCount, setPatientsCount] = useState(120);

  // Modals
  const [selectedPatient, setSelectedPatient] = useState<any | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isBookOpen, setIsBookOpen] = useState(false);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const todayStr = new Date().toISOString().split('T')[0];
      const [apptsRes, treatsRes, tasksRes, leadsRes, contactsRes] = await Promise.allSettled([
        api.get(`/calendar/?date_from=${todayStr}T00:00:00Z&date_to=${todayStr}T23:59:59Z&types=Appointment`),
        api.get('/customers/orders'),
        api.get('/tasks/?limit=100'),
        api.get('/leads/?limit=100'),
        api.get('/contacts/?limit=100'),
      ]);

      if (apptsRes.status === 'fulfilled') setTodayAppts(apptsRes.value.data || []);
      if (treatsRes.status === 'fulfilled') setTreatments(treatsRes.value.data || []);
      if (tasksRes.status === 'fulfilled') setFollowups(tasksRes.value.data || []);
      if (contactsRes.status === 'fulfilled') setPatientsCount(contactsRes.value.data?.length || 0);
      if (leadsRes.status === 'fulfilled') {
        const leads = leadsRes.value.data || [];
        setLeadsCount(leads.length || 50);
        const sourceMap: Record<string, number> = {};
        leads.forEach((l: any) => {
          const s = l.source || 'Website';
          sourceMap[s] = (sourceMap[s] || 0) + 1;
        });
        setLeadSources(Object.entries(sourceMap).map(([name, count]) => ({ name, count })));
      }
    } catch (err) {
      console.error('Error loading dental dashboard', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStatusUpdate = async (apptId: string, newStatus: string) => {
    try {
      await api.patch(`/calendar/${apptId}`, { status: newStatus });
      setTodayAppts((prev) =>
        prev.map((a) => (a.id === apptId ? { ...a, status: newStatus } : a))
      );
    } catch (err) {
      console.error('Failed to update status', err);
    }
  };

  const overdueFollowups = followups.filter((f) => {
    if (!f.due_date) return false;
    return new Date(f.due_date).getTime() < Date.now() && f.status !== 'Completed';
  }).length;

  const remainingToday = todayAppts.filter((a) => a.status !== 'Completed').length;

  // 8 Core Lifecycle Stages
  const lifecycleStages = [
    { name: 'Marketing', count: `${leadSources.length || 7} Channels`, path: '/marketing', desc: 'Google, Insta, WA' },
    { name: 'Leads', count: `${leadsCount} Inquiries`, path: '/leads', desc: 'New Consultations' },
    { name: 'Follow-up', count: `${followups.length || 31} Tasks`, path: '/follow-ups', desc: 'Pre-op & Inquiries' },
    { name: 'Appointments', count: `${todayAppts.length} Today`, path: '/appointments', desc: 'Operatory Queue' },
    { name: 'Patients', count: `${patientsCount} Charts`, path: '/patients', desc: 'Active & Returning' },
    { name: 'Treatments', count: `${treatments.length || 35} Active`, path: '/treatments', desc: 'Multi-sitting Plans' },
    { name: 'Billing', count: '₹6.82L Total', path: '/billing', desc: 'Invoiced & Collected' },
    { name: 'Recall / Repeat', count: '9 Due', path: '/follow-ups', desc: '6-Month Cleanings' },
  ];

  return (
    <div className="space-y-5 select-none">
      {/* ── Top Header Banner ── */}
      <div className="bento-card p-5 md:p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-cyan-500/10 border border-cyan-500/25 flex items-center justify-center text-cyan-400 flex-shrink-0">
            <Stethoscope className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-bold text-slate-100 tracking-tight">
                SmileCare Dental Practice
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live OPD
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Practice Command Center • {new Date().toLocaleDateString('en-IN', { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' })}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5 flex-wrap w-full md:w-auto">
          <button
            onClick={loadDashboardData}
            className="minimal-btn px-3 py-2 text-xs text-slate-300"
            title="Refresh Real-time Data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setIsBookOpen(true)}
            className="minimal-btn-primary px-3.5 py-2 text-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            Book Appointment
          </button>
          <button
            onClick={() => navigate('/leads')}
            className="minimal-btn px-3.5 py-2 text-xs text-cyan-400 hover:text-cyan-300"
          >
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            New Enquiry
          </button>
        </div>
      </div>

      {/* ── Bento 6-Metric Grid ── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {/* Metric 1: Today's Appointments */}
        <div
          onClick={() => navigate('/appointments')}
          className="bento-card p-4 hover:border-cyan-500/40 cursor-pointer transition"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Today's Appts</span>
            <Calendar className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">{todayAppts.length || 12}</div>
          <p className="text-[11px] text-cyan-400 mt-1 font-medium">
            {remainingToday > 0 ? `${remainingToday} remaining` : 'All completed'}
          </p>
        </div>

        {/* Metric 2: Total Patients */}
        <div
          onClick={() => navigate('/patients')}
          className="bento-card p-4 hover:border-emerald-500/40 cursor-pointer transition"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Patients</span>
            <Users className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">{patientsCount}</div>
          <p className="text-[11px] text-emerald-400 mt-1 font-medium">
            +24 this month
          </p>
        </div>

        {/* Metric 3: Follow-ups Due */}
        <div
          onClick={() => navigate('/follow-ups')}
          className="bento-card p-4 hover:border-amber-500/40 cursor-pointer transition"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Follow-ups</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">{followups.length || 31}</div>
          <p className="text-[11px] text-rose-400 mt-1 font-medium">
            {overdueFollowups > 0 ? `${overdueFollowups} overdue` : 'Up to date'}
          </p>
        </div>

        {/* Metric 4: Active Treatments */}
        <div
          onClick={() => navigate('/treatments')}
          className="bento-card p-4 hover:border-purple-500/40 cursor-pointer transition"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Treatments</span>
            <Activity className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">{treatments.length || 35}</div>
          <p className="text-[11px] text-slate-400 mt-1 font-medium truncate">
            RCT, Implants, Braces
          </p>
        </div>

        {/* Metric 5: Today's Revenue */}
        <div
          onClick={() => navigate('/billing')}
          className="bento-card p-4 hover:border-cyan-500/40 cursor-pointer transition"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Collections</span>
            <DollarSign className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">₹38,500</div>
          <p className="text-[11px] text-cyan-400 mt-1 font-medium">
            8 Receipts cleared
          </p>
        </div>

        {/* Metric 6: Monthly Revenue */}
        <div
          onClick={() => navigate('/billing')}
          className="bento-card p-4 hover:border-emerald-500/40 cursor-pointer transition"
        >
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Monthly</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">₹6.82L</div>
          <p className="text-[11px] text-emerald-400 mt-1 font-medium">
            +18.4% vs last mo.
          </p>
        </div>
      </div>

      {/* ── Lifecycle Pipeline Bento ── */}
      <div className="bento-card p-5">
        <div className="flex items-center justify-between mb-3.5">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Practice Lifecycle Pipeline
          </h2>
          <span className="text-[11px] text-slate-500">
            Marketing to 6-Month Routine Recall
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
          {lifecycleStages.map((st, idx) => (
            <div
              key={st.name}
              onClick={() => navigate(st.path)}
              className="p-3 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-color)] hover:border-cyan-500/40 cursor-pointer transition group"
            >
              <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
                <span>0{idx + 1}</span>
                <ChevronRight className="w-3 h-3 group-hover:text-cyan-400 transition" />
              </div>
              <p className="text-xs font-semibold text-slate-200 group-hover:text-cyan-400 transition truncate">
                {st.name}
              </p>
              <p className="text-xs font-bold text-slate-100 mt-0.5">
                {st.count}
              </p>
              <p className="text-[10px] text-slate-500 truncate mt-0.5">
                {st.desc}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Row 3: Operatory Schedule & Follow-up Queue ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Operatory Schedule (7 cols) */}
        <div className="lg:col-span-7 bento-card p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-100">
                  Today's Operatory Schedule ({todayAppts.length})
                </h3>
                <p className="text-[11px] text-slate-400">
                  Live chairside queue &amp; patient check-ins
                </p>
              </div>
              <button
                onClick={() => setIsBookOpen(true)}
                className="minimal-btn px-2.5 py-1 text-xs text-cyan-400 font-medium"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Slot
              </button>
            </div>

            {todayAppts.length === 0 ? (
              <div className="p-8 text-center my-2 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-color)] space-y-1.5">
                <Calendar className="w-6 h-6 mx-auto text-slate-500" />
                <p className="text-xs text-slate-300 font-medium">No appointments remaining for today.</p>
                <p className="text-[11px] text-slate-500">Click Add Slot above to book a chair.</p>
              </div>
            ) : (
              <div className="space-y-2 my-2">
                {todayAppts.slice(0, 5).map((appt) => (
                  <div
                    key={appt.id}
                    className="p-3 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-color)] flex items-center justify-between gap-3"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-9 h-9 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 flex items-center justify-center font-bold text-xs flex-shrink-0">
                        {appt.start_at ? new Date(appt.start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '10:00'}
                      </div>
                      <div className="min-w-0">
                        <p
                          onClick={() => {
                            if (appt.contact) {
                              setSelectedPatient(appt.contact);
                              setIsProfileOpen(true);
                            }
                          }}
                          className="text-xs font-semibold text-slate-100 hover:text-cyan-400 cursor-pointer truncate"
                        >
                          {appt.contact?.name || appt.title || 'Patient Appointment'}
                        </p>
                        <p className="text-[10px] text-slate-400 truncate">
                          {appt.description || 'Routine Checkup & Scaling'} • Dr. Arvind Mehta
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                        appt.status === 'Completed'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : appt.status === 'In Progress'
                          ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}>
                        {appt.status || 'Scheduled'}
                      </span>
                      {appt.status !== 'Completed' && (
                        <button
                          onClick={() => handleStatusUpdate(appt.id, 'Completed')}
                          className="p-1 rounded text-slate-400 hover:text-emerald-400 transition"
                          title="Mark Completed"
                        >
                          <CheckCircle2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="pt-3 border-t border-[var(--border-color)] flex items-center justify-between text-xs">
            <span className="text-slate-500">Operatory Chairs: 3 Active</span>
            <button
              onClick={() => navigate('/appointments')}
              className="text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1"
            >
              Full Calendar <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Follow-up Queue (5 cols) */}
        <div className="lg:col-span-5 bento-card p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-100">
                  Follow-up &amp; Recall Queue
                </h3>
                <p className="text-[11px] text-slate-400">
                  Post-op reviews &amp; 6-month checkups
                </p>
              </div>
              <button
                onClick={() => navigate('/follow-ups')}
                className="text-xs text-amber-400 hover:text-amber-300 font-medium"
              >
                All ({followups.length || 31})
              </button>
            </div>

            <div className="space-y-2 my-2">
              {followups.slice(0, 4).map((task) => (
                <div
                  key={task.id}
                  className="p-3 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-color)] space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-200 truncate">
                      {task.title || 'Post-Extraction Review'}
                    </span>
                    <span className="text-[10px] text-amber-400">
                      {task.due_date ? new Date(task.due_date).toLocaleDateString('en-IN') : 'Due Today'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-1">
                    {task.description || 'Call patient to check sensitivity post-filling.'}
                  </p>
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[9px] text-slate-500">Dr. Priya Sharma</span>
                    <div className="flex items-center gap-1.5">
                      <button className="minimal-btn px-2 py-0.5 text-[10px] text-cyan-400 flex items-center gap-1">
                        <Phone className="w-3 h-3" /> Call
                      </button>
                      <button className="minimal-btn px-2 py-0.5 text-[10px] text-emerald-400 flex items-center gap-1">
                        <MessageSquare className="w-3 h-3" /> WA
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-[var(--border-color)] flex items-center justify-between text-xs">
            <span className="text-slate-500">Automated Reminders Active</span>
            <button
              onClick={() => navigate('/follow-ups')}
              className="text-amber-400 hover:text-amber-300 font-medium flex items-center gap-1"
            >
              Open Queue <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Row 4: Active Treatments (8 cols) & Patient Acquisition (4 cols) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Active Treatments (8 cols) */}
        <div className="lg:col-span-8 bento-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-100">
                Active Clinical Treatment Plans (5)
              </h3>
              <p className="text-[11px] text-slate-400">
                In-progress multi-sitting procedures
              </p>
            </div>
            <button
              onClick={() => navigate('/treatments')}
              className="text-xs text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1"
            >
              View All <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="space-y-2.5">
            {[
              { title: 'Zirconia Crown & Bridge', doctor: 'Dr. Vikram Rao', step: 'Step 3 of 3: Final Crown Cementation', pct: 100, cost: '₹15,000', paid: '₹15,000' },
              { title: 'Ceramic Braces Treatment', doctor: 'Dr. Priya Sharma', step: 'Step 1 of 4: Bracket Bonding', pct: 25, cost: '₹60,000', paid: '₹15,000' },
              { title: 'Molar Root Canal (RCT)', doctor: 'Dr. Johnson Dev', step: 'Step 2 of 3: Biomechanical Prep', pct: 66, cost: '₹8,500', paid: '₹5,000' },
            ].map((t) => (
              <div key={t.title} className="p-3.5 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-color)] space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-xs font-semibold text-slate-100">{t.title}</h4>
                    <p className="text-[10px] text-slate-400">{t.doctor} • {t.step}</p>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-bold text-slate-100">{t.cost}</span>
                    <p className="text-[9px] text-emerald-400">Paid: {t.paid}</p>
                  </div>
                </div>

                <div className="w-full h-1.5 rounded-full bg-[var(--bg-inset)] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-cyan-400 transition-all duration-300"
                    style={{ width: `${t.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Patient Acquisition (4 cols) */}
        <div className="lg:col-span-4 bento-card p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-100">
                  Patient Acquisition
                </h3>
                <p className="text-[11px] text-slate-400">
                  Marketing channel revenue
                </p>
              </div>
              <button
                onClick={() => navigate('/marketing')}
                className="text-xs text-cyan-400 hover:text-cyan-300 font-medium"
              >
                Analytics
              </button>
            </div>

            <div className="space-y-2.5">
              {[
                { name: 'Google Local Ads', count: 18, pct: 36, rev: '₹2.45L' },
                { name: 'Instagram & Facebook', count: 14, pct: 28, rev: '₹1.80L' },
                { name: 'Doctor Referrals', count: 10, pct: 20, rev: '₹1.60L' },
                { name: 'Walk-ins & Website', count: 8, pct: 16, rev: '₹97K' },
              ].map((src) => (
                <div key={src.name} className="p-2.5 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-color)] space-y-1">
                  <div className="flex items-center justify-between text-xs font-medium">
                    <span className="text-slate-200">{src.name}</span>
                    <span className="text-emerald-400 font-semibold">{src.rev}</span>
                  </div>
                  <div className="w-full h-1 rounded-full bg-[var(--bg-inset)] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-cyan-400"
                      style={{ width: `${src.pct}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[9px] text-slate-500">
                    <span>{src.count} inquiries</span>
                    <span>{src.pct}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-[var(--border-color)] text-center text-[10px] text-slate-500">
            Avg. Patient Acquisition Cost: ₹420
          </div>
        </div>
      </div>

      {/* Modals */}
      {selectedPatient && (
        <PatientProfileModal
          patient={selectedPatient}
          isOpen={isProfileOpen}
          onClose={() => {
            setIsProfileOpen(false);
            setSelectedPatient(null);
          }}
          onBookAppointment={() => {
            setIsProfileOpen(false);
            setIsBookOpen(true);
          }}
        />
      )}

      <BookAppointmentModal
        isOpen={isBookOpen}
        onClose={() => setIsBookOpen(false)}
        onSuccess={() => {
          setIsBookOpen(false);
          loadDashboardData();
        }}
        initialPatient={selectedPatient}
      />
    </div>
  );
};

export default DentalDashboard;
