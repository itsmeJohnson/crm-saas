import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { X, ShieldAlert, Loader2, KeyRound, UserCheck } from 'lucide-react';
import { useUserStore } from '../../store/userStore';
import { useAuthStore } from '../../store/authStore';
import { userApi, UserResponse } from '../../services/userApi';

interface EditUserModalProps {
  user: UserResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

interface EditFormInput {
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  password?: string;
  reporting_to_id: string;
  allowed_ip_whitelist?: string;
  registered_device_uuid?: string;
}

export const EditUserModal: React.FC<EditUserModalProps> = ({ user, isOpen, onClose }) => {
  const { updateUser, isLoading, error } = useUserStore();
  const currentUser = useAuthStore((state) => state.user);

  const [reportingUsers, setReportingUsers] = useState<UserResponse[]>([]);
  const [isFetchingManagers, setIsFetchingManagers] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    clearErrors,
    watch,
    reset,
    formState: { errors },
  } = useForm<EditFormInput>({
    defaultValues: {
      email: '',
      first_name: '',
      last_name: '',
      role: '',
      password: '',
      reporting_to_id: '',
    },
  });

  const watchRole = watch('role');
  const isSelf = currentUser?.id === user?.id;
  const isAgentSelf = isSelf && currentUser?.role !== 'OrgAdmin';

  // Clear reporting_to_id validation error when switching to a role where it is optional
  useEffect(() => {
    if (watchRole !== 'Employee') {
      clearErrors('reporting_to_id');
    }
  }, [watchRole, clearErrors]);

  // Load potential managers when modal opens
  useEffect(() => {
    if (isOpen) {
      const fetchManagers = async () => {
        setIsFetchingManagers(true);
        try {
          const data = await userApi.getUsers({ limit: 500, is_active: true });
          setReportingUsers(data);
        } catch (err) {
          console.error('Failed to load active users for reporting structure:', err);
        } finally {
          setIsFetchingManagers(false);
        }
      };
      fetchManagers();
    }
  }, [isOpen]);

  useEffect(() => {
    if (user) {
      setValue('email', user.email);
      setValue('first_name', user.first_name || '');
      setValue('last_name', user.last_name || '');
      setValue('role', user.role);
      setValue('password', '');
      setValue('reporting_to_id', user.reporting_to_id || '');
      setValue('allowed_ip_whitelist', (user as any).allowed_ip_whitelist || '');
      setValue('registered_device_uuid', (user as any).registered_device_uuid || '');
    }
  }, [user, setValue, isOpen]);

  const onSubmit = async (data: EditFormInput) => {
    if (!user) return;
    try {
      const payload: Parameters<typeof updateUser>[1] = {
        email: data.email,
        first_name: data.first_name || null,
        last_name: data.last_name || null,
        role: user.role,
      };

      // Only allow managerial changes when NOT an agent editing their own profile
      if (!isAgentSelf) {
        payload.role = data.role;
        payload.reporting_to_id = data.reporting_to_id && data.reporting_to_id.trim() !== '' ? data.reporting_to_id : null;
        payload.allowed_ip_whitelist = data.allowed_ip_whitelist && data.allowed_ip_whitelist.trim() !== '' ? data.allowed_ip_whitelist.trim() : null;
        payload.registered_device_uuid = data.registered_device_uuid && data.registered_device_uuid.trim() !== '' ? data.registered_device_uuid.trim() : null;
      } else {
        // Preserving existing reporting structure for agents/self
        payload.reporting_to_id = user.reporting_to_id || null;
      }

      if (data.password && data.password.trim() !== '') {
        payload.password = data.password;
      }
      await updateUser(user.id, payload);
      reset();
      onClose();
    } catch (err) {
      // Handled by store
    }
  };

  if (!isOpen || !user) return null;

