import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { api } from '../../services/api';
import { AlertCircle, Loader2, CheckCircle } from 'lucide-react';

const registerSchema = z.object({
  company_name: z.string().min(2, 'Company name must be at least 2 characters'),
  slug: z.string().min(2, 'Slug must be at least 2 characters').regex(/^[a-z0-9-]+$/, 'Slug must contain only lowercase letters, numbers, and hyphens'),
  admin_email: z.string().email('Please enter a valid email address'),
  admin_password: z.string().min(8, 'Password must be at least 8 characters long'),
  first_name: z.string().min(1, 'First name is required'),
  last_name: z.string().min(1, 'Last name is required'),
});

type RegisterForm = z.infer<typeof registerSchema>;

export const Register: React.FC = () => {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  });

  const handleCompanyNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    const generatedSlug = value
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-');
    setValue('slug', generatedSlug, { shouldValidate: true });
  };

  const onSubmit = async (data: RegisterForm) => {
    setIsLoading(true);
    setError(null);
    try {
      await api.post('/auth/register', data);
      setSuccess(true);
      setTimeout(() => {
        navigate('/login');
      }, 2500);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed. Please check details and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="text-center py-6 space-y-4">
        <div className="w-16 h-16 bg-green-500/10 border border-green-500/20 rounded-full flex items-center justify-center mx-auto">
          <CheckCircle className="w-8 h-8 text-green-400" />
        </div>
        <h2 className="text-xl font-bold text-white">Tenant Created!</h2>
        <p className="text-slate-400 text-sm max-w-xs mx-auto">
          Your organization workspace has been created successfully. Redirecting you to login...
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-200 text-sm rounded-xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <p>{error}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Company Name</label>
          <input
            type="text"
            {...register('company_name')}
            onChange={(e) => {
              register('company_name').onChange(e);
              handleCompanyNameChange(e);
            }}
            className={`w-full px-4 py-3 rounded-xl glass-input ${errors.company_name ? 'border-red-500/50' : ''}`}
            placeholder="Acme Corp"
          />
          {errors.company_name && <p className="mt-1.5 text-xs text-red-400">{errors.company_name.message}</p>}
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Org Slug</label>
          <input
            type="text"
            {...register('slug')}
            className={`w-full px-4 py-3 rounded-xl glass-input ${errors.slug ? 'border-red-500/50' : ''}`}
            placeholder="acme-corp"
          />
          {errors.slug && <p className="mt-1.5 text-xs text-red-400">{errors.slug.message}</p>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">First Name</label>
          <input
            type="text"
            {...register('first_name')}
            className={`w-full px-4 py-3 rounded-xl glass-input ${errors.first_name ? 'border-red-500/50' : ''}`}
            placeholder="John"
          />
          {errors.first_name && <p className="mt-1.5 text-xs text-red-400">{errors.first_name.message}</p>}
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Last Name</label>
          <input
            type="text"
            {...register('last_name')}
            className={`w-full px-4 py-3 rounded-xl glass-input ${errors.last_name ? 'border-red-500/50' : ''}`}
            placeholder="Doe"
          />
          {errors.last_name && <p className="mt-1.5 text-xs text-red-400">{errors.last_name.message}</p>}
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Admin Email</label>
        <input
          type="email"
          {...register('admin_email')}
          className={`w-full px-4 py-3 rounded-xl glass-input ${errors.admin_email ? 'border-red-500/50' : ''}`}
          placeholder="admin@acme.com"
        />
        {errors.admin_email && <p className="mt-1.5 text-xs text-red-400">{errors.admin_email.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Password</label>
        <input
          type="password"
          {...register('admin_password')}
          className={`w-full px-4 py-3 rounded-xl glass-input ${errors.admin_password ? 'border-red-500/50' : ''}`}
          placeholder="••••••••"
        />
        {errors.admin_password && <p className="mt-1.5 text-xs text-red-400">{errors.admin_password.message}</p>}
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full py-3 px-4 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-150 flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20"
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Creating Workspace...
          </>
        ) : (
          'Register Tenant'
        )}
      </button>

      <div className="text-center pt-2">
        <p className="text-slate-400 text-sm">
          Already have an account?{' '}
          <Link to="/login" className="text-brand-400 hover:text-brand-300 font-semibold transition-all">
            Sign In
          </Link>
        </p>
      </div>
    </form>
  );
};
