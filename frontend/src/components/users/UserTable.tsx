import React from 'react';
import { Edit3, Trash2, Shield, UserCheck, UserX, Loader2 } from 'lucide-react';
import { useUserStore } from '../../store/userStore';
import { useAuthStore } from '../../store/authStore';
import { UserResponse } from '../../services/userApi';

interface UserTableProps {
  onEditClick: (user: UserResponse) => void;
}

export const UserTable: React.FC<UserTableProps> = ({ onEditClick }) => {
  const { users, isLoading, error, filters, toggleUserStatus, deleteUser } = useUserStore();
  const currentUser = useAuthStore((state) => state.user);

  // Client-side filtering for role and status
  const filteredUsers = users.filter((u) => {
    if (filters.role !== 'All') {
      if (filters.role === 'TeamLeader') {
        if (u.role !== 'Employee' || !u.is_team_leader) {
          return false;
        }
      } else if (filters.role === 'Employee') {
        if (u.role !== 'Employee' || u.is_team_leader) {
          return false;
        }
      } else if (u.role !== filters.role) {
        return false;
      }
    }
    if (filters.status !== 'All') {
      const wantActive = filters.status === 'Active';
      if (u.is_active !== wantActive) {
        return false;
      }
    }
    return true;
  });

  const getRoleBadge = (user: UserResponse) => {
    switch (user.role) {
      case 'OrgAdmin':
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
      case 'Employee':
        if (user.is_team_leader) {
          return (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse">
              Team Leader
            </span>
          );
        }
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            Employee
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

  // RBAC Permission Helpers
  const canEdit = (target: UserResponse) => {
    if (!currentUser) return false;
    if (currentUser.id === target.id) return true; // Can always edit self profile
    if (currentUser.role === 'OrgAdmin') return true; // Admin can edit anyone
    if (currentUser.role === 'Manager' && target.role === 'Employee') return true; // Manager can edit employees
    if (currentUser.role === 'Employee' && currentUser.is_team_leader && target.role === 'Employee' && target.reporting_to_id === currentUser.id) return true; // Team Leader can edit downline employees
    return false;
  };

  const canDeactivate = (target: UserResponse) => {
    if (!currentUser) return false;
    if (currentUser.id === target.id) return false; // Cannot deactivate self
    if (currentUser.role === 'OrgAdmin') return true; // Only admin can toggle status by default, but managers/TLs can toggle their downline
    if (currentUser.role === 'Manager' && target.role === 'Employee') return true;
    if (currentUser.role === 'Employee' && currentUser.is_team_leader && target.role === 'Employee' && target.reporting_to_id === currentUser.id) return true;
    return false;
  };

  const canDelete = (target: UserResponse) => {
    if (!currentUser) return false;
    if (currentUser.id === target.id) return false; // Cannot delete self
    if (currentUser.role === 'OrgAdmin') return true; // Only admin can delete by default, but managers/TLs can delete their downline
    if (currentUser.role === 'Manager' && target.role === 'Employee') return true;
    if (currentUser.role === 'Employee' && currentUser.is_team_leader && target.role === 'Employee' && target.reporting_to_id === currentUser.id) return true;
    return false;
  };

  const handleToggleStatus = async (user: UserResponse) => {
    if (window.confirm(`Are you sure you want to ${user.is_active ? 'deactivate' : 'activate'} this user?`)) {
      try {
        await toggleUserStatus(user.id, !user.is_active);
      } catch (err: any) {
        alert(err.message || 'Operation failed');
      }
    }
  };

  const handleDelete = async (user: UserResponse) => {
    if (window.confirm(`Are you sure you want to delete ${user.first_name || user.email}? This cannot be undone.`)) {
      try {
        await deleteUser(user.id);
      } catch (err: any) {
        alert(err.message || 'Operation failed');
      }
    }
  };

  if (isLoading && filteredUsers.length === 0) {
    return (
      <div className="glass-panel p-16 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
        <p className="text-sm">Loading organization users...</p>
      </div>
    );
  }

  if (error && filteredUsers.length === 0) {
    return (
      <div className="glass-panel p-12 rounded-2xl border border-red-900/30 bg-red-950/10 flex flex-col items-center justify-center text-red-400">
        <p className="font-semibold mb-2">Error Loading Users</p>
        <p className="text-sm text-red-400/80 mb-4">{error}</p>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800/80 bg-slate-900/40">
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">User</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Role</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Status</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/65 bg-slate-950/20">
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-12 text-center text-sm text-slate-500">
                  No users found matching current filters.
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => {
                const initials = `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase() || 'U';
                const isSelf = currentUser?.id === user.id;

                return (
                  <tr key={user.id} className="hover:bg-slate-900/30 transition-colors">
                    {/* User profile details */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/30 flex items-center justify-center font-semibold text-brand-300 text-sm shadow-inner">
                          {initials}
                        </div>
                        <div className="overflow-hidden">
                          <p className="text-sm font-semibold text-slate-200 truncate">
                            {user.first_name} {user.last_name}
                            {isSelf && (
                              <span className="ml-2 text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 bg-brand-500/10 text-brand-400 border border-brand-500/20 rounded">
                                You
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-slate-400 truncate">{user.email}</p>
                        </div>
                      </div>
                    </td>

                    {/* Role */}
                    <td className="px-6 py-4 align-middle">
                      {getRoleBadge(user)}
                    </td>

                    {/* Status */}
                    <td className="px-6 py-4 align-middle">
                      <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                        user.is_active ? 'text-emerald-400' : 'text-slate-500'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          user.is_active ? 'bg-emerald-400' : 'bg-slate-500'
                        }`} />
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="px-6 py-4 text-right align-middle">
                      <div className="flex items-center justify-end gap-2">
                        {/* Toggle Status */}
                        {canDeactivate(user) && (
                          <button
                            onClick={() => handleToggleStatus(user)}
                            title={user.is_active ? 'Deactivate User' : 'Activate User'}
                            className={`p-2 rounded-lg border transition-all cursor-pointer ${
                              user.is_active
                                ? 'border-slate-800 hover:border-amber-500/25 hover:bg-amber-500/10 text-amber-400'
                                : 'border-slate-800 hover:border-emerald-500/25 hover:bg-emerald-500/10 text-emerald-400'
                            }`}
                          >
                            {user.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                          </button>
                        )}

                        {/* Edit Profile */}
                        {canEdit(user) && (
                          <button
                            onClick={() => onEditClick(user)}
                            title="Edit User Details"
                            className="p-2 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-lg text-slate-300 transition-all cursor-pointer"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                        )}

                        {/* Soft Delete */}
                        {canDelete(user) && (
                          <button
                            onClick={() => handleDelete(user)}
                            title="Delete User"
                            className="p-2 border border-slate-800 hover:border-red-500/25 hover:bg-red-500/10 text-red-400 rounded-lg transition-all cursor-pointer"
                          >
                            <Trash2 className="w-4 h-4" />
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
  );
};
