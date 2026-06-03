import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { X, ShieldAlert, Loader2, KeyRound } from 'lucide-react';
import { useUserStore } from '../../store/userStore';
import { useAuthStore } from '../../store/authStore';
import { UserResponse } from '../../services/userApi';

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
}

export const EditUserModal: React.FC<EditUserModalProps> = ({ user, isOpen, onClose }) => {
  const { updateUser, isLoading, error } = useUserStore();
  const currentUser = useAuthStore((state) => state.user);

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<EditFormInput>({
    defaultValues: {
      email: '',
      first_name: '',
      last_name: '',
      role: '',
      password: '',
    },
  });

  useEffect(() => {
    if (user) {
      setValue('email', user.email);
      setValue('first_name', user.first_name || '');
      setValue('last_name', user.last_name || '');
      setValue('role', user.role);
      setValue('password', '');
    }
  }, [user, setValue]);

  const onSubmit = async (data: EditFormInput) => {
    if (!user) return;
    try {
      const payload: Parameters<typeof updateUser>[1] = {
        email: data.email,
        first_name: data.first_name || null,
        last_name: data.last_name || null,
        role: data.role,
      };
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

  const isSelf = currentUser?.id === user.id;

  // Determine if caller can edit the role field
  const canEditRole = () => {
    if (!currentUser) return false;
    if (isSelf) {
      return currentUser.role === 'OrgAdmin'; // Only admin can change own role (but demoting self requires other admin, handled on backend)
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
        { value: 'Employee', label: 'Employee' },
      ];
    }
    // Managers can toggle between Manager/Employee roles for employees
    return [
      { value: 'Manager', label: 'Manager' },
      { value: 'Employee', label: 'Employee' },
    ];
  };

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
        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-5">
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
              <div className="w-full px-3.5 py-2.5 bg-slate-900/40 border border-slate-800/80 rounded-xl text-sm text-slate-500 select-none">
                {user.role} (Role locked)
                <input type="hidden" {...register('role')} />
              </div>
            )}
          </div>

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

          {/* Buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
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
