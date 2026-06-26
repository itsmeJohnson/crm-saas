import React, { useEffect, useState } from 'react';
import { UserFilters } from '../components/users/UserFilters';
import { UserTable } from '../components/users/UserTable';
import { Pagination } from '../components/users/Pagination';
import { InviteModal } from '../components/users/InviteModal';
import { EditUserModal } from '../components/users/EditUserModal';
import { CreateMemberModal } from '../components/users/CreateMemberModal';
import { useUserStore } from '../store/userStore';
import { useAuthStore } from '../store/authStore';
import { UserPlus, Mail, Calendar, ShieldAlert, Users, ShieldCheck } from 'lucide-react';
import { UserResponse, userApi } from '../services/userApi';

export const UsersPage: React.FC = () => {
  const { fetchUsers, fetchInvitations, invitations } = useUserStore();
  const currentUser = useAuthStore((state) => state.user);

  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);
  const [seatUtil, setSeatUtil] = useState<{ licensed_seats: number; active_users: number; available_new_seats: number } | null>(null);

  useEffect(() => {
    fetchUsers();
    if (currentUser && (currentUser.role === 'OrgAdmin' || currentUser.role === 'Manager')) {
      fetchInvitations();
      userApi.getSeatUtilization().then(setSeatUtil).catch(() => {});
    }
  }, [fetchUsers, fetchInvitations, currentUser]);

  const handleEditClick = (user: UserResponse) => {
    setSelectedUser(user);
    setIsEditOpen(true);
  };

  const showInviteButton = currentUser?.role === 'OrgAdmin' || currentUser?.role === 'Manager';
  const showCreateButton = currentUser?.role === 'OrgAdmin' ||
                           currentUser?.role === 'Manager' ||
                           (currentUser?.role === 'Employee' && currentUser?.is_team_leader);
  const showInvitationsPanel = currentUser?.role === 'OrgAdmin' || currentUser?.role === 'Manager';

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
            User Management
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Manage your organization's team members, roles, status, and pending invitations.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {showCreateButton && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="flex items-center justify-center gap-2 px-5 py-3 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50 text-white rounded-xl text-sm font-semibold transition-all cursor-pointer"
            >
              <UserPlus className="w-4 h-4 text-brand-400" />
              Create Member
            </button>
          )}

          {showInviteButton && (
            <button
              onClick={() => setIsInviteOpen(true)}
              className="flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 active:from-brand-700 active:to-indigo-700 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer"
            >
              <Mail className="w-4 h-4" />
              Invite Member
            </button>
          )}
        </div>
      </div>

      {/* Seat Utilization Banner */}
      {seatUtil && (
        <div className="grid grid-cols-3 gap-4">
          <div className="glass-panel border border-slate-800/80 rounded-xl px-5 py-4 flex items-center gap-3">
            <ShieldCheck className="w-5 h-5 text-brand-400 shrink-0" />
            <div>
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Licensed Seats</p>
              <p className="text-xl font-bold text-slate-100">{seatUtil.licensed_seats}</p>
            </div>
          </div>
          <div className="glass-panel border border-slate-800/80 rounded-xl px-5 py-4 flex items-center gap-3">
            <Users className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Occupied Seats</p>
              <p className="text-xl font-bold text-slate-100">{seatUtil.active_users}</p>
            </div>
          </div>
          <div className="glass-panel border border-slate-800/80 rounded-xl px-5 py-4 flex items-center gap-3">
            <UserPlus className="w-5 h-5 text-indigo-400 shrink-0" />
            <div>
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Available Seats</p>
              <p className="text-xl font-bold text-slate-100">{seatUtil.available_new_seats}</p>
            </div>
          </div>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
        {/* Left Side: Table & Filters */}
        <div className="xl:col-span-2 space-y-4">
          <UserFilters />
          <UserTable onEditClick={handleEditClick} />
          <Pagination />
        </div>

        {/* Right Side: Invitations Panel */}
        {showInvitationsPanel && (
          <div className="glass-panel border border-slate-800/80 rounded-2xl p-6 space-y-4">
            <div>
              <h3 className="text-md font-semibold text-slate-200 flex items-center gap-2">
                <Mail className="w-4 h-4 text-brand-400" />
                Pending Invitations
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Active invitation links waiting to be accepted.
              </p>
            </div>

            <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
              {invitations.length === 0 ? (
                <div className="p-8 border border-dashed border-slate-800 rounded-xl flex flex-col items-center justify-center text-slate-500 text-center">
                  <Mail className="w-6 h-6 mb-2.5 text-slate-600" />
                  <p className="text-xs">No pending invitations.</p>
                </div>
              ) : (
                invitations.map((invite) => {
                  const isExpired = new Date(invite.expires_at) < new Date();
                  return (
                    <div
                      key={invite.id}
                      className="p-3.5 bg-slate-900/40 border border-slate-800/90 rounded-xl space-y-2.5 hover:border-slate-800 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2 overflow-hidden">
                        <div className="overflow-hidden">
                          <p className="text-xs font-semibold text-slate-300 truncate" title={invite.email}>
                            {invite.email}
                          </p>
                          <span className="inline-block mt-1 px-2 py-0.5 text-[9px] font-bold bg-slate-800 text-slate-400 border border-slate-700/80 rounded">
                            {invite.role}
                          </span>
                        </div>
                        {isExpired && (
                          <span className="flex items-center gap-1 text-[10px] font-semibold text-amber-500 shrink-0">
                            <ShieldAlert className="w-3.5 h-3.5" />
                            Expired
                          </span>
                        )}
                      </div>

                      <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1.5 border-t border-slate-800/50">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" />
                          Expires {new Date(invite.expires_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>

      {/* Invite Modal */}
      <InviteModal isOpen={isInviteOpen} onClose={() => setIsInviteOpen(false)} />

      {/* Create Member Modal */}
      <CreateMemberModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />

      {/* Edit User Modal */}
      <EditUserModal
        isOpen={isEditOpen}
        user={selectedUser}
        onClose={() => {
          setIsEditOpen(false);
          setSelectedUser(null);
        }}
      />
    </div>
  );
};
