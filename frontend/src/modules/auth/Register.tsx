import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { api } from '../../services/api';
import { AlertCircle, Loader2, CheckCircle } from 'lucide-react';

const INDUSTRY_OPTIONS = [
  { value: 'telecalling', label: 'Telecalling / Call Center' },
  { value: 'healthcare_dental', label: 'Healthcare / Dental' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'insurance', label: 'Insurance' },
  { value: 'loan_recovery', label: 'Loan Recovery / Collections' },
  { value: 'generic', label: 'Other / Generic CRM' },
];

const registerSchema = z.object({
  full_name: z.string().min(1, 'Full name is required'),
  company_name: z.string().min(2, 'Company name must be at least 2 characters'),
  email: z.string().email('Please enter a valid email address'),
  phone: z.string().min(5, 'Please enter a valid phone number'),
  industry: z.string().min(1, 'Please choose your industry'),
});

type RegisterForm = z.infer<typeof registerSchema>;

export const Register: React.FC = () => {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchParams] = useSearchParams();
  const presetIndustry = searchParams.get('industry') || 'telecalling';

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: { industry: presetIndustry },
  });

  const onSubmit = async (data: RegisterForm) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.post('/auth/trial-register', data);
      setSuccessMsg(res.data?.detail || '');
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed. Please check details and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="text-center py-6 space-y-4">
        <div className="w-16 h-16 bg-green-500/10 border border-green-500/20 rounded-full flex items-center justify-center mx-auto animate-pulse">
          <CheckCircle className="w-8 h-8 text-green-400" />
        </div>
        <h2 className="text-xl font-bold text-white">Your Workspace is Ready!</h2>
        <p className="text-slate-400 text-sm max-w-xs mx-auto">
          {successMsg || "We've emailed you a secure link to set your password and sign in to your 14-day free trial."}
        </p>
        <p className="text-slate-500 text-xs max-w-xs mx-auto pt-2">
          Check your inbox (and spam) for the setup link, then log in to start using your CRM.
        </p>
        <div className="pt-4">
          <Link to="/login" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-xl transition-all">
            Return to Login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="text-center pb-2">
        <h2 className="text-lg font-semibold text-white">Start Your 14-Day Trial</h2>
        <p className="text-xs text-slate-400 mt-1">Submit your details to request an enterprise-grade CRM workspace.</p>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-200 text-sm rounded-xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <p>{error}</p>
        </div>
      )}

      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Full Name</label>
        <input
          type="text"
          {...register('full_name')}
          className={`w-full px-4 py-3 rounded-xl glass-input ${errors.full_name ? 'border-red-500/50' : ''}`}
          placeholder="John Doe"
        />
        {errors.full_name && <p className="mt-1.5 text-xs text-red-400">{errors.full_name.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Company Name</label>
        <input
          type="text"
          {...register('company_name')}
          className={`w-full px-4 py-3 rounded-xl glass-input ${errors.company_name ? 'border-red-500/50' : ''}`}
          placeholder="Acme Corp"
        />
        {errors.company_name && <p className="mt-1.5 text-xs text-red-400">{errors.company_name.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Your Industry</label>
        <select
          {...register('industry')}
          className={`w-full px-4 py-3 rounded-xl glass-input ${errors.industry ? 'border-red-500/50' : ''}`}
        >
          {INDUSTRY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <p className="mt-1.5 text-[10px] text-slate-500">Sets up your CRM dashboard for your business.</p>
        {errors.industry && <p className="mt-1.5 text-xs text-red-400">{errors.industry.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Email Address</label>
        <input
          type="email"
          {...register('email')}
          className={`w-full px-4 py-3 rounded-xl glass-input ${errors.email ? 'border-red-500/50' : ''}`}
          placeholder="john@acme.com"
        />
        {errors.email && <p className="mt-1.5 text-xs text-red-400">{errors.email.message}</p>}
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Phone Number</label>
        <input
          type="tel"
          {...register('phone')}
          className={`w-full px-4 py-3 rounded-xl glass-input ${errors.phone ? 'border-red-500/50' : ''}`}
          placeholder="+91 98765 43210"
        />
        {errors.phone && <p className="mt-1.5 text-xs text-red-400">{errors.phone.message}</p>}
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full py-3 px-4 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-150 flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20"
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Submitting Request...
          </>
        ) : (
          'Request Free Trial'
        )}
      </button>

      <p className="text-center text-[10px] text-slate-500 pt-1 leading-normal">
        By requesting a trial, you agree to our{' '}
        <Link to="/legal/terms" className="text-brand-400 hover:text-brand-300">Terms of Service</Link> and{' '}
        <Link to="/legal/privacy" className="text-brand-400 hover:text-brand-300">Privacy Policy</Link>.
      </p>

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
