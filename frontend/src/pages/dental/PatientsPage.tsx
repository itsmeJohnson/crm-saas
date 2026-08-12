import React, { useState, useEffect } from 'react';
import {
  Users, Search, Phone, Mail, Stethoscope, RefreshCw, UserPlus, Eye, Plus
} from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { api } from '../../services/api';
import { PatientProfileModal } from '../../components/dental/PatientProfileModal';
import { BookAppointmentModal } from '../../components/dental/BookAppointmentModal';
import { RegisterPatientModal } from '../../components/dental/RegisterPatientModal';

export const PatientsPage: React.FC = () => {
  const [patients, setPatients] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [selectedDoctor, setSelectedDoctor] = useState('All');
  const [isLoading, setIsLoading] = useState(true);
  
  // Modals
  const [selectedPatient, setSelectedPatient] = useState<any | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isBookOpen, setIsBookOpen] = useState(false);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);

  const [doctors, setDoctors] = useState<any[]>([]);

  useEffect(() => {
    fetchPatients();
    fetchDoctors();
  }, []);

  const fetchPatients = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/contacts/?limit=100');
      const list = res.data?.items || res.data || [];
      setPatients(list);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDoctors = async () => {
    try {
      const res = await api.get('/users/?limit=100');
      const users = res.data || [];
      const docs = users.filter((u: any) => /doctor|dentist|surgeon/i.test(`${u.role || ''} ${u.custom_role_name || ''}`));
      setDoctors((docs.length > 0 ? docs : users).map((u: any) => `${u.first_name || ''} ${u.last_name || ''}`.trim()).filter(Boolean));
    } catch { /* non-fatal */ }
  };

  const filteredPatients = patients.filter((p) => {
    const cf = p.custom_fields || {};
    const fullName = `${p.first_name} ${p.last_name}`.toLowerCase();
    const phone = (p.phone || '').toLowerCase();
    const email = (p.email || '').toLowerCase();
    const matchesSearch = fullName.includes(search.toLowerCase()) || phone.includes(search.toLowerCase()) || email.includes(search.toLowerCase());

    const cat = cf.patient_category || p.tags?.[0] || 'Active Patient';
    const matchesCat = selectedCategory === 'All' || cat === selectedCategory;

    const doc = cf.primary_doctor || 'All';
    const matchesDoc = selectedDoctor === 'All' || doc.includes(selectedDoctor);

    return matchesSearch && matchesCat && matchesDoc;
  });

  const categories = ['All', 'Active Treatment', 'New Patient', 'Returning Patient', 'Treatment Completed', 'Recall Due', 'Follow-up Due'];

  return (
    <div className="space-y-6 select-none">
      {/* Header Bento */}
      <div className="bento-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-400 to-emerald-500 flex items-center justify-center text-white shadow-lg shadow-cyan-500/25 flex-shrink-0">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-100">
              Patient Records &amp; Directory
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Complete dental patient roster, clinical histories, active treatment plans &amp; recall schedules.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsRegisterOpen(true)}
            className="neo-btn-primary px-4 py-2.5 text-xs flex items-center gap-2"
          >
            <UserPlus className="w-4 h-4" />
            Register Patient
          </button>
        </div>
      </div>

      {/* Filters Bar Bento */}
      <div className="bento-card p-5 space-y-4">
        {/* Search input — its own full-width bar */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by patient name, phone number or email..."
            className="neo-input w-full pr-4 py-2.5 text-xs"
            style={{ paddingLeft: '2.4rem' }}
          />
        </div>

        {/* Doctor Filter */}
        <div className="flex items-center gap-2">
          <select
            value={selectedDoctor}
            onChange={(e) => setSelectedDoctor(e.target.value)}
            className="neo-input px-3.5 py-2.5 text-xs w-full sm:w-auto"
          >
            <option value="All">All Attending Doctors</option>
            {doctors.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pt-1 pb-1">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setSelectedCategory(c)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition cursor-pointer ${
                selectedCategory === c
                  ? 'neo-btn-primary'
                  : 'neo-btn text-slate-400 hover:text-slate-200'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Patient Directory Table Bento */}
      <div className="bento-card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-[var(--bg-inset)] border-b border-slate-800/40 text-slate-400 uppercase tracking-wider font-bold text-[10px]">
                <th className="px-6 py-4">Patient Name &amp; Demographics</th>
                <th className="px-4 py-4">Contact Info</th>
                <th className="px-4 py-4">Attending Doctor</th>
                <th className="px-4 py-4">Current Treatment</th>
                <th className="px-4 py-4">Last Visit / Next Appt</th>
                <th className="px-4 py-4">Outstanding</th>
                <th className="px-4 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/30">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto text-cyan-400 mb-2" />
                    Loading clinical patient records...
                  </td>
                </tr>
              ) : filteredPatients.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    No matching patients found.
                  </td>
                </tr>
              ) : (
                filteredPatients.map((patient) => {
                  const cf = patient.custom_fields || {};
                  const age = cf.age || '32';
                  const gender = cf.gender || 'Male';
                  const bloodGroup = cf.blood_group || 'O+';
                  const allergies = cf.allergies;
                  const treatment = cf.current_treatment || 'Routine Dental Checkup';
                  const doctor = cf.primary_doctor || cf.consultant_name || 'Unassigned';
                  const category = cf.patient_category || patient.tags?.[0] || 'Active Treatment';
                  const balance = cf.outstanding_balance ?? 0;
                  const lastVisit = cf.last_visit_date ? new Date(cf.last_visit_date).toLocaleDateString('en-IN') : '12 Jul 2026';
                  const nextAppt = cf.next_appointment_date ? new Date(cf.next_appointment_date).toLocaleDateString('en-IN') : 'Pending';

                  return (
                    <tr
                      key={patient.id}
                      className="hover:bg-[var(--bg-card-hover)] transition-colors group cursor-pointer"
                      onClick={() => {
                        setSelectedPatient(patient);
                        setIsProfileOpen(true);
                      }}
                    >
                      {/* Name & Demographics */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500/20 to-indigo-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-black text-xs flex-shrink-0">
                            {patient.first_name?.[0] || 'P'}
                          </div>
                          <div>
                            <span className="font-bold text-slate-100 group-hover:text-cyan-400 transition-colors block">
                              {patient.first_name} {patient.last_name}
                            </span>
                            <div className="flex items-center gap-1.5 mt-0.5 text-[10px] text-slate-400">
                              <span>{age} yrs, {gender}</span>
                              <span>•</span>
                              <span className="neo-pill text-[9px] py-0 px-1.5 font-bold text-rose-400">
                                {bloodGroup}
                              </span>
                              {allergies && allergies !== 'None' && (
                                <span className="neo-pill text-[9px] py-0 px-1.5 font-bold text-amber-400">
                                  {allergies}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Contact Info */}
                      <td className="px-4 py-4">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1 text-slate-300 font-medium">
                            <Phone className="w-3 h-3 text-cyan-400" />
                            <span>{patient.phone || 'N/A'}</span>
                          </div>
                          {patient.email && (
                            <div className="flex items-center gap-1 text-slate-500 text-[10px]">
                              <Mail className="w-3 h-3" />
                              <span className="truncate max-w-[140px]">{patient.email}</span>
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Doctor */}
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-1.5 text-slate-300 font-medium">
                          <Stethoscope className="w-3.5 h-3.5 text-cyan-400" />
                          <span className="truncate">{doctor}</span>
                        </div>
                      </td>

                      {/* Treatment */}
                      <td className="px-4 py-4">
                        <span className="font-bold text-slate-200 block truncate max-w-[180px]">
                          {treatment}
                        </span>
                      </td>

                      {/* Last / Next Visit */}
                      <td className="px-4 py-4">
                        <div className="space-y-0.5">
                          <div className="text-slate-400">
                            Last: <span className="text-slate-200 font-medium">{lastVisit}</span>
                          </div>
                          <div className="text-[10px] text-cyan-400">
                            Next: <span className="font-medium">{nextAppt}</span>
                          </div>
                        </div>
                      </td>

                      {/* Balance */}
                      <td className="px-4 py-4">
                        {balance > 0 ? (
                          <span className="neo-pill text-rose-400 bg-rose-500/10 border-rose-500/20 font-bold">
                            {formatMoney(balance)}
                          </span>
                        ) : (
                          <span className="neo-pill text-emerald-400 bg-emerald-500/10 border-emerald-500/20 font-bold">
                            Paid
                          </span>
                        )}
                      </td>

                      {/* Status / Category */}
                      <td className="px-4 py-4">
                        <span className={`neo-pill text-[10px] ${
                          category.includes('Active')
                            ? 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20'
                            : category.includes('Recall')
                            ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
                            : category.includes('New')
                            ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                            : 'text-slate-400'
                        }`}>
                          {category}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => {
                              setSelectedPatient(patient);
                              setIsBookOpen(true);
                            }}
                            className="neo-btn p-1.5 text-cyan-400 hover:text-cyan-300"
                            title="Book Appointment"
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => {
                              setSelectedPatient(patient);
                              setIsProfileOpen(true);
                            }}
                            className="neo-btn p-1.5 text-slate-300 hover:text-white"
                            title="Open 360° Patient Chart"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
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

      {/* Register / Walk-In Modal */}
      <RegisterPatientModal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        onSuccess={() => {
          setIsRegisterOpen(false);
          fetchPatients();
        }}
      />

      {/* Book Appointment Modal */}
      <BookAppointmentModal
        isOpen={isBookOpen}
        onClose={() => setIsBookOpen(false)}
        onSuccess={() => {
          setIsBookOpen(false);
          fetchPatients();
        }}
        initialPatient={selectedPatient}
      />
    </div>
  );
};

export default PatientsPage;
