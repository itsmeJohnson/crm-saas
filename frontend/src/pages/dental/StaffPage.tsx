import React, { useState, useEffect } from 'react';
import {
  Users, UserPlus, Mail, RefreshCw, Phone, Shield, Edit3, Trash2,
  Search, Filter
} from 'lucide-react';
import { useUserStore } from '../../store/userStore';
import { useAuthStore } from '../../store/authStore';
import { CreateMemberModal } from '../../components/users/CreateMemberModal';
import { InviteModal } from '../../components/users/InviteModal';
import { EditUserModal } from '../../components/users/EditUserModal';
import { UserResponse } from '../../services/userApi';

export const StaffPage: React.FC = () => {
  const { users, isLoading, fetchUsers, deleteUser } = useUserStore();
  const currentUser = useAuthStore((state) => state.user);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [attendanceFilter, setAttendanceFilter] = useState('ALL');

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const canCreate = currentUser?.role === 'OrgAdmin' ||
                    currentUser?.role === 'SuperAdmin' ||
                    currentUser?.role === 'Manager' ||
                    currentUser?.role === 'TeamLeader' ||
                    (currentUser?.role === 'Employee' && currentUser?.is_team_leader);

  const canInvite = currentUser?.role === 'OrgAdmin' ||
                    currentUser?.role === 'SuperAdmin' ||
                    currentUser?.role === 'Manager';

  // Metrics
  const totalStaff = users.length;
  const presentCount = users.filter((u) => u.is_present_today).length;
  const absentCount = totalStaff - presentCount;
  const leadershipCount = users.filter((u) =>
    u.role === 'OrgAdmin' || u.role === 'SuperAdmin' || u.role === 'Manager' || u.role === 'TeamLeader' || u.is_team_leader
  ).length;

  // Filtered users
  const filteredUsers = users.filter((u) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const name = `${u.first_name || ''} ${u.last_name || ''}`.toLowerCase();
      const email = (u.email || '').toLowerCase();
      const phone = (u.phone || '').toLowerCase();
      if (!name.includes(q) && !email.includes(q) && !phone.includes(q)) return false;
    }

    if (roleFilter !== 'ALL') {
      if (roleFilter === 'TeamLeader') {
        if (u.role !== 'TeamLeader' && !(u.role === 'Employee' && u.is_team_leader)) return false;
      } else if (roleFilter === 'Employee') {
        if (u.role !== 'Employee' || u.is_team_leader) return false;
      } else if (u.role !== roleFilter) {
        return false;
      }
    }

    if (attendanceFilter === 'PRESENT') {
      if (!u.is_present_today) return false;
    } else if (attendanceFilter === 'ABSENT') {
      if (u.is_present_today) return false;
    }

    return true;
  });

  const getRoleBadge = (user: UserResponse) => {
    switch (user.role) {
      case 'OrgAdmin':
      case 'SuperAdmin':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/10 text-red-400 border border-red-500/20">
            <Shield className="w-3 h-3" />
            Admin
          </span>
        );
      case 'Manager':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Manager
          </span>
        );
      case 'TeamLeader':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
            Team Leader
          </span>
        );
      case 'Employee':
        if (user.is_team_leader) {
          return (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
              Team Leader
            </span>
          );
        }
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            Sales Agent
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            {user.role}
          </span>
        );
    }
  };

  const getAttendanceBadge = (user: UserResponse) => {
    if (user.is_present_today) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Present (On Duty)
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800/80 text-slate-400 border border-slate-700/60">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
        Absent / Off Duty
      </span>
    );
  };

  const handleEditClick = (user: UserResponse) => {
    setSelectedUser(user);
    setIsEditOpen(true);
  };

  const handleDeleteUser = async (user: UserResponse) => {
    if (window.confirm(`Are you sure you want to remove ${user.first_name || user.email}?`)) {
      try {
        await deleteUser(user.id);
      } catch (err: any) {
        alert(err.message || 'Failed to remove member');
      }
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-2.5">
            <Users className="w-6 h-6 text-brand-400" />
            Staff & Organization Team
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Manage organization members, managers, team leaders, telecallers and live attendance.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => fetchUsers()}
            title="Refresh Staff"
            className="p-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-brand-400' : ''}`} />
          </button>

          {canCreate && (
            <button
              id="add-member-button"
              onClick={() => setIsCreateOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/80 text-white rounded-xl text-xs sm:text-sm font-semibold transition-all shadow-sm cursor-pointer"
            >
              <UserPlus className="w-4 h-4 text-brand-400" />
              Add Member
            </button>
          )}

          {canInvite && (
            <button
              onClick={() => setIsInviteOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs sm:text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer"
            >
              <Mail className="w-4 h-4" />
              Invite Member
            </button>
          )}
        </div>
      </div>

      {/* KPI Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        <div className="glass-panel p-4 rounded-xl border border-slate-800/80 bg-slate-900/40">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Members</p>
          <p className="text-2xl font-bold text-slate-100 mt-1">{totalStaff}</p>
        </div>

        <div className="glass-panel p-4 rounded-xl border border-emerald-900/30 bg-emerald-950/15">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Present Today</p>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          </div>
          <p className="text-2xl font-bold text-emerald-300 mt-1">{presentCount}</p>
        </div>

        <div className="glass-panel p-4 rounded-xl border border-slate-800/80 bg-slate-900/40">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Absent / Off Duty</p>
          <p className="text-2xl font-bold text-slate-400 mt-1">{absentCount}</p>
        </div>

        <div className="glass-panel p-4 rounded-xl border border-indigo-900/30 bg-indigo-950/15">
          <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">Leadership</p>
          <p className="text-2xl font-bold text-indigo-300 mt-1">{leadershipCount}</p>
        </div>
      </div>

      {/* Search and Filter Controls */}
      <div className="glass-panel p-3.5 sm:p-4 rounded-xl border border-slate-800/80 flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search staff by name, email, or phone..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3.5 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs sm:text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/50"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Roles</option>
              <option value="OrgAdmin">Admins</option>
              <option value="Manager">Managers</option>
              <option value="TeamLeader">Team Leaders</option>
              <option value="Employee">Sales Agents</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-xs">
            <span className="text-slate-400">Attendance:</span>
            <select
              value={attendanceFilter}
              onChange={(e) => setAttendanceFilter(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="ALL">All</option>
              <option value="PRESENT">Present Only</option>
              <option value="ABSENT">Absent Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Mobile Card View (Optimized for phones) */}
      <div className="grid grid-cols-1 gap-3 sm:hidden">
        {filteredUsers.length === 0 ? (
          <div className="glass-panel p-8 rounded-xl border border-slate-800 text-center text-xs text-slate-500">
            No staff members found matching criteria.
          </div>
        ) : (
          filteredUsers.map((u) => {
            const initials = `${u.first_name?.[0] || ''}${u.last_name?.[0] || ''}`.toUpperCase() || 'U';
            return (
              <div key={u.id} className="glass-panel p-4 rounded-xl border border-slate-800 space-y-3 bg-slate-900/60">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/30 flex items-center justify-center font-bold text-brand-300 text-sm">
                      {initials}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-100">
                        {u.first_name} {u.last_name}
                      </p>
                      <p className="text-xs text-slate-400 truncate">{u.email}</p>
                    </div>
                  </div>
                  <div className="shrink-0">{getRoleBadge(u)}</div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
                  <div>{getAttendanceBadge(u)}</div>
                  <span className={`inline-flex items-center gap-1 text-[11px] font-medium ${
                    u.is_active ? 'text-emerald-400' : 'text-slate-500'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {u.phone && (
                  <div className="text-xs text-slate-300 flex items-center justify-between bg-slate-950/40 p-2 rounded-lg">
                    <span className="text-slate-500">Call / Mobile:</span>
                    <a href={`tel:${u.phone}`} className="flex items-center gap-1 text-brand-400 font-mono hover:underline">
                      <Phone className="w-3 h-3" />
                      {u.phone}
                    </a>
                  </div>
                )}

                <div className="flex items-center justify-end gap-2 pt-1 border-t border-slate-800/60">
                  <button
                    onClick={() => handleEditClick(u)}
                    className="p-2 border border-slate-800 hover:border-slate-700 rounded-lg text-slate-300 text-xs flex items-center gap-1"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span>Edit</span>
                  </button>
                  {currentUser?.role === 'OrgAdmin' && (
                    <button
                      onClick={() => handleDeleteUser(u)}
                      className="p-2 border border-slate-800 hover:border-red-500/30 text-red-400 rounded-lg text-xs flex items-center gap-1"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Desktop Table View */}
      <div className="hidden sm:block glass-panel rounded-2xl border border-slate-800/80 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                <th className="px-6 py-4">Staff Member</th>
                <th className="px-4 py-4">Role</th>
                <th className="px-4 py-4">Contact Phone</th>
                <th className="px-4 py-4">Email</th>
                <th className="px-4 py-4">Attendance Today</th>
                <th className="px-4 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-500">
                    No staff members found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const initials = `${u.first_name?.[0] || ''}${u.last_name?.[0] || ''}`.toUpperCase() || 'U';
                  return (
                    <tr key={u.id} className="hover:bg-slate-800/30 transition">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-xl bg-brand-500/15 border border-brand-500/25 flex items-center justify-center text-brand-400 font-bold text-xs">
                            {initials}
                          </div>
                          <div>
                            <span className="font-bold text-slate-100">{u.first_name} {u.last_name}</span>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        {getRoleBadge(u)}
                      </td>
                      <td className="px-4 py-4 text-slate-300 font-mono">
                        {u.phone ? (
                          <a href={`tel:${u.phone}`} className="hover:text-brand-400 flex items-center gap-1">
                            <Phone className="w-3 h-3 text-slate-500" />
                            {u.phone}
                          </a>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-4 text-slate-400">{u.email}</td>
                      <td className="px-4 py-4">
                        {getAttendanceBadge(u)}
                      </td>
                      <td className="px-4 py-4">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                          u.is_active
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            : 'bg-slate-800 text-slate-500 border border-slate-700'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                          {u.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleEditClick(u)}
                            className="p-1.5 border border-slate-800 hover:border-slate-700 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
                            title="Edit Staff Member"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          {currentUser?.role === 'OrgAdmin' && (
                            <button
                              onClick={() => handleDeleteUser(u)}
                              className="p-1.5 border border-slate-800 hover:border-red-500/30 rounded-lg text-slate-400 hover:text-red-400 transition-colors cursor-pointer"
                              title="Remove Staff Member"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
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

      {/* Modals */}
      <CreateMemberModal
        isOpen={isCreateOpen}
        onClose={() => {
          setIsCreateOpen(false);
          fetchUsers();
        }}
      />

      <InviteModal
        isOpen={isInviteOpen}
        onClose={() => {
          setIsInviteOpen(false);
        }}
      />

      {selectedUser && (
        <EditUserModal
          isOpen={isEditOpen}
          user={selectedUser}
          onClose={() => {
            setIsEditOpen(false);
            setSelectedUser(null);
            fetchUsers();
          }}
        />
      )}
    </div>
  );
};