  // Determine if caller can edit the role field
  const canEditRole = () => {
    if (!currentUser) return false;
    if (isSelf) {
      return currentUser.role === 'OrgAdmin'; // Only admin can change own role
    }
    if (currentUser.role === 'OrgAdmin') return true; // Admins can change other roles
    if (currentUser.role === 'Manager' && user.role === 'Employee') return true; // Managers can change employee roles
    return false;
  };

  // Determine allowed roles dropdown options
  const getAllowedRoles = () => {
    if (currentUser?.role === 'OrgAdmin') {
      return [
        { value: 'OrgAdmin', label: 'Organization Admin' },
        { value: 'Manager', label: 'Manager' },
        { value: 'TeamLeader', label: 'Team Leader' },
        { value: 'Employee', label: 'Employee' },
      ];
    }
    return [
      { value: 'Manager', label: 'Manager' },
      { value: 'TeamLeader', label: 'Team Leader' },
      { value: 'Employee', label: 'Employee' },
    ];
  };

  const getReportingManagerOptions = () => {
    if (watchRole === 'OrgAdmin') {
      return [];
    }
    if (watchRole === 'Manager') {
      return reportingUsers.filter((u) => (u.role === 'OrgAdmin' || u.role === 'SuperAdmin') && u.id !== user?.id);
    }
    if (watchRole === 'TeamLeader') {
      return reportingUsers.filter(
        (u) => (u.role === 'Manager' || u.role === 'OrgAdmin' || u.role === 'SuperAdmin') && u.id !== user?.id
      );
    }
    if (watchRole === 'Employee') {
      const leaders = reportingUsers.filter(
        (u) => (u.role === 'TeamLeader' || (u.role === 'Employee' && u.is_team_leader) || u.role === 'Manager') && u.id !== user?.id
      );
      if (leaders.length > 0) {
        return leaders;
      }
      return reportingUsers.filter((u) => (u.role === 'OrgAdmin' || u.role === 'SuperAdmin') && u.id !== user?.id);
    }
    return [];
  };

  const managerOptions = getReportingManagerOptions();

