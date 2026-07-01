import React, { useState, useEffect } from 'react';
import { userApi, UserResponse, SeatUtilizationResponse, SeatHistoryResponse } from '../../services/userApi';
import { extractErrorMessage } from '../../utils/errors';
import {
  Users, UserPlus, Search, ShieldAlert, Loader2, CheckCircle2,
  AlertTriangle, ToggleLeft, ToggleRight, RefreshCw, History,
  UserCheck, ShieldCheck, UserMinus, HelpCircle
} from 'lucide-react';

export const PortalUsers: React.FC = () => {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [seatUtilization, setSeatUtilization] = useState<SeatUtilizationResponse | null>(null);
  const [seatHistory, setSeatHistory] = useState<SeatHistoryResponse[]>([]);
  const [inactiveEmployees, setInactiveEmployees] = useState<UserResponse[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Tab: 'users' | 'inactive' | 'history'
  const [activeTab, setActiveTab] = useState<'users' | 'inactive' | 'history'>('users');

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');

  // Add User Form Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    phone: '',
    role: 'Employee',
    reporting_to_id: '',
    password: 'Password123'
  });

  // Deactivate Reason Modal
  const [deactivateTarget, setDeactivateTarget] = useState<UserResponse | null>(null);
  const [deactivateReason, setDeactivateReason] = useState('Resigned');

  // Replace Employee Modal
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [replaceTarget, setReplaceTarget] = useState<UserResponse | null>(null);
  const [replaceFormData, setReplaceFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    phone: '',
    role: 'Employee',
    reporting_to_id: '',
    password: 'Password123'
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const userList = await userApi.getUsers({});
      const seatUtil = await userApi.getSeatUtilization();
      const historyList = await userApi.getSeatHistory();
      const inactiveList = await userApi.getInactiveEmployees();

      setUsers(userList);
      setSeatUtilization(seatUtil);
      setSeatHistory(historyList);
      setInactiveEmployees(inactiveList);
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to load seat licensing and user data."));
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStatus = async (user: UserResponse) => {
    if (user.is_active) {
      // Open deactivation modal to select reason
      setDeactivateReason('Resigned');
      setDeactivateTarget(user);
    } else {
      // Direct activation
      try {
        setError(null);
        setSuccess(null);
        await userApi.toggleUserStatus(user.id, true);
        setSuccess(`User account activated successfully! A new seat has been assigned.`);
        fetchData();
      } catch (err: any) {
        setError(extractErrorMessage(err, "Failed to activate user account. Please check seat limits."));
      }
    }
  };

  const confirmDeactivation = async () => {
    if (!deactivateTarget) return;
    try {
      setError(null);
      setSuccess(null);
      await userApi.toggleUserStatus(deactivateTarget.id, false, deactivateReason);
      setSuccess(`User account deactivated successfully (Reason: ${deactivateReason}). Seat remains occupied until billing cycle ends or replaced.`);
      setDeactivateTarget(null);
      fetchData();
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to deactivate user."));
    }
  };

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!seatUtilization) return;

    if (seatUtilization.available_new_seats <= 0) {
      setError("No new seats available. Please purchase additional seats or use the Replace Employee functionality.");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      setSuccess(null);

      await userApi.createUser({
        ...formData,
        reporting_to_id: formData.reporting_to_id || null,
      });

      setSuccess(`User invited successfully. A new seat has been allocated.`);
      setShowAddModal(false);
      setFormData({
        email: '',
        first_name: '',
        last_name: '',
        phone: '',
        role: 'Employee',
        reporting_to_id: '',
        password: 'Password123'
      });
      fetchData();
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to add user seat."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReplaceEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replaceTarget) return;

    try {
      setSubmitting(true);
      setError(null);
      setSuccess(null);

      await userApi.replaceEmployee({
        old_user_id: replaceTarget.id,
        first_name: replaceFormData.first_name,
        last_name: replaceFormData.last_name,
        email: replaceFormData.email,
        phone: replaceFormData.phone || undefined,
        role: replaceFormData.role,
        reporting_to_id: replaceFormData.reporting_to_id || null,
        password: replaceFormData.password
      });

      setSuccess("Employee replaced successfully! Seat transferred successfully with no additional billing applied.");
      setShowReplaceModal(false);
      setReplaceTarget(null);
      setReplaceFormData({
        email: '',
        first_name: '',
        last_name: '',
        phone: '',
        role: 'Employee',
        reporting_to_id: '',
        password: 'Password123'
      });
      fetchData();
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to replace employee."));
    } finally {
      setSubmitting(false);
    }
  };

  const filteredUsers = users.filter((u) => {
    const matchesSearch = u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          (u.first_name && u.first_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
                          (u.last_name && u.last_name.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesRole = roleFilter === 'all' || u.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  const potentialManagers = users.filter(u => u.is_active && (u.role === 'Manager' || u.role === 'OrgAdmin' || u.is_team_leader));

  if (loading && users.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8 text-left max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
            Enterprise Seat Licensing & Users
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Manage organization seats, perform employee replacements without additional billing, and monitor seat utilization logs.
          </p>
        </div>
        
        <div className="flex gap-3">
          <button
            onClick={fetchData}
            className="p-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-400 hover:text-slate-200 rounded-xl transition-all cursor-pointer"
            title="Refresh Data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          
          {seatUtilization && seatUtilization.available_new_seats > 0 ? (
            <button
              onClick={() => {
                setError(null);
                setSuccess(null);
                setShowAddModal(true);
              }}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
            >
              <UserPlus className="w-3.5 h-3.5" />
              Allocate New Seat
            </button>
          ) : (
            <button
              onClick={() => {
                setError(null);
                setSuccess(null);
                setActiveTab('inactive');
              }}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-slate-900 border border-amber-500/30 text-amber-400 hover:bg-slate-850 rounded-xl text-xs font-bold transition-all cursor-pointer"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              Replace Employee (Seats Full)
            </button>
          )}
        </div>
      </div>

      {success && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {success}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Seat Licensing Statistics Grid */}
      {seatUtilization && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="glass-panel border border-slate-900 rounded-2xl p-5 space-y-1">
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Licensed Seats</span>
            <p className="text-2xl font-black text-slate-200">{seatUtilization.licensed_seats}</p>
            <span className="text-[9px] text-slate-600 block">Growth Subscription</span>
          </div>
          <div className="glass-panel border border-slate-900 rounded-2xl p-5 space-y-1">
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Active Users</span>
            <p className="text-2xl font-black text-emerald-400">{seatUtilization.active_users}</p>
            <span className="text-[9px] text-slate-600 block">Occupying & logging in</span>
          </div>
          <div className="glass-panel border border-slate-900 rounded-2xl p-5 space-y-1">
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Inactive Seats</span>
            <p className="text-2xl font-black text-rose-400">{seatUtilization.inactive_assigned_seats}</p>
            <span className="text-[9px] text-slate-600 block">Seats occupied temporarily</span>
          </div>
          <div className="glass-panel border border-slate-900 rounded-2xl p-5 space-y-1">
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Available Seats</span>
            <p className="text-2xl font-black text-brand-400">{seatUtilization.available_new_seats}</p>
            <span className="text-[9px] text-slate-600 block">Ready to allocate</span>
          </div>
          <div className="glass-panel border border-slate-900 rounded-2xl p-5 space-y-1 col-span-2 md:col-span-1">
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Replace Available</span>
            <p className="text-2xl font-black text-amber-400">{seatUtilization.replace_employee_available}</p>
            <span className="text-[9px] text-slate-600 block">Can replace now</span>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-900 gap-6">
        <button
          onClick={() => setActiveTab('users')}
          className={`pb-3 text-xs font-bold flex items-center gap-1.5 transition-all relative cursor-pointer ${
            activeTab === 'users' ? 'text-brand-400' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          <Users className="w-4 h-4" />
          Active Workspace ({filteredUsers.filter(u => u.is_active).length})
          {activeTab === 'users' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-500 rounded-full" />}
        </button>

        <button
          onClick={() => setActiveTab('inactive')}
          className={`pb-3 text-xs font-bold flex items-center gap-1.5 transition-all relative cursor-pointer ${
            activeTab === 'inactive' ? 'text-amber-400' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          <UserMinus className="w-4 h-4" />
          Inactive Employees ({inactiveEmployees.length})
          {inactiveEmployees.length > 0 && (
            <span className="px-1.5 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[9px] font-extrabold rounded-full">
              {inactiveEmployees.length} Reassignable
            </span>
          )}
          {activeTab === 'inactive' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-amber-500 rounded-full" />}
        </button>

        <button
          onClick={() => setActiveTab('history')}
          className={`pb-3 text-xs font-bold flex items-center gap-1.5 transition-all relative cursor-pointer ${
            activeTab === 'history' ? 'text-indigo-400' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          <History className="w-4 h-4" />
          Seat Utilization Logs
          {activeTab === 'history' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500 rounded-full" />}
        </button>
      </div>

      {/* Tab: Users */}
      {activeTab === 'users' && (
        <div className="space-y-6">
          {/* Search and Filters */}
          <div className="flex flex-col sm:flex-row gap-4 justify-between items-stretch">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search active users by name or email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
              />
            </div>

            <div className="bg-slate-900/60 border border-slate-800 p-1 rounded-xl flex gap-1 items-center">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider px-2">Role</span>
              {['all', 'OrgAdmin', 'Manager', 'Employee'].map((role) => (
                <button
                  key={role}
                  onClick={() => setRoleFilter(role)}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-bold capitalize transition-all cursor-pointer ${
                    roleFilter === role
                      ? 'bg-brand-500 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {role === 'all' ? 'All Roles' : role}
                </button>
              ))}
            </div>
          </div>

          {/* Grid list */}
          <div className="glass-panel border border-slate-900 rounded-2xl overflow-hidden">
            {filteredUsers.length === 0 ? (
              <p className="p-8 text-slate-500 text-xs text-center">No active users matching filters.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="bg-slate-950/40 text-slate-500 border-b border-slate-900 uppercase font-bold">
                      <th className="p-4">Employee</th>
                      <th className="p-4">Seat Number</th>
                      <th className="p-4">Email</th>
                      <th className="p-4">Assigned Role</th>
                      <th className="p-4">Created Date</th>
                      <th className="p-4 text-center">Status</th>
                      <th className="p-4 text-center">Access Switch</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.map((u) => (
                      <tr key={u.id} className="border-b border-slate-900 hover:bg-slate-900/10 text-slate-300">
                        <td className="p-4 font-semibold text-slate-200">
                          {u.first_name || u.last_name ? `${u.first_name || ''} ${u.last_name || ''}`.trim() : 'Invited Member'}
                        </td>
                        <td className="p-4">
                          <span className={`px-2 py-0.5 text-[9px] font-mono font-bold rounded ${
                            u.seat_number ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-slate-900 text-slate-600 border border-slate-800'
                          }`}>
                            {u.seat_number || 'No Seat'}
                          </span>
                        </td>
                        <td className="p-4 font-mono text-slate-400">{u.email}</td>
                        <td className="p-4">
                          <span className={`px-2 py-0.5 text-[9px] font-bold rounded uppercase border ${
                            u.role === 'OrgAdmin'
                              ? 'bg-brand-500/10 text-brand-400 border-brand-500/20'
                              : u.role === 'Manager'
                              ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'
                              : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          }`}>
                            {u.role}
                          </span>
                        </td>
                        <td className="p-4 text-slate-500">
                          {new Date(u.created_at).toLocaleDateString()}
                        </td>
                        <td className="p-4 text-center">
                          <span className={`px-2 py-0.5 text-[9px] font-bold rounded uppercase border ${
                            u.is_active
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}>
                            {u.is_active ? 'Active' : 'Inactive'}
                          </span>
                          {u.inactive_reason && (
                            <span className="block text-[8px] text-slate-500 mt-0.5 font-semibold">({u.inactive_reason})</span>
                          )}
                        </td>
                        <td className="p-4 flex justify-center items-center">
                          <button
                            onClick={() => handleToggleStatus(u)}
                            className="p-1 text-slate-500 hover:text-slate-300 transition-all cursor-pointer"
                            title={u.is_active ? "Suspend User" : "Activate User"}
                          >
                            {u.is_active ? (
                              <ToggleRight className="w-6 h-6 text-emerald-400" />
                            ) : (
                              <ToggleLeft className="w-6 h-6 text-slate-600" />
                            )}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Inactive Employees */}
      {activeTab === 'inactive' && (
        <div className="space-y-6 text-left">
          <div className="glass-panel border border-slate-900 rounded-2xl p-5 bg-amber-500/5 border-amber-500/10 flex items-start gap-3">
            <HelpCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wide">Replace Employee Policy</h4>
              <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                When employees are marked deactivated, they continue occupying their licensed seat until replaced or deleted. 
                Using <strong>Replace Employee</strong> releases the seat from the inactive employee and transfers it to the new hire immediately <strong>with no additional billing applied</strong>.
              </p>
            </div>
          </div>

          <div className="glass-panel border border-slate-900 rounded-2xl overflow-hidden">
            {inactiveEmployees.length === 0 ? (
              <p className="p-8 text-slate-500 text-xs text-center">No inactive employees currently occupy a seat.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="bg-slate-950/40 text-slate-500 border-b border-slate-900 uppercase font-bold">
                      <th className="p-4">Name</th>
                      <th className="p-4">Email</th>
                      <th className="p-4">Assigned Seat</th>
                      <th className="p-4">Inactivity Reason</th>
                      <th className="p-4">Deactivation Date</th>
                      <th className="p-4 text-center">Replace Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inactiveEmployees.map((u) => (
                      <tr key={u.id} className="border-b border-slate-900 hover:bg-slate-900/10 text-slate-300">
                        <td className="p-4 font-semibold text-slate-200">
                          {u.first_name} {u.last_name}
                        </td>
                        <td className="p-4 font-mono text-slate-400">{u.email}</td>
                        <td className="p-4">
                          <span className="px-2 py-0.5 text-[9px] font-mono font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded">
                            {u.seat_number}
                          </span>
                        </td>
                        <td className="p-4">
                          <span className="px-2 py-0.5 text-[9px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded capitalize">
                            {u.inactive_reason || 'Resigned'}
                          </span>
                        </td>
                        <td className="p-4 text-slate-500">
                          {new Date(u.updated_at).toLocaleDateString()}
                        </td>
                        <td className="p-4 text-center">
                          <button
                            onClick={() => {
                              setError(null);
                              setSuccess(null);
                              setReplaceTarget(u);
                              setShowReplaceModal(true);
                            }}
                            className="inline-flex items-center gap-1 px-3 py-1.5 bg-gradient-to-tr from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-lg text-[10px] font-bold cursor-pointer transition-all shadow shadow-amber-500/10"
                          >
                            <UserCheck className="w-3 h-3" />
                            Replace Employee
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Seat History */}
      {activeTab === 'history' && (
        <div className="glass-panel border border-slate-900 rounded-2xl overflow-hidden">
          {seatHistory.length === 0 ? (
            <p className="p-8 text-slate-500 text-xs text-center">No seat assignment history logs recorded.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="bg-slate-950/40 text-slate-500 border-b border-slate-900 uppercase font-bold">
                    <th className="p-4">Seat Number</th>
                    <th className="p-4">User</th>
                    <th className="p-4">Action</th>
                    <th className="p-4">Performed By</th>
                    <th className="p-4">Date & Time</th>
                    <th className="p-4">Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {seatHistory.map((log) => (
                    <tr key={log.id} className="border-b border-slate-900 hover:bg-slate-900/10 text-slate-300">
                      <td className="p-4 font-mono font-semibold text-slate-200">
                        {log.seat_number}
                      </td>
                      <td className="p-4 font-semibold text-slate-300">
                        {log.user_name || 'System / Replaced'}
                      </td>
                      <td className="p-4">
                        <span className={`px-2 py-0.5 text-[9px] font-bold rounded uppercase border ${
                          log.action === 'Assigned'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : log.action === 'Inactive'
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                        }`}>
                          {log.action}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400">
                        {log.performed_by_name || 'System'}
                      </td>
                      <td className="p-4 text-slate-500">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="p-4 text-slate-400 max-w-xs truncate">
                        {log.remarks}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modal: Deactivate Reason Form */}
      {deactivateTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <div className="glass-panel border border-slate-800 rounded-2xl max-w-sm w-full p-6 space-y-5 bg-slate-950">
            <div>
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                Deactivate User Account
              </h3>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                Provide a deactivation status reason. The user will be unable to log in, but continues to occupy their seat until billing end or employee replacement.
              </p>
            </div>

            <div className="space-y-3">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">Deactivation Reason</label>
              <select
                value={deactivateReason}
                onChange={(e) => setDeactivateReason(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
              >
                <option value="Resigned">Resigned / Left Company</option>
                <option value="Terminated">Terminated / Contract Ended</option>
                <option value="On Leave">On Leave / Extended Absentee</option>
                <option value="Disabled">Disabled / Blocked Access</option>
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDeactivateTarget(null)}
                className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDeactivation}
                className="px-5 py-2 bg-gradient-to-tr from-rose-500 to-red-500 hover:from-rose-600 hover:to-red-600 text-white rounded-xl text-xs font-bold cursor-pointer"
              >
                Deactivate Seat
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Add User Form */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <form
            onSubmit={handleAddUser}
            className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-5 bg-slate-950"
          >
            <div>
              <h3 className="text-lg font-bold text-slate-100">Allocate User Seat</h3>
              <p className="text-xs text-slate-500 mt-1">
                Enter details to add a new calling agent or manager under a new seat.
              </p>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">First Name</label>
                  <input
                    type="text"
                    required
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Last Name</label>
                  <input
                    type="text"
                    required
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Email Address</label>
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Phone Number</label>
                  <input
                    type="tel"
                    inputMode="tel"
                    maxLength={20}
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Access Role</label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  >
                    <option value="Employee">Employee (Telecaller)</option>
                    <option value="Manager">Manager</option>
                    <option value="OrgAdmin">OrgAdmin</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Reporting Manager</label>
                  <select
                    value={formData.reporting_to_id}
                    onChange={(e) => setFormData({ ...formData, reporting_to_id: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  >
                    <option value="">None / Direct</option>
                    {potentialManagers.map(u => (
                      <option key={u.id} value={u.id}>
                        {u.first_name} {u.last_name} ({u.role})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Password</label>
                <input
                  type="text"
                  required
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="flex items-center justify-center gap-1.5 px-6 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold cursor-pointer"
              >
                {submitting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <>
                    <UserPlus className="w-3.5 h-3.5" />
                    Invite User Seat
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Modal: Replace Employee Form */}
      {showReplaceModal && replaceTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <form
            onSubmit={handleReplaceEmployee}
            className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-5 bg-slate-950"
          >
            <div className="pb-3 border-b border-slate-900">
              <span className="px-2 py-0.5 text-[9px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded uppercase">
                Reassigning {replaceTarget.seat_number}
              </span>
              <h3 className="text-base font-bold text-slate-100 mt-2">Replace Employee Workflow</h3>
              <p className="text-[11px] text-slate-500 mt-1">
                Replacing inactive employee <strong>{replaceTarget.first_name} {replaceTarget.last_name}</strong>. Their login will release seat <strong>{replaceTarget.seat_number}</strong> with no billing changes.
              </p>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">First Name</label>
                  <input
                    type="text"
                    required
                    value={replaceFormData.first_name}
                    onChange={(e) => setReplaceFormData({ ...replaceFormData, first_name: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Last Name</label>
                  <input
                    type="text"
                    required
                    value={replaceFormData.last_name}
                    onChange={(e) => setReplaceFormData({ ...replaceFormData, last_name: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Email Address</label>
                  <input
                    type="email"
                    required
                    value={replaceFormData.email}
                    onChange={(e) => setReplaceFormData({ ...replaceFormData, email: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Phone Number</label>
                  <input
                    type="tel"
                    inputMode="tel"
                    maxLength={20}
                    value={replaceFormData.phone}
                    onChange={(e) => setReplaceFormData({ ...replaceFormData, phone: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Access Role</label>
                  <select
                    value={replaceFormData.role}
                    onChange={(e) => setReplaceFormData({ ...replaceFormData, role: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  >
                    <option value="Employee">Employee (Telecaller)</option>
                    <option value="Manager">Manager</option>
                    <option value="OrgAdmin">OrgAdmin</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Reporting Manager</label>
                  <select
                    value={replaceFormData.reporting_to_id}
                    onChange={(e) => setReplaceFormData({ ...replaceFormData, reporting_to_id: e.target.value })}
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                  >
                    <option value="">None / Direct</option>
                    {potentialManagers.map(u => (
                      <option key={u.id} value={u.id}>
                        {u.first_name} {u.last_name} ({u.role})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Password</label>
                <input
                  type="text"
                  required
                  value={replaceFormData.password}
                  onChange={(e) => setReplaceFormData({ ...replaceFormData, password: e.target.value })}
                  className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                />
              </div>
            </div>

            <div className="flex justify-between items-center pt-2">
              <span className="text-[9px] text-emerald-400 flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                No additional billing will be applied
              </span>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowReplaceModal(false);
                    setReplaceTarget(null);
                  }}
                  className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center justify-center gap-1.5 px-6 py-2 bg-gradient-to-tr from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-xl text-xs font-bold cursor-pointer"
                >
                  {submitting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <>
                      <UserCheck className="w-3.5 h-3.5" />
                      Create & Assign Seat
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
