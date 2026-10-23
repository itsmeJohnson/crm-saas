import React, { useState, useEffect } from 'react';
import { useLeadStore } from '../../store/leadStore';
import { useAuthStore } from '../../store/authStore';
import { useAnalyticsStore } from '../../store/analyticsStore';
import { X, Loader2, AlertCircle, Info, ArrowRightLeft } from 'lucide-react';
import { UserResponse, userApi } from '../../services/userApi';
import { LeadResponse } from '../../services/leadApi';

interface LeadTransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedLeads: LeadResponse[];
  onSuccess: () => void;
}

export const LeadTransferModal: React.FC<LeadTransferModalProps> = ({
  isOpen,
  onClose,
  selectedLeads,
  onSuccess,
}) => {
  const { transferLeads, isLoading, error } = useLeadStore();
  const { user } = useAuthStore();
  
  const [employees, setEmployees] = useState<UserResponse[]>([]);
  const [isLoadingEmployees, setIsLoadingEmployees] = useState(false);
  const [sourceUserId, setSourceUserId] = useState<string>('');
  const [selectedDestUserIds, setSelectedDestUserIds] = useState<string[]>([]);
  const [transferType, setTransferType] = useState<'SELECTED' | 'QUANTITY'>('SELECTED');
  const [quantity, setQuantity] = useState<number | ''>('');
  const [transferReason, setTransferReason] = useState<string>('Territory Rebalance');
  const [transferNotes, setTransferNotes] = useState<string>('');
  const [localError, setLocalError] = useState<string | null>(null);

  // Fetch employees/downlines reporting to current user
  useEffect(() => {
    if (isOpen) {
      setSourceUserId(user?.id || '');
      setSelectedDestUserIds([]);
      setTransferType(selectedLeads.length > 0 ? 'SELECTED' : 'QUANTITY');
      setQuantity('');
      setTransferReason('Territory Rebalance');
      setTransferNotes('');
      setLocalError(null);

      const fetchEmployees = async () => {
        setIsLoadingEmployees(true);
        try {
          // Assignable users: all roles for admins/managers; downline + self
          // for team leaders — so the assign option is always present.
          const data = await userApi.getAssignableUsers();
          setEmployees(data);
        } catch (err) {
          console.error('Failed to fetch employees', err);
        } finally {
          setIsLoadingEmployees(false);
        }
      };

      const isTL = useAnalyticsStore.getState().dashboardData?.role === 'TeamLeader';
      if (user && (user.role === 'SuperAdmin' || user.role === 'OrgAdmin' || user.role === 'Manager' || isTL)) {
        fetchEmployees();
      }
    }
  }, [isOpen, user, selectedLeads]);

  if (!isOpen) return null;

  // Filter selected leads that belong to the current source user
  const matchingSelectedLeads = selectedLeads.filter(l => l.assigned_user_id === sourceUserId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (!sourceUserId) {
      setLocalError('Please select a source user.');
      return;
    }

    if (selectedDestUserIds.length === 0) {
      setLocalError('Please select at least one destination assignee.');
      return;
    }

    if (selectedDestUserIds.includes(sourceUserId)) {
      setLocalError('Source user cannot be one of the destination assignees.');
      return;
    }

    let payload: any = {
      source_user_id: sourceUserId,
      destination_user_ids: selectedDestUserIds,
      reason: transferReason,
      notes: transferNotes.trim() || undefined,
    };

    if (transferType === 'SELECTED') {
      if (matchingSelectedLeads.length === 0) {
        setLocalError(`No selected leads are currently assigned to the chosen source user.`);
        return;
      }
      payload.lead_ids = matchingSelectedLeads.map(l => l.id);
    } else {
      if (quantity === '' || Number(quantity) <= 0) {
        setLocalError('Please specify a positive quantity count to transfer.');
        return;
      }
      payload.quantity = Number(quantity);
    }

    try {
      await transferLeads(payload);
      onSuccess();
      onClose();
    } catch (err: any) {
      // Error handled by store
    }
  };

  const handleToggleDestUser = (userId: string) => {
    if (selectedDestUserIds.includes(userId)) {
      setSelectedDestUserIds(selectedDestUserIds.filter(id => id !== userId));
    } else {
      setSelectedDestUserIds([...selectedDestUserIds, userId]);
    }
  };

  const handleSelectAllDest = () => {
    const candidates = employees.filter(emp => emp.id !== sourceUserId);
    if (selectedDestUserIds.length === candidates.length) {
      setSelectedDestUserIds([]);
    } else {
      setSelectedDestUserIds(candidates.map(emp => emp.id));
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm transition-opacity" onClick={onClose}></div>

      {/* Modal Container */}
      <div className="relative w-full max-w-lg bg-[var(--bg-modal)] border border-[var(--border-color)] rounded-2xl shadow-2xl flex flex-col max-h-[90vh] z-10 overflow-hidden text-[var(--text-primary)]">
        {/* Header */}
        <div className="px-6 py-4.5 border-b border-[var(--border-color)] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/25 flex items-center justify-center">
              <ArrowRightLeft className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-[var(--text-primary)]">Transfer Leads</h3>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Reassign leads from a source owner to destination team members
              </p>
            </div>
          </div>
          <button 
            type="button"
            onClick={onClose} 
            className="p-1.5 border border-[var(--border-color)] hover:bg-[var(--bg-card-hover)] text-[var(--text-muted)] hover:text-[var(--text-primary)] rounded-xl transition-all cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Error Callout */}
        {(error || localError) && (
          <div className="mx-6 mt-4 p-3 bg-red-950/20 border border-red-900/30 text-red-400 rounded-xl flex items-start gap-2.5 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Error:</span> {localError || error}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Source User Dropdown */}
          <div className="space-y-1">
            <label className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block">Source Owner (From)</label>
            {isLoadingEmployees ? (
              <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] py-1">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Fetching team...
              </div>
            ) : (
              <select
                value={sourceUserId}
                onChange={(e) => {
                  setSourceUserId(e.target.value);
                  setSelectedDestUserIds(selectedDestUserIds.filter(id => id !== e.target.value));
                }}
                className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none focus:border-brand-500/40"
              >
                {/* Team Leaders can also select themselves */}
                {user && (
                  <option value={user.id}>
                    {user.first_name || ''} {user.last_name || ''} ({user.email}) [You]
                  </option>
                )}
                {employees
                  .filter(emp => emp.id !== user?.id)
                  .map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.first_name || ''} {emp.last_name || ''} ({emp.email})
                    </option>
                  ))}
              </select>
            )}
          </div>

          {/* Transfer Method */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Transfer Method</label>
            <div className="grid grid-cols-2 gap-3">
              <label 
                className={`p-3 border rounded-xl flex flex-col justify-between cursor-pointer transition-all ${
                  transferType === 'SELECTED' 
                    ? 'border-brand-500/50 bg-brand-500/5 text-[var(--text-primary)]' 
                    : 'border-[var(--border-color)] hover:border-[var(--border-strong)] bg-[var(--bg-subtle)] text-[var(--text-muted)]'
                }`}
              >
                <div className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="transferType"
                    value="SELECTED"
                    checked={transferType === 'SELECTED'}
                    disabled={selectedLeads.length === 0}
                    onChange={() => setTransferType('SELECTED')}
                    className="w-4 h-4 accent-brand-500 cursor-pointer disabled:opacity-50"
                  />
                  <span className="text-xs font-semibold">Selected Leads</span>
                </div>
                <span className="text-[10px] text-[var(--text-muted)] mt-1 block">
                  Transfer the selected ({matchingSelectedLeads.length}) leads owned by source.
                </span>
              </label>

              <label 
                className={`p-3 border rounded-xl flex flex-col justify-between cursor-pointer transition-all ${
                  transferType === 'QUANTITY' 
                    ? 'border-brand-500/50 bg-brand-500/5 text-[var(--text-primary)]' 
                    : 'border-[var(--border-color)] hover:border-[var(--border-strong)] bg-[var(--bg-subtle)] text-[var(--text-muted)]'
                }`}
              >
                <div className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="transferType"
                    value="QUANTITY"
                    checked={transferType === 'QUANTITY'}
                    onChange={() => setTransferType('QUANTITY')}
                    className="w-4 h-4 accent-brand-500 cursor-pointer"
                  />
                  <span className="text-xs font-semibold">By Quantity Count</span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Specify a number of leads to transfer.
                </span>
              </label>
            </div>
          </div>

          {/* Quantity Input */}
          {transferType === 'QUANTITY' && (
            <div className="p-4 bg-slate-950/30 border border-slate-800/80 rounded-xl space-y-2">
              <div className="flex items-center gap-2 text-xs text-brand-300 font-semibold mb-1">
                <Info className="w-3.5 h-3.5" />
                <span>Specify Lead Count</span>
              </div>
              <div className="space-y-1">
                <label className="text-[10px] text-[var(--text-muted)] font-semibold uppercase">Number of leads to transfer</label>
                <input
                  type="number"
                  min="1"
                  placeholder="e.g. 10"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value === '' ? '' : Number(e.target.value))}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none focus:border-brand-500/40"
                />
              </div>
            </div>
          )}

          {/* Destination Checklist */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Destination Assignees (To)</label>
              {employees.length > 1 && (
                <button
                  type="button"
                  onClick={handleSelectAllDest}
                  className="text-xs font-semibold text-brand-400 hover:text-brand-300 cursor-pointer"
                >
                  {selectedDestUserIds.length === employees.filter(emp => emp.id !== sourceUserId).length ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>

            {isLoadingEmployees ? (
              <div className="flex items-center justify-center py-8 text-[var(--text-muted)] text-xs gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-brand-500" />
                Loading assignees...
              </div>
            ) : employees.filter(emp => emp.id !== sourceUserId).length === 0 ? (
              <div className="p-4 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-center text-xs text-[var(--text-muted)]">
                No other team members available to receive leads.
              </div>
            ) : (
              <div className="border border-[var(--border-color)] rounded-xl max-h-48 overflow-y-auto divide-y divide-[var(--border-subtle)] bg-[var(--bg-subtle)] px-3 py-1">
                {employees
                  .filter(emp => emp.id !== sourceUserId)
                  .map((emp) => {
                    const isChecked = selectedDestUserIds.includes(emp.id);
                    return (
                      <label 
                        key={emp.id} 
                        className="flex items-center gap-2.5 py-2.5 cursor-pointer text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleToggleDestUser(emp.id)}
                          className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-input)] focus:ring-brand-500/20 cursor-pointer"
                        />
                        <div className="overflow-hidden">
                          <span className="font-semibold block">
                            {emp.first_name || ''} {emp.last_name || ''}
                          </span>
                          <span className="text-[10px] text-[var(--text-muted)] block">
                            {emp.email}
                          </span>
                        </div>
                      </label>
                    );
                  })}
              </div>
            )}
          </div>

          {/* Transfer Reason & Notes */}
          <div className="space-y-3 pt-1">
            <div className="space-y-1">
              <label className="text-[10px] text-[var(--text-muted)] font-semibold uppercase tracking-wider">Transfer Reason</label>
              <select
                value={transferReason}
                onChange={(e) => setTransferReason(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none focus:border-brand-500/40"
              >
                <option value="Territory Rebalance">Territory Rebalance / Workload Distribution</option>
                <option value="Agent On Leave">Agent On Leave / Absent</option>
                <option value="Escalation to Specialist">Escalation to Specialist / Senior Rep</option>
                <option value="Shift Handoff">Shift Handoff</option>
                <option value="Customer Preference">Customer Request / Preference</option>
                <option value="Other">Other Reason</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-[var(--text-muted)] font-semibold uppercase tracking-wider">Handoff Notes & Context</label>
              <textarea
                rows={2}
                placeholder="Add critical context, deal status, or caller instructions for the new agent..."
                value={transferNotes}
                onChange={(e) => setTransferNotes(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none focus:border-brand-500/40 resize-none"
              />
            </div>
          </div>

          {/* Footer Actions */}
          <div className="pt-4 border-t border-[var(--border-color)] flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-[var(--bg-card)] border border-[var(--border-color)] hover:bg-[var(--bg-card-hover)] rounded-xl text-xs font-semibold text-[var(--text-secondary)] transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || isLoadingEmployees || selectedDestUserIds.length === 0}
              className="flex items-center gap-1.5 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 rounded-xl text-xs font-semibold text-white transition-all shadow-md shadow-brand-500/10 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Transferring...
                </>
              ) : (
                <>
                  Confirm Transfer
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
export default LeadTransferModal;
