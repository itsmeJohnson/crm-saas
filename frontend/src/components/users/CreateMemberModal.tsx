import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { X, Mail, ShieldAlert, Loader2, KeyRound, UserCheck } from 'lucide-react';
import { useUserStore } from '../../store/userStore';
import { useAuthStore } from '../../store/authStore';
import { userApi, UserResponse } from '../../services/userApi';

interface CreateMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface CreateFormInput {
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  password: string;
  reporting_to_id: string;
}

export const CreateMemberModal: React.FC<CreateMemberModalProps> = ({ isOpen, onClose }) => {
  const { createUser, isLoading, error } = useUserStore();
  const currentUser = useAuthStore((state) => state.user);
  const currentOrg = useAuthStore((state) => state.organization);

  const [reportingUsers, setReportingUsers] = useState<UserResponse[]>([]);
  const [isFetchingManagers, setIsFetchingManagers] = useState(false);

  const isTeamLeader = currentUser?.role === 'Employee' && currentUser?.is_team_leader;
  const isManager = currentUser?.role === 'Manager';
  const isAdminOrSuper = currentUser?.role === 'OrgAdmin' || currentUser?.role === 'SuperAdmin';

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<CreateFormInput>({
    defaultValues: {
      email: '',
      first_name: '',
      last_name: '',
      role: 'Employee',
      password: '',
      reporting_to_id: '',
    },
  });

  const selectedRole = watch('role');

  // Load potential managers when modal opens
  useEffect(() => {
    if (isOpen) {
      const fetchManagers = async () => {
        setIsFetchingManagers(true);
        try {
          const data = await userApi.getUsers({ limit: 200, is_active: true });
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

  // Set default values based on current user role when modal opens
  useEffect(() => {
    if (isOpen && currentUser) {
      if (isTeamLeader) {
        setValue('role', 'Employee');
        setValue('reporting_to_id', currentUser.id);
      } else if (isManager) {
        setValue('role', 'Employee');
        setValue('reporting_to_id', currentUser.id);
      } else {
        setValue('role', 'Employee');
        setValue('reporting_to_id', '');
      }
    }
  }, [isOpen, currentUser, isTeamLeader, isManager, setValue]);

  const onSubmit = async (data: CreateFormInput) => {
    if (!currentOrg) return;
    try {
      const mappedRole = data.role === 'TeamLeader' ? 'Employee' : data.role;
      const payload: Parameters<typeof createUser>[0] = {
        email: data.email,
        first_name: data.first_name || undefined,
        last_name: data.last_name || undefined,
        role: mappedRole,
        password: data.password,
        organization_id: currentOrg.id,
        reporting_to_id: data.reporting_to_id !== '' ? data.reporting_to_id : null,
      };

      await createUser(payload);
      reset();
      onClose();
    } catch (err) {
      // Error handled by store
    }
  };

  if (!isOpen) return null;

  // Roles available in dropdown
  const getAllowedRoles = () => {
    if (isAdminOrSuper) {
      return [
        { value: 'OrgAdmin', label: 'Organization Admin' },
        { value: 'Manager', label: 'Manager' },
        { value: 'TeamLeader', label: 'Team Leader' },
        { value: 'Employee', label: 'Employee' },
      ];
    }
    if (isManager) {
      return [
        { value: 'TeamLeader', label: 'Team Leader' },
        { value: 'Employee', label: 'Employee' },
      ];
    }
    // Team Leaders can only create Employees
    return [{ value: 'Employee', label: 'Employee' }];
  };

  // Filter reporting manager choices
  const getReportingManagerOptions = () => {
    if (selectedRole === 'OrgAdmin') {
      return []; // OrgAdmin reports to no one
    }
    if (selectedRole === 'Manager') {
      // Managers report to OrgAdmin
      return reportingUsers.filter((u) => u.role === 'OrgAdmin');
    }
    if (selectedRole === 'TeamLeader') {
      // Team Leaders report to Managers
      return reportingUsers.filter((u) => u.role === 'Manager');
    }
    if (selectedRole === 'Employee') {
      // Employees report to Team Leaders (Employees who report to a Manager)
      return reportingUsers.filter((u) => u.role === 'Employee' && u.is_team_leader);
    }
    return [];
  };

  const managerOptions = getReportingManagerOptions();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md glass-panel border border-slate-800/90 rounded-2xl shadow-2xl relative overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
              <UserCheck className="w-5 h-5 text-brand-400" />
              Create Team Member
            </h3>
            <p className="text-xs text-slate-400">Directly register a new member with login credentials.</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
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
                placeholder="Jane"
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
                placeholder="Doe"
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
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-slate-500" />
              <input
                type="email"
                placeholder="email@example.com"
                {...register('email', {
                  required: 'Email address is required',
                  pattern: {
                    value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                    message: 'Invalid email address',
                  },
                })}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
              />
            </div>
            {errors.email && (
              <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>
            )}
          </div>

          {/* Password */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Password
            </label>
            <div className="relative">
              <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-slate-500" />
              <input
                type="password"
                placeholder="Min 8 characters"
                {...register('password', {
                  required: 'Password is required',
                  minLength: {
                    value: 8,
                    message: 'Password must be at least 8 characters',
                  },
                })}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
              />
            </div>
            {errors.password && (
              <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>
            )}
          </div>

          {/* Role selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Role Permission
            </label>
            {isAdminOrSuper ? (
              <select
                {...register('role', { required: 'Please select a role' })}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
              >
                {getAllowedRoles().map((role) => (
                  <option key={role.value} value={role.value}>
                    {role.label}
                  </option>
                ))}
              </select>
            ) : (
              <div className="w-full px-3.5 py-2.5 bg-slate-900/40 border border-slate-800/80 rounded-xl text-sm text-slate-500 select-none">
                Employee (Role locked)
                <input type="hidden" {...register('role')} />
              </div>
            )}
          </div>

          {/* Reporting manager selection */}
          {selectedRole !== 'OrgAdmin' && (
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between">
                <span>Reporting Manager</span>
                {isFetchingManagers && <Loader2 className="w-3 h-3 animate-spin text-brand-400" />}
              </label>

              {isTeamLeader ? (
                // Lock Team Leader report to themselves
                <div className="w-full px-3.5 py-2.5 bg-slate-900/40 border border-slate-800/80 rounded-xl text-sm text-slate-500 select-none">
                  {currentUser?.first_name} {currentUser?.last_name} (Self - locked)
                  <input type="hidden" {...register('reporting_to_id')} />
                </div>
              ) : (
                <select
                  {...register('reporting_to_id', {
                    required: selectedRole !== 'OrgAdmin' ? 'Reporting Manager is required' : false,
                  })}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
                >
                  <option value="">-- Select Reporting Manager --</option>
                  {managerOptions.map((mgr) => (
                    <option key={mgr.id} value={mgr.id}>
                      {mgr.first_name} {mgr.last_name} ({mgr.role}
                      {mgr.reporting_to_id && mgr.role === 'Employee' ? ' - TL' : ''})
                    </option>
                  ))}
                </select>
              )}
              {errors.reporting_to_id && (
                <p className="mt-1 text-xs text-red-400">{errors.reporting_to_id.message}</p>
              )}
            </div>
          )}

          {/* Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800/80">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2.5 bg-slate-900 hover:bg-slate-900/80 active:bg-slate-900/50 border border-slate-800 hover:border-slate-700 rounded-xl text-sm font-medium text-slate-300 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
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
                  Creating...
                </>
              ) : (
                'Create Member'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