  // Find assigned reporting manager for display
  const assignedManager = reportingUsers.find((u) => u.id === user.reporting_to_id);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="w-full max-w-md glass-panel border border-slate-800/90 rounded-2xl shadow-2xl relative overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-100">
              {isSelf ? 'Edit Your Profile' : 'Edit User Profile'}
            </h3>
            <p className="text-xs text-slate-400">
              {isSelf ? 'Update your personal profile details.' : 'Update user profile details and roles.'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
          {error && (
            <div className="p-3.5 bg-red-950/20 border border-red-900/30 rounded-xl flex items-start gap-2.5 text-sm text-red-400">
              <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* First Name & Last Name */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                First Name
              </label>
              <input
                type="text"
                {...register('first_name', { maxLength: 100 })}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Last Name
              </label>
              <input
                type="text"
                {...register('last_name', { maxLength: 100 })}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
              />
            </div>
          </div>

          {/* Email */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Email Address
            </label>
            <input
              type="email"
              {...register('email', {
                required: 'Email is required',
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: 'Invalid email address',
                },
              })}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>
            )}
          </div>

          {/* Role */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Role Permission
            </label>
            {canEditRole() ? (
              <select
                {...register('role', { required: 'Role is required' })}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
              >
                {getAllowedRoles().map((role) => (
                  <option key={role.value} value={role.value}>
                    {role.label}
                  </option>
                ))}
              </select>
            ) : (
              <div className="w-full px-3.5 py-2.5 bg-slate-900/40 border border-slate-800/80 rounded-xl text-sm text-slate-400 select-none flex items-center justify-between">
                <span>{user.role}</span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-500 border border-slate-700/60">
                  Role Locked
                </span>
                <input type="hidden" {...register('role')} />
              </div>
            )}
          </div>

          {/* Reporting Manager Section */}
          {watchRole !== 'OrgAdmin' && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between">
                <span>
                  Reporting Manager{' '}
                  {!isAgentSelf && watchRole === 'Employee' ? (
                    <span className="text-red-400">*</span>
                  ) : null}
                </span>
                {isFetchingManagers && <Loader2 className="w-3 h-3 animate-spin text-brand-400" />}
              </label>

              {/* Agent Self-Profile: READ-ONLY DISPLAY, NO SELECTABLE DROPDOWN */}
              {isAgentSelf ? (
                <div className="w-full px-3.5 py-2.5 bg-slate-900/60 border border-slate-800 rounded-xl text-sm text-slate-200 flex items-center justify-between select-none">
                  <div className="flex items-center gap-2 min-w-0">
                    <UserCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span className="font-medium text-slate-200 truncate">
                      {assignedManager
                        ? `${assignedManager.first_name || ''} ${assignedManager.last_name || ''} (${assignedManager.role}${assignedManager.reporting_to_id && assignedManager.role === 'Employee' ? ' - TL' : ''})`.trim()
                        : user.reporting_to_id
                          ? 'Assigned Manager'
                          : 'Not Assigned / Direct'}
                    </span>
                  </div>
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
                    Manager Assigned
                  </span>
                  <input type="hidden" {...register('reporting_to_id')} />
                </div>
              ) : (
                /* Admin/Manager editing staff member: Selectable Dropdown */
                <>
                  <select
                    {...register('reporting_to_id', {
                      required: watchRole === 'Employee' ? 'Reporting Manager is required for Sales Agents' : false,
                    })}
                    className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
                  >
                    <option value="">
                      {watchRole === 'Employee'
                        ? '-- Select Reporting Manager * --'
                        : '-- None / Top Level (Optional) --'}
                    </option>
                    {managerOptions.map((mgr) => (
                      <option key={mgr.id} value={mgr.id}>
                        {mgr.first_name} {mgr.last_name} ({mgr.role}
                        {mgr.reporting_to_id && mgr.role === 'Employee' ? ' - TL' : ''})
                      </option>
                    ))}
                  </select>
                  {errors.reporting_to_id && (
                    <p className="mt-1 text-xs text-red-400">{errors.reporting_to_id.message}</p>
                  )}
                </>
              )}
            </div>
          )}

          {/* Optional Password Update */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Update Password (Optional)
            </label>
            <div className="relative">
              <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-slate-500" />
              <input
                type="password"
                placeholder="•••••••• (Leave blank to keep current)"
                {...register('password', {
                  validate: (val) => {
                    if (val && val.length < 8) return 'Password must be at least 8 characters';
                    return true;
                  },
                })}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
              />
            </div>
            {errors.password && (
              <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
            )}
          </div>

          {/* Floor IP Whitelisting & Device Binding - HIDDEN for agent self-profile */}
          {!isAgentSelf && (currentUser?.role === 'OrgAdmin' || currentUser?.role === 'Manager') && (
            <div className="pt-3 border-t border-slate-800/80 space-y-3">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-300 uppercase tracking-wider">
                <ShieldAlert className="w-3.5 h-3.5 text-indigo-400" />
                <span>Floor Security &amp; Device Binding</span>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Floor IP Whitelist (Comma-separated)
                </label>
                <input
                  type="text"
                  placeholder="e.g. 192.168.1.0/24, 203.0.113.5 (Blank = Any IP)"
                  {...register('allowed_ip_whitelist')}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                />
                <p className="mt-1 text-[10px] text-slate-500">Restricts user login exclusively to floor network coordinates.</p>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Registered Device UUID (Smartphone Binding)
                </label>
                <input
                  type="text"
                  placeholder="e.g. a8b4c2e1-9f33-40a2-b210-998877665544"
                  {...register('registered_device_uuid')}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                />
                <p className="mt-1 text-[10px] text-slate-500">Locks calling floor logins to this registered smartphone/machine hardware ID.</p>
              </div>
            </div>
          )}

          {/* Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800/60">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 active:bg-slate-900 border border-slate-700 hover:border-slate-600 rounded-xl text-sm font-medium text-slate-200 hover:text-white transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-sm font-semibold transition-all cursor-pointer shadow-lg shadow-brand-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
