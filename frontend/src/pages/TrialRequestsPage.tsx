import React, { useEffect, useState } from 'react';
import { superAdminApi, TrialRequestResponse } from '../services/superAdminApi';
import { 
  CheckCircle, XCircle, Clock, Search, ShieldAlert, 
  Check, X, RefreshCw, Sparkles, Building, User, Mail, Phone 
} from 'lucide-react';

export const TrialRequestsPage: React.FC = () => {
  const [requests, setRequests] = useState<TrialRequestResponse[]>([]);
  const [filteredRequests, setFilteredRequests] = useState<TrialRequestResponse[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'PENDING' | 'APPROVED' | 'REJECTED'>('ALL');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const fetchRequests = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await superAdminApi.getTrialRequests();
      setRequests(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch trial requests.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, []);

  useEffect(() => {
    let result = requests;

    if (statusFilter !== 'ALL') {
      result = result.filter(r => r.status === statusFilter);
    }

    if (searchQuery.trim() !== '') {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        r =>
          r.full_name.toLowerCase().includes(query) ||
          r.company_name.toLowerCase().includes(query) ||
          r.email.toLowerCase().includes(query) ||
          r.phone.toLowerCase().includes(query)
      );
    }

    setFilteredRequests(result);
  }, [requests, searchQuery, statusFilter]);

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleApprove = async (id: string, company: string) => {
    setActioningId(id);
    try {
      await superAdminApi.approveTrialRequest(id);
      showToast(`Trial request for ${company} approved successfully. Welcome email sent.`, 'success');
      fetchRequests();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to approve request.', 'error');
    } finally {
      setActioningId(null);
    }
  };

  const handleReject = async (id: string, company: string) => {
    setActioningId(id);
    try {
      await superAdminApi.rejectTrialRequest(id);
      showToast(`Trial request for ${company} rejected.`, 'success');
      fetchRequests();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to reject request.', 'error');
    } finally {
      setActioningId(null);
    }
  };

  const handleResendActivation = async (id: string, email: string) => {
    setActioningId(id);
    try {
      await superAdminApi.resendTrialActivationEmail(id);
      showToast(`Activation email successfully resent to ${email}`, 'success');
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to resend activation email.', 'error');
    } finally {
      setActioningId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'PENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="w-3.5 h-3.5" />
            Pending Review
          </span>
        );
      case 'APPROVED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
            <CheckCircle className="w-3.5 h-3.5" />
            Approved
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
            <XCircle className="w-3.5 h-3.5" />
            Rejected
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-xl flex items-center gap-2 border text-sm transition-all duration-300 animate-slide-in ${
          toast.type === 'success' 
            ? 'bg-green-500/10 border-green-500/20 text-green-200' 
            : 'bg-red-500/10 border-red-500/20 text-red-200'
        }`}>
          {toast.type === 'success' ? <Check className="w-4 h-4 text-green-400" /> : <X className="w-4 h-4 text-red-400" />}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/40 p-6 rounded-2xl border border-slate-800 backdrop-blur-sm">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-brand-400" />
            <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Trial Registration Requests</h1>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Review and approve enterprise CRM trial workspaces. Approving provisions their tenant environment automatically.
          </p>
        </div>
        <button
          onClick={fetchRequests}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-sm font-medium border border-slate-700/50 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters & Search */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Search */}
        <div className="md:col-span-2 relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by name, company, email..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-950/40 border border-slate-850 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500/50"
          />
        </div>

        {/* Status Filters */}
        <div className="md:col-span-2 flex bg-slate-950/20 p-1 rounded-xl border border-slate-900">
          {(['ALL', 'PENDING', 'APPROVED', 'REJECTED'] as const).map(filter => (
            <button
              key={filter}
              onClick={() => setStatusFilter(filter)}
              className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                statusFilter === filter
                  ? 'bg-brand-500 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      {/* Main List */}
      {error ? (
        <div className="p-6 bg-red-500/5 border border-red-500/10 rounded-2xl text-center text-red-200 flex flex-col items-center gap-3">
          <ShieldAlert className="w-10 h-10 text-red-500" />
          <p className="font-semibold">{error}</p>
          <button onClick={fetchRequests} className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-xl text-xs font-medium border border-red-500/20 transition-all">
            Try Again
          </button>
        </div>
      ) : isLoading && requests.length === 0 ? (
        <div className="py-24 text-center">
          <RefreshCw className="w-8 h-8 text-brand-400 animate-spin mx-auto mb-4" />
          <p className="text-slate-400 text-sm">Loading trial requests...</p>
        </div>
      ) : filteredRequests.length === 0 ? (
        <div className="py-16 bg-slate-950/20 border border-slate-900 rounded-2xl text-center text-slate-500 text-sm">
          No trial requests found matching the current filters.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredRequests.map(req => (
            <div
              key={req.id}
              className="bg-slate-950/25 hover:bg-slate-950/40 p-5 rounded-2xl border border-slate-900/60 hover:border-slate-800 transition-all flex flex-col lg:flex-row lg:items-center justify-between gap-6"
            >
              {/* Content fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 flex-1">
                {/* Company & Status */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-slate-100 font-semibold">
                    <Building className="w-4 h-4 text-brand-400 flex-shrink-0" />
                    <span className="truncate">{req.company_name}</span>
                  </div>
                  <div>{getStatusBadge(req.status)}</div>
                </div>

                {/* Contact Name & Date */}
                <div className="space-y-1 text-sm text-slate-400">
                  <div className="flex items-center gap-2 text-slate-200 font-medium">
                    <User className="w-4 h-4 text-slate-500 flex-shrink-0" />
                    <span>{req.full_name}</span>
                  </div>
                  <div className="text-xs text-slate-500">
                    Requested: {new Date(req.created_at).toLocaleDateString(undefined, { 
                      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' 
                    })}
                  </div>
                </div>

                {/* Email */}
                <div className="flex items-center gap-2 text-sm text-slate-300 min-w-0">
                  <Mail className="w-4 h-4 text-slate-500 flex-shrink-0" />
                  <span className="truncate">{req.email}</span>
                </div>

                {/* Phone */}
                <div className="flex items-center gap-2 text-sm text-slate-300">
                  <Phone className="w-4 h-4 text-slate-500 flex-shrink-0" />
                  <span>{req.phone}</span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-2 lg:border-l lg:border-slate-900 lg:pl-6">
                {req.status === 'PENDING' && (
                  <>
                    <button
                      disabled={actioningId !== null}
                      onClick={() => handleReject(req.id, req.company_name)}
                      className="flex-1 lg:flex-initial px-3.5 py-2 bg-red-500/10 hover:bg-red-500/20 disabled:opacity-50 text-red-400 hover:text-red-300 border border-red-500/20 hover:border-red-500/30 rounded-xl text-xs font-semibold transition-all flex items-center justify-center gap-1.5"
                    >
                      {actioningId === req.id ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <X className="w-3.5 h-3.5" />
                      )}
                      Reject
                    </button>
                    <button
                      disabled={actioningId !== null}
                      onClick={() => handleApprove(req.id, req.company_name)}
                      className="flex-1 lg:flex-initial px-3.5 py-2 bg-green-500 hover:bg-green-600 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition-all shadow-lg shadow-green-500/10 flex items-center justify-center gap-1.5"
                    >
                      {actioningId === req.id ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Check className="w-3.5 h-3.5" />
                      )}
                      Approve & Provision
                    </button>
                  </>
                )}
                {req.status === 'APPROVED' && (
                  <button
                    disabled={actioningId !== null}
                    onClick={() => handleResendActivation(req.id, req.email)}
                    className="flex-1 lg:flex-initial px-3.5 py-2 bg-brand-500/10 hover:bg-brand-500/20 disabled:opacity-50 text-brand-400 hover:text-brand-300 border border-brand-500/20 hover:border-brand-500/30 rounded-xl text-xs font-semibold transition-all flex items-center justify-center gap-1.5"
                  >
                    {actioningId === req.id ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Mail className="w-3.5 h-3.5" />
                    )}
                    Resend Email
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
