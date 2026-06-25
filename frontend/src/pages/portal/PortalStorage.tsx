import React, { useState, useEffect } from 'react';
import { portalApi } from '../../services/portalApi';
import {
  HardDrive, Plus, CreditCard, Loader2, CheckCircle2,
  AlertTriangle, 
} from 'lucide-react';

export const PortalStorage: React.FC = () => {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Storage purchase modal
  const [showModal, setShowModal] = useState(false);
  const [storageGb, setStorageGb] = useState(10);
  const [selectedGateway, setSelectedGateway] = useState('UPI');
  const [purchasing, setPurchasing] = useState(false);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const data = await portalApi.getStats();
      setStats(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load storage statistics.");
    } finally {
      setLoading(false);
    }
  };

  const handlePurchaseStorage = async () => {
    try {
      setPurchasing(true);
      setError(null);
      setSuccess(null);

      // 1. Generate Invoice
      const invoice = await portalApi.buyExtraStorage({
        storage_gb: storageGb,
        gateway: selectedGateway
      });

      // 2. Pay immediately via simulated transaction ID
      await portalApi.payInvoice(invoice.id, {
        gateway: selectedGateway,
        transaction_id: `TXN-STORAGE-${Math.random().toString(36).substring(2, 14).toUpperCase()}`
      });

      setSuccess(`Successfully purchased ${storageGb} GB extra storage! Your boundary limits are updated.`);
      setShowModal(false);
      fetchStats();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to complete storage purchase.");
    } finally {
      setPurchasing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  const storage = stats?.storage;
  const usedGb = storage?.used_gb || 0;
  const limitGb = storage?.limit_gb || 10;
  const percent = storage?.percent || 0;

  // Split calculations
  const voiceRecordingsGb = usedGb * 0.7;
  const leadDataGb = usedGb * 0.2;
  const documentFilesGb = usedGb * 0.1;

  return (
    <div className="space-y-8 text-left max-w-4xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
            Storage Allocations & Limits
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Audit cloud storage volumes, trace call recordings capacity, and buy additional GB space instantly.
          </p>
        </div>
        <button
          onClick={() => {
            setSuccess(null);
            setShowModal(true);
          }}
          className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10"
        >
          <Plus className="w-3.5 h-3.5" />
          Buy Storage Capacity
        </button>
      </div>

      {success && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {success}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Storage usage meter card */}
        <div className="md:col-span-2 space-y-6">
          <div className="glass-panel border border-slate-900 rounded-2xl p-6 text-left space-y-6">
            <div>
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Active Boundary</span>
              <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2 mt-1">
                <HardDrive className="w-5 h-5 text-indigo-400" />
                {usedGb.toFixed(2)} GB / {limitGb} GB Allocated
              </h3>
            </div>

            {/* Progress bar */}
            <div className="space-y-2">
              <div className="w-full bg-slate-900 h-4 rounded-full overflow-hidden flex">
                <div
                  className="bg-indigo-500 h-full transition-all"
                  style={{ width: `${(voiceRecordingsGb / limitGb) * 100}%` }}
                  title="Voice Recordings"
                ></div>
                <div
                  className="bg-purple-500 h-full transition-all"
                  style={{ width: `${(leadDataGb / limitGb) * 100}%` }}
                  title="Leads Database"
                ></div>
                <div
                  className="bg-emerald-500 h-full transition-all"
                  style={{ width: `${(documentFilesGb / limitGb) * 100}%` }}
                  title="System Logs & Audits"
                ></div>
              </div>

              <div className="flex justify-between items-center text-[10px] text-slate-500">
                <span>{percent.toFixed(1)}% Consumed</span>
                <span>{(limitGb - usedGb).toFixed(2)} GB Free Space</span>
              </div>
            </div>

            {/* Legend split */}
            <div className="grid grid-cols-3 gap-4 text-xs pt-4 border-t border-slate-900">
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-slate-400">
                  <div className="w-2.5 h-2.5 bg-indigo-500 rounded"></div>
                  <span>Voice Calls</span>
                </div>
                <p className="text-slate-100 font-bold font-mono">{voiceRecordingsGb.toFixed(2)} GB</p>
              </div>

              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-slate-400">
                  <div className="w-2.5 h-2.5 bg-purple-500 rounded"></div>
                  <span>Leads Info</span>
                </div>
                <p className="text-slate-100 font-bold font-mono">{leadDataGb.toFixed(2)} GB</p>
              </div>

              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-slate-400">
                  <div className="w-2.5 h-2.5 bg-emerald-500 rounded"></div>
                  <span>System Logs</span>
                </div>
                <p className="text-slate-100 font-bold font-mono">{documentFilesGb.toFixed(2)} GB</p>
              </div>
            </div>
          </div>
        </div>

        {/* Pricing sidebar info card */}
        <div className="md:col-span-1">
          <div className="glass-panel border border-slate-900 rounded-2xl p-6 bg-slate-950/60 space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Storage Rates</h4>
            <p className="text-[10px] text-slate-500 mt-1">Scale space dynamic configurations</p>
            
            <div className="p-3.5 bg-slate-900/50 rounded-xl space-y-1 text-xs border border-slate-900">
              <span className="text-slate-500">Storage Unit Rate:</span>
              <strong className="block text-slate-200 font-mono text-sm mt-0.5">₹10.00 / GB / month</strong>
            </div>

            <div className="text-[10px] text-slate-500 leading-relaxed">
              * Extra purchased storage spaces remain active alongside subscription billing cycles.
            </div>
          </div>
        </div>
      </div>

      {/* Buy Storage modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <div className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-6 bg-slate-950">
            <div>
              <h3 className="text-lg font-bold text-slate-100">Add Extra Storage</h3>
              <p className="text-xs text-slate-500 mt-1">
                Select required extra GB size. Storage bounds upgrade instantly upon transaction completion.
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                  GB Capacity: {storageGb} GB
                </label>
                <input
                  type="range"
                  min="5"
                  max="200"
                  step="5"
                  value={storageGb}
                  onChange={(e) => setStorageGb(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-brand-500 focus:outline-none"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1.5 font-bold">
                  <span>5 GB</span>
                  <span>100 GB</span>
                  <span>200 GB</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Payment Gateway</label>
                <select
                  value={selectedGateway}
                  onChange={(e) => setSelectedGateway(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                >
                  <option value="UPI">UPI / Instant QR</option>
                  <option value="Stripe">Stripe Checkout</option>
                  <option value="Razorpay">Razorpay Gateway</option>
                  <option value="PhonePe">PhonePe Portal</option>
                  <option value="Bank">Direct Bank Transfer</option>
                </select>
              </div>

              <div className="p-4 bg-slate-900/50 rounded-xl space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Unit Price:</span>
                  <span className="font-mono text-slate-300">₹10.00 / GB</span>
                </div>
                <div className="flex justify-between border-t border-slate-800/80 pt-2 font-bold text-sm">
                  <span className="text-slate-400">Total + Tax (18% GST):</span>
                  <span className="text-slate-100">₹{(storageGb * 10.0 * 1.18).toFixed(2)}</span>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handlePurchaseStorage}
                disabled={purchasing}
                className="flex items-center justify-center gap-1.5 px-6 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold"
              >
                {purchasing ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <>
                    <CreditCard className="w-3.5 h-3.5" />
                    Pay & Process
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
