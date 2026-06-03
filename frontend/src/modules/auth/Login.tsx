import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../services/api';
import { AlertCircle, Loader2 } from 'lucide-react';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters long'),
});

type LoginForm = z.infer<typeof loginSchema>;

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    setError(null);
    try {
      const loginRes = await api.post('/auth/login', data);
      const { access_token, refresh_token } = loginRes.data;

      const meRes = await api.get('/auth/me', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });

      const { user, organization } = meRes.data;
      setAuth(user, organization, access_token, refresh_token);
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred during login. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-200 text-sm rounded-xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <p>{error}</p>
        </div>
      )}

      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Email Address</label>
        <input
          type="email"
          {...register('email')}
          className={`w-full px-4 py-3 rounded-xl glass-input ${errors.email ? 'border-red-500/50' : ''}`}
          placeholder="admin@company.com"
        />
        {errors.email && <p className="mt-1.5 text-xs text-red-400">{errors.email.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Password</label>
        <input
          type="password"
          {...register('password')}
          className={`w-full px-4 py-3 rounded-xl glass-input ${errors.password ? 'border-red-500/50' : ''}`}
          placeholder="••••••••"
        />
        {errors.password && <p className="mt-1.5 text-xs text-red-400">{errors.password.message}</p>}
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full py-3 px-4 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-150 flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20"
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Signing In...
          </>
        ) : (
          'Sign In'
        )}
      </button>

      <div className="text-center pt-2">
        <p className="text-slate-400 text-sm">
          Don't have a workspace?{' '}
          <Link to="/register" className="text-brand-400 hover:text-brand-300 font-semibold transition-all">
            Create tenant
          </Link>
        </p>
      </div>
    </form>
  );
};
