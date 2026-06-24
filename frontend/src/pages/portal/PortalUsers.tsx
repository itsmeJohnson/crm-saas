import React, { useState, useEffect } from 'react';
import { userApi, UserResponse } from '../../services/userApi';
import { portalApi } from '../../services/portalApi';
import {
  Users, UserPlus, Search, Edit2, ShieldAlert,
  Loader2, CheckCircle2, AlertTriangle, ToggleLeft, ToggleRight
} from 'lucide-react';

export const PortalUsers: React.FC = () => {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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
    role: 'Employee',
    password: 'Password123'
  });

  useEffect(() => {
    fetchUsersAndStats();
  }, []);

  const fetchUsersAndStats = async () => {
    try {
      setLoading(true);
      const userList = await userApi.getUsers({});
      const portalStats = await portalApi.getStats();
      setUsers(userList);
      setStats(portalStats);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load user information.");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStatus = async (userId: string, currentStatus: boolean) => {
    try {
      setError(null);
      setSuccess(null);
      await userApi.toggleUserStatus(userId, !currentStatus);
      setSuccess(`User status successfully updated.`);
      fetchUsersAndStats();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to toggle user status.");
    }
  };

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stats) return;

    // Guard: check seats limits
    if (stats.users.current >= stats.users.limit) {
      setError("Cannot add more users. Seat limits reached. Please purchase more seats first.");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      setSuccess(null);

      await userApi.createUser({
        ...formData,
        organization_id: stats.recent_activities?.[0]?.organization_id || '' // Org ID fallback handled by backend JWT token auth
      });

      setSuccess(`Successfully invited user ${formData.email}!`);
      setShowAddModal(false);
      setFormData({
        email: '',
        first_name: '',
        last_name: '',
        role: 'Employee',
        password: 'Password123'
      });
      fetchUsersAndStats();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create user. Please verify input fields.");
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

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  const currentCount = stats?.users?.current || 0;
  const limitCount = stats?.users?.limit || 0;
  const percent = stats?.users?.percent || 0;

  return (
    <div className="space-y-8 text-left max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
            User Workspace Allocations
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Audit calling agent seats, invite team managers, toggle user permissions, and track active count limits.
          </p>
        </div>
        <button
          onClick={() => {
            setError(null);
            setSuccess(null);
            setShowAddModal(true);
          }}
          className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
        >
          <UserPlus className="w-3.5 h-3.5" />
          Invite User Seat
        </button>
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

      {/* Seats Allocation Progress Panel */}
      <div className="glass-panel border border-slate-900 rounded-2xl p-6 text-left space-y-4">
        <div className="flex justify-between items-center text-xs">
          <span className="text-slate-400 font-bold uppercase tracking-wider">Seats Capacity Meter</span>
          <span className="text-slate-300 font-semibold">{currentCount} Active / {limitCount} Seats Limit</span>
        </div>
        <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden">
          <div
            className="bg-gradient-to-r from-brand-500 to-indigo-500 h-full rounded-full transition-all"
            style={{ width: `${Math.min(percent, 100)}%` }}
          ></div>
        </div>
        <div className="flex justify-between items-center text-[10px] text-slate-500 font-medium">
          <span>{percent}% Used</span>
          {currentCount >= limitCount && (
            <span className="text-amber-400 flex items-center gap-1">
              <ShieldAlert className="w-3 h-3" />
              Seats capacity reached. Buy more seats to invite new users.
            </span>
          )}
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-stretch">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search users by name or email..."
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

      {/* User grid table */}
      <div className="glass-panel border border-slate-900 rounded-2xl overflow-hidden">
        {filteredUsers.length === 0 ? (
          <p className="p-8 text-slate-500 text-xs text-center">No workspace users found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="bg-slate-950/40 text-slate-500 border-b border-slate-900 uppercase font-bold">
                  <th className="p-4">User Details</th>
                  <th className="p-4">Email</th>
                  <th className="p-4">Assigned Role</th>
                  <th className="p-4">Created Date</th>
                  <th className="p-4 text-center">Status</th>
                  <th className="p-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="border-b border-slate-900 hover:bg-slate-900/10 text-slate-300">
                    <td className="p-4 font-semibold text-slate-200">
                      {u.first_name || u.last_name ? `${u.first_name || ''} ${u.last_name || ''}`.trim() : 'Invited Member'}
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
                        {u.is_active ? 'Active' : 'Suspended'}
                      </span>
                    </td>
                    <td className="p-4 flex justify-center items-center">
                      <button
                        onClick={() => handleToggleStatus(u.id, u.is_active)}
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

      {/* Add User modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <form
            onSubmit={handleAddUser}
            className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-5 bg-slate-950"
          >
            <div>
              <h3 className="text-lg font-bold text-slate-100 font-sans">Invite Workspace Seat</h3>
              <p className="text-xs text-slate-500 mt-1">
                Enter details to add a new calling agent or manager. Limit verification runs immediately.
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
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Access Role</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                >
                  <option value="Employee">Employee (Telecaller / Agent)</option>
                  <option value="Manager">Manager (Team Coordinator)</option>
                  <option value="OrgAdmin">OrgAdmin (Organization Owner)</option>
                </select>
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
                    Process Invitation
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
