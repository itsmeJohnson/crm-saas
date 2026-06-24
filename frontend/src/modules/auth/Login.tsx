import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../services/api';
import { AlertCircle, Loader2, KeyRound, Mail, ArrowLeft, CheckCircle } from 'lucide-react';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters long'),
});

const forgotSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
});

const resetSchema = z.object({
  token: z.string().min(4, 'Code/Token is required'),
  password: z.string().min(8, 'Password must be at least 8 characters long'),
});

type LoginForm = z.infer<typeof loginSchema>;
type ForgotForm = z.infer<typeof forgotSchema>;
type ResetForm = z.infer<typeof resetSchema>;

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  
  const [step, setStep] = useState<'login' | 'forgot' | 'reset'>('login');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [demoToken, setDemoToken] = useState<string | null>(null);

  // Forms
  const {
    register: loginRegister,
    handleSubmit: handleLoginSubmit,
    formState: { errors: loginErrors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const {
    register: forgotRegister,
    handleSubmit: handleForgotSubmit,
    formState: { errors: forgotErrors },
  } = useForm<ForgotForm>({
    resolver: zodResolver(forgotSchema),
  });

  const {
    register: resetRegister,
    handleSubmit: handleResetSubmit,
    formState: { errors: resetErrors },
    reset: resetFormReset,
  } = useForm<ResetForm>({
    resolver: zodResolver(resetSchema),
  });

  const onLoginSubmit = async (data: LoginForm) => {
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

      const { user, organization, features } = meRes.data;
      setAuth(user, organization, features || [], access_token, refresh_token);
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred during login. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const onForgotSubmit = async (data: ForgotForm) => {
    setIsLoading(true);
    setError(null);
    setDemoToken(null);
    try {
      const res = await api.post('/auth/forgot-password', data);
      setDemoToken(res.data.token);
      setSuccess('Reset code generated successfully! Enter it below to change your password.');
      setTimeout(() => {
        setStep('reset');
        setSuccess(null);
      }, 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to request password reset code.');
    } finally {
      setIsLoading(false);
    }
  };

  const onResetSubmit = async (data: ResetForm) => {
    setIsLoading(true);
    setError(null);
    try {
      await api.post('/auth/reset-password', data);
      setSuccess('Your password has been reset successfully! Redirecting to login...');
      setDemoToken(null);
      resetFormReset();
      setTimeout(() => {
        setStep('login');
        setSuccess(null);
      }, 2500);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset password. Please verify the code.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-200 text-sm rounded-xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <p>{error}</p>
        </div>
      )}

      {success && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-200 text-sm rounded-xl flex items-start gap-3">
          <CheckCircle className="w-5 h-5 flex-shrink-0 text-emerald-400" />
          <p>{success}</p>
        </div>
      )}

      {/* STEP 1: LOGIN */}
      {step === 'login' && (
        <form onSubmit={handleLoginSubmit(onLoginSubmit)} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Email Address</label>
            <input
              type="email"
              {...loginRegister('email')}
              className={`w-full px-4 py-3 rounded-xl glass-input ${loginErrors.email ? 'border-red-500/50' : ''}`}
              placeholder="admin@company.com"
            />
            {loginErrors.email && <p className="mt-1.5 text-xs text-red-400">{loginErrors.email.message}</p>}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 font-inter">Password</label>
            <input
              type="password"
              {...loginRegister('password')}
              className={`w-full px-4 py-3 rounded-xl glass-input ${loginErrors.password ? 'border-red-500/50' : ''}`}
              placeholder="••••••••"
            />
            {loginErrors.password && <p className="mt-1.5 text-xs text-red-400">{loginErrors.password.message}</p>}
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 px-4 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-150 flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20 cursor-pointer"
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
            <button
              type="button"
              onClick={() => {
                setError(null);
                setSuccess(null);
                setStep('forgot');
              }}
              className="text-brand-400 hover:text-brand-300 text-sm font-semibold transition-all cursor-pointer"
            >
              Forgot Password?
            </button>
          </div>
        </form>
      )}

      {/* STEP 2: FORGOT PASSWORD */}
      {step === 'forgot' && (
        <form onSubmit={handleForgotSubmit(onForgotSubmit)} className="space-y-5">
          <div className="flex items-center gap-2 mb-2">
            <button
              type="button"
              onClick={() => {
                setError(null);
                setSuccess(null);
                setStep('login');
              }}
              className="p-1 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
            >
              <ArrowLeft className="w-4.5 h-4.5" />
            </button>
            <span className="text-sm font-semibold text-slate-300">Back to Login</span>
          </div>

          <div>
            <h3 className="text-lg font-bold text-slate-100 mb-1">Reset Password</h3>
            <p className="text-xs text-slate-400 mb-4">Enter your email and we'll generate a reset code for you.</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="email"
                {...forgotRegister('email')}
                className={`w-full pl-10 pr-4 py-3 rounded-xl glass-input ${forgotErrors.email ? 'border-red-500/50' : ''}`}
                placeholder="user@example.com"
              />
            </div>
            {forgotErrors.email && <p className="mt-1.5 text-xs text-red-400">{forgotErrors.email.message}</p>}
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 px-4 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-150 flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20 cursor-pointer"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating Code...
              </>
            ) : (
              'Send Reset Code'
            )}
          </button>
        </form>
      )}

      {/* STEP 3: RESET PASSWORD */}
      {step === 'reset' && (
        <form onSubmit={handleResetSubmit(onResetSubmit)} className="space-y-5">
          <div className="flex items-center gap-2 mb-2">
            <button
              type="button"
              onClick={() => {
                setError(null);
                setSuccess(null);
                setStep('forgot');
              }}
              className="p-1 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
            >
              <ArrowLeft className="w-4.5 h-4.5" />
            </button>
            <span className="text-sm font-semibold text-slate-300">Back</span>
          </div>

          <div>
            <h3 className="text-lg font-bold text-slate-100 mb-1">Set New Password</h3>
            <p className="text-xs text-slate-400 mb-4">Enter the code and specify your new password.</p>
          </div>

          {demoToken && (
            <div className="p-3.5 bg-amber-500/10 border border-amber-500/25 text-amber-300 text-xs rounded-xl space-y-1">
              <p className="font-semibold flex items-center gap-1.5">
                <KeyRound className="w-3.5 h-3.5 text-amber-400" />
                Demo Reset Code (SMTP Disabled):
              </p>
              <p className="font-mono text-sm tracking-wider select-all bg-slate-950/40 p-2 rounded border border-slate-800 text-center font-bold text-slate-200 mt-1.5">
                {demoToken}
              </p>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Reset Code / Token</label>
            <input
              type="text"
              {...resetRegister('token')}
              className={`w-full px-4 py-3 rounded-xl glass-input font-mono tracking-widest text-center uppercase ${resetErrors.token ? 'border-red-500/50' : ''}`}
              placeholder="E5A3F1"
            />
            {resetErrors.token && <p className="mt-1.5 text-xs text-red-400">{resetErrors.token.message}</p>}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">New Password</label>
            <input
              type="password"
              {...resetRegister('password')}
              className={`w-full px-4 py-3 rounded-xl glass-input ${resetErrors.password ? 'border-red-500/50' : ''}`}
              placeholder="•••••••• (Min 8 chars)"
            />
            {resetErrors.password && <p className="mt-1.5 text-xs text-red-400">{resetErrors.password.message}</p>}
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 px-4 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-150 flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20 cursor-pointer"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Resetting Password...
              </>
            ) : (
              'Reset Password'
            )}
          </button>
        </form>
      )}
    </div>
  );
};
