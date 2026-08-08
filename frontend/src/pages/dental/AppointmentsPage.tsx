import React, { useState, useEffect } from 'react';
import {
  Calendar, Plus, ChevronLeft, ChevronRight, RefreshCw, Eye, Stethoscope, Clock
} from 'lucide-react';
import { api } from '../../services/api';
import { BookAppointmentModal } from '../../components/dental/BookAppointmentModal';
import { PatientProfileModal } from '../../components/dental/PatientProfileModal';

export const AppointmentsPage: React.FC = () => {
  const [appointments, setAppointments] = useState<any[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [statusFilter, setStatusFilter] = useState('All');
  const [doctorFilter, setDoctorFilter] = useState('All');
  const [viewMode, setViewMode] = useState<'day' | 'week' | 'month'>('day');
  const [isLoading, setIsLoading] = useState(true);

  // Modals
  const [isBookOpen, setIsBookOpen] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState<any | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  useEffect(() => {
    fetchAppointments();
  }, [selectedDate]);

  const fetchAppointments = async () => {
    setIsLoading(true);
    try {
      const from = new Date(new Date(selectedDate).getTime() - 7 * 86400000).toISOString();
      const to = new Date(new Date(selectedDate).getTime() + 14 * 86400000).toISOString();
      const res = await api.get(`/calendar/?date_from=${from}&date_to=${to}&types=Appointment`);
      setAppointments(res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateStatus = async (apptId: string, newStatus: string) => {
    try {
      await api.patch(`/calendar/events/${apptId}`, { status: newStatus });
      setAppointments(prev => prev.map(a => a.id === apptId ? { ...a, status: newStatus } : a));
    } catch {
      setAppointments(prev => prev.map(a => a.id === apptId ? { ...a, status: newStatus } : a));
    }
  };

  const filteredAppts = appointments.filter((a) => {
    const aDate = new Date(a.start_at || a.start_time).toISOString().split('T')[0];
    const matchesDate = viewMode === 'day' ? aDate === selectedDate : true;
    const matchesStatus = statusFilter === 'All' || a.status === statusFilter;
    const matchesDoc = doctorFilter === 'All' || (a.assigned_user_name || '').includes(doctorFilter);
    return matchesDate && matchesStatus && matchesDoc;
  });

  const statuses = ['All', 'Booked', 'Confirmed', 'Arrived', 'In Treatment', 'Completed', 'Rescheduled', 'Cancelled'];

  const changeDate = (days: number) => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + days);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  return (
    <div className="space-y-6 select-none">
      {/* Header Bento */}
      <div className="bento-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/25 flex-shrink-0">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-100">
              Operatory Appointments &amp; Calendar
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Live chair allocation, procedure time slots &amp; doctor consultation schedule.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsBookOpen(true)}
            className="neo-btn-primary px-4 py-2.5 text-xs flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Book Patient Slot
          </button>
        </div>
      </div>

      {/* Date Navigation & Controls Bento */}
      <div className="bento-card p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Day / Week switch & Date navigator */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 p-1 neo-inset rounded-xl">
              <button
                onClick={() => setViewMode('day')}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                  viewMode === 'day' ? 'neo-btn text-cyan-400' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Day Agenda
              </button>
              <button
                onClick={() => setViewMode('week')}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                  viewMode === 'week' ? 'neo-btn text-cyan-400' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Week View
              </button>
            </div>

            {/* Date Picker */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => changeDate(-1)}
                className="neo-btn p-2 text-slate-300"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="neo-input py-1.5 px-3 text-xs font-bold text-slate-200"
              />
              <button
                onClick={() => changeDate(1)}
                className="neo-btn p-2 text-slate-300"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
              <button
                onClick={() => setSelectedDate(new Date().toISOString().split('T')[0])}
                className="neo-btn px-3 py-1.5 text-xs text-cyan-400 font-semibold"
              >
                Today
              </button>
            </div>
          </div>

          {/* Doctor Filter */}
          <select
            value={doctorFilter}
            onChange={(e) => setDoctorFilter(e.target.value)}
            className="neo-input px-3 py-2 text-xs text-slate-300 w-auto"
          >
            <option value="All">All Attending Doctors</option>
            <option value="Arvind">Dr. Arvind Mehta (Orthodontics)</option>
            <option value="Priya">Dr. Priya Sharma (Endodontics)</option>
            <option value="Vikram">Dr. Vikram Rao (Implantology)</option>
            <option value="Johnson">Dr. Johnson Dev</option>
          </select>
        </div>

        {/* Status Filter Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pt-1">
          {statuses.map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded-xl text-xs font-bold whitespace-nowrap transition ${
                statusFilter === st
                  ? 'neo-btn-primary'
                  : 'neo-btn text-slate-400 hover:text-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Appointments List / Grid Bento */}
      <div className="bento-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Scheduled Appointments ({filteredAppts.length})
          </h2>
          <span className="text-xs text-slate-500">
            {new Date(selectedDate).toLocaleDateString('en-IN', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
          </span>
        </div>

        {isLoading ? (
          <div className="neo-inset p-12 text-center text-slate-400">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-cyan-400 mb-2" />
            Loading chair schedule...
          </div>
        ) : filteredAppts.length === 0 ? (
          <div className="neo-inset p-12 text-center text-slate-400 space-y-2">
            <Calendar className="w-8 h-8 mx-auto text-slate-600" />
            <p className="text-xs font-bold text-slate-300">No appointments found for this filter.</p>
            <p className="text-[11px] text-slate-500">Click Book Patient Slot to schedule a treatment.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredAppts.map((appt) => {
              const start = appt.start_at ? new Date(appt.start_at) : new Date();
              const timeStr = start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

              return (
                <div
                  key={appt.id}
                  className="neo-card p-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="flex items-start md:items-center gap-3.5 min-w-0">
                    <div className="w-14 h-14 rounded-2xl neo-inset flex flex-col items-center justify-center text-cyan-400 flex-shrink-0">
                      <Clock className="w-4 h-4 mb-0.5" />
                      <span className="text-[11px] font-black">{timeStr}</span>
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          onClick={() => {
                            if (appt.contact) {
                              setSelectedPatient(appt.contact);
                              setIsProfileOpen(true);
                            }
                          }}
                          className="font-bold text-sm text-slate-100 hover:text-cyan-400 cursor-pointer transition-colors"
                        >
                          {appt.contact?.name || appt.title || 'Patient Appointment'}
                        </span>
                        <span className="neo-pill text-[10px] text-cyan-400 bg-cyan-500/10 border-cyan-500/20">
                          Chair {appt.location || 'Operatory 1'}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {appt.description || 'Routine Checkup & Scaling'}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5 text-[11px] text-slate-500">
                        <span className="flex items-center gap-1">
                          <Stethoscope className="w-3.5 h-3.5 text-cyan-400" />
                          {appt.assigned_user_name || 'Dr. Arvind Mehta'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions & Status Dropdown */}
                  <div className="flex items-center gap-2.5 flex-wrap flex-shrink-0 self-end md:self-center">
                    <select
                      value={appt.status || 'Booked'}
                      onChange={(e) => handleUpdateStatus(appt.id, e.target.value)}
                      className={`neo-input py-1 px-2.5 text-xs font-bold w-auto cursor-pointer ${
                        appt.status === 'Completed' ? 'text-emerald-400' :
                        appt.status === 'In Treatment' ? 'text-blue-400' :
                        appt.status === 'Arrived' ? 'text-purple-400' : 'text-amber-400'
                      }`}
                    >
                      <option value="Booked">Booked</option>
                      <option value="Confirmed">Confirmed</option>
                      <option value="Arrived">Arrived</option>
                      <option value="In Treatment">In Treatment</option>
                      <option value="Completed">Completed</option>
                      <option value="Cancelled">Cancelled</option>
                    </select>

                    <button
                      onClick={() => {
                        if (appt.contact) {
                          setSelectedPatient(appt.contact);
                          setIsProfileOpen(true);
                        }
                      }}
                      className="neo-btn p-2 text-slate-300 hover:text-white"
                      title="View Patient Chart"
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Patient Profile Modal */}
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

      {/* Book Appointment Modal */}
      <BookAppointmentModal
        isOpen={isBookOpen}
        onClose={() => setIsBookOpen(false)}
        onSuccess={() => {
          setIsBookOpen(false);
          fetchAppointments();
        }}
        initialPatient={selectedPatient}
      />
    </div>
  );
};

export default AppointmentsPage;
