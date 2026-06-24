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
  const [localError, setLocalError] = useState<string | null>(null);

  // Fetch employees/downlines reporting to current user
  useEffect(() => {
    if (isOpen) {
      setSourceUserId(user?.id || '');
      setSelectedDestUserIds([]);
      setTransferType(selectedLeads.length > 0 ? 'SELECTED' : 'QUANTITY');
      setQuantity('');
      setLocalError(null);

      const fetchEmployees = async () => {
        setIsLoadingEmployees(true);
        try {
          // If Team Leader, this endpoint will return only their downlines
          const data = await userApi.getUsers({ limit: 100, role: 'Employee', is_active: true });
          setEmployees(data);
        } catch (err) {
          console.error('Failed to fetch employees', err);
        } finally {
          setIsLoadingEmployees(false);
        }
      };

      const isTL = useAnalyticsStore.getState().dashboardData?.role === 'TeamLeader';
      if (user && (user.role === 'OrgAdmin' || user.role === 'Manager' || isTL)) {
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
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800/80 rounded-2xl shadow-2xl flex flex-col max-h-[90vh] z-10 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4.5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/25 flex items-center justify-center">
              <ArrowRightLeft className="w-5 h-5 text-brand-300" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-100">Transfer Leads</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Reassign leads from a source owner to destination team members
              </p>
            </div>
          </div>
          <button 
            type="button"
            onClick={onClose} 
            className="p-1.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-950/50 text-slate-400 hover:text-slate-200 rounded-xl transition-all cursor-pointer"
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
            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider block">Source Owner (From)</label>
            {isLoadingEmployees ? (
              <div className="flex items-center gap-2 text-xs text-slate-500 py-1">
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
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-brand-500/40"
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
            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Transfer Method</label>
            <div className="grid grid-cols-2 gap-3">
              <label 
                className={`p-3 border rounded-xl flex flex-col justify-between cursor-pointer transition-all ${
                  transferType === 'SELECTED' 
                    ? 'border-brand-500/50 bg-brand-500/5 text-slate-200' 
                    : 'border-slate-800 hover:border-slate-700 bg-slate-950/20 text-slate-400'
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
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Transfer the selected ({matchingSelectedLeads.length}) leads owned by source.
                </span>
              </label>

              <label 
                className={`p-3 border rounded-xl flex flex-col justify-between cursor-pointer transition-all ${
                  transferType === 'QUANTITY' 
                    ? 'border-brand-500/50 bg-brand-500/5 text-slate-200' 
                    : 'border-slate-800 hover:border-slate-700 bg-slate-950/20 text-slate-400'
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
                <label className="text-[10px] text-slate-500 font-semibold uppercase">Number of leads to transfer</label>
                <input
                  type="number"
                  min="1"
                  placeholder="e.g. 10"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value === '' ? '' : Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-brand-500/40"
                />
              </div>
            </div>
          )}

          {/* Destination Checklist */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Destination Assignees (To)</label>
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
              <div className="flex items-center justify-center py-8 text-slate-500 text-xs gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-brand-500" />
                Loading assignees...
              </div>
            ) : employees.filter(emp => emp.id !== sourceUserId).length === 0 ? (
              <div className="p-4 bg-slate-950/20 border border-slate-800 rounded-xl text-center text-xs text-slate-500">
                No other team members available to receive leads.
              </div>
            ) : (
              <div className="border border-slate-800 rounded-xl max-h-48 overflow-y-auto divide-y divide-slate-850 bg-slate-950/20 px-3 py-1">
                {employees
                  .filter(emp => emp.id !== sourceUserId)
                  .map((emp) => {
                    const isChecked = selectedDestUserIds.includes(emp.id);
                    return (
                      <label 
                        key={emp.id} 
                        className="flex items-center gap-2.5 py-2.5 cursor-pointer text-xs text-slate-300 hover:text-slate-100 transition-colors"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleToggleDestUser(emp.id)}
                          className="w-4 h-4 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-brand-500/20 cursor-pointer"
                        />
                        <div className="overflow-hidden">
                          <span className="font-semibold block">
                            {emp.first_name || ''} {emp.last_name || ''}
                          </span>
                          <span className="text-[10px] text-slate-500 block">
                            {emp.email}
                          </span>
                        </div>
                      </label>
                    );
                  })}
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="pt-4 border-t border-slate-800 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-900/80 active:bg-slate-900/60 rounded-xl text-xs font-semibold text-slate-300 transition-all cursor-pointer"
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
