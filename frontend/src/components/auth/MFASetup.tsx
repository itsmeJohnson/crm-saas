/**
 * MFA Setup Component
 * Handles the full MFA lifecycle: setup, enable, disable, backup codes.
 * Embed this in any settings/profile page.
 */
import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  ShieldCheck, ShieldOff, Shield, Loader2, AlertCircle, CheckCircle,
  QrCode, Key, RefreshCw, Copy, Eye, EyeOff, X
} from 'lucide-react';

interface MFAStatus {
  mfa_enabled: boolean;
  backup_codes_remaining: number;
}

export const MFASetup: React.FC = () => {
  const [status, setStatus] = useState<MFAStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Setup flow state
  const [step, setStep] = useState<'idle' | 'setup' | 'enable' | 'disable' | 'backup-regen'>('idle');
  const [qrUri, setQrUri] = useState<string | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [totpCode, setTotpCode] = useState('');
  const [backupCode, setBackupCode] = useState('');
  const [useBackupForDisable, setUseBackupForDisable] = useState(false);
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Load MFA status
  const loadStatus = async () => {
    setLoading(true);
    try {
      const res = await api.get('/auth/mfa/status');
      setStatus(res.data);
    } catch {
      setError('Failed to load MFA status.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadStatus(); }, []);

  const clearMessages = () => { setError(null); setSuccess(null); };

  // ---------- SETUP: Generate QR ----------
  const handleSetup = async () => {
    clearMessages();
    setActionLoading(true);
    try {
      const res = await api.post('/auth/mfa/setup');
      setQrUri(res.data.qr_uri);
      setSecret(res.data.secret);
      setTotpCode('');
      setStep('setup');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate MFA setup.');
    } finally {
      setActionLoading(false);
    }
  };

  // ---------- ENABLE: Verify code ----------
  const handleEnable = async () => {
    if (totpCode.length !== 6) {
      setError('Enter the 6-digit code from your authenticator app.');
      return;
    }
    clearMessages();
    setActionLoading(true);
    try {
      const res = await api.post('/auth/mfa/enable', { totp_code: totpCode });
      setBackupCodes(res.data.backup_codes);
      setStep('enable');
      await loadStatus();
      setSuccess('MFA enabled! Save your backup codes below.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid code. Try again.');
    } finally {
      setActionLoading(false);
    }
  };

  // ---------- DISABLE: Verify + turn off ----------
  const handleDisable = async () => {
    clearMessages();
    setActionLoading(true);
    try {
      await api.post('/auth/mfa/disable', {
        totp_code: !useBackupForDisable ? (totpCode || undefined) : undefined,
        backup_code: useBackupForDisable ? (backupCode || undefined) : undefined,
      });
      setStep('idle');
      setTotpCode('');
      setBackupCode('');
      await loadStatus();
      setSuccess('MFA has been disabled.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid code. MFA not disabled.');
    } finally {
      setActionLoading(false);
    }
  };

  // ---------- REGEN backup codes ----------
  const handleRegenBackupCodes = async () => {
    if (totpCode.length !== 6) {
      setError('Enter your 6-digit authenticator code to regenerate backup codes.');
      return;
    }
    clearMessages();
    setActionLoading(true);
    try {
      const res = await api.post('/auth/mfa/backup-codes/regenerate', { totp_code: totpCode });
      setBackupCodes(res.data.backup_codes);
      setStep('backup-regen');
      setTotpCode('');
      await loadStatus();
      setSuccess('New backup codes generated. Old codes are now invalid.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to regenerate backup codes.');
    } finally {
      setActionLoading(false);
    }
  };

  const copyBackupCodes = () => {
    if (!backupCodes) return;
    navigator.clipboard.writeText(backupCodes.join('\n'));
    setSuccess('Backup codes copied to clipboard.');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-brand-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Status Banner */}
      <div className={`p-4 rounded-xl border flex items-start gap-3 ${
        status?.mfa_enabled
          ? 'bg-emerald-500/10 border-emerald-500/25'
          : 'bg-amber-500/10 border-amber-500/25'
      }`}>
        {status?.mfa_enabled
          ? <ShieldCheck className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" />
          : <ShieldOff className="w-5 h-5 text-amber-400 mt-0.5 flex-shrink-0" />
        }
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-semibold ${status?.mfa_enabled ? 'text-emerald-300' : 'text-amber-300'}`}>
            {status?.mfa_enabled ? 'MFA is Enabled' : 'MFA is Disabled'}
          </p>
          <p className={`text-xs mt-0.5 ${status?.mfa_enabled ? 'text-emerald-400/70' : 'text-amber-400/70'}`}>
            {status?.mfa_enabled
              ? `Your account is protected with two-factor authentication. ${status.backup_codes_remaining} backup code${status.backup_codes_remaining !== 1 ? 's' : ''} remaining.`
              : 'Enable MFA to secure your account with Google Authenticator.'}
          </p>
        </div>
      </div>

      {/* Alert Messages */}
      {error && (
        <div className="p-3.5 bg-red-500/10 border border-red-500/20 text-red-300 text-sm rounded-xl flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-red-400" />
          <p>{error}</p>
          <button onClick={() => setError(null)} className="ml-auto flex-shrink-0"><X className="w-4 h-4" /></button>
        </div>
      )}
      {success && (
        <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm rounded-xl flex items-start gap-2.5">
          <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-emerald-400" />
          <p>{success}</p>
          <button onClick={() => setSuccess(null)} className="ml-auto flex-shrink-0"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* ---- IDLE STATE ---- */}
      {step === 'idle' && (
        <div className="flex flex-wrap gap-3">
          {!status?.mfa_enabled ? (
            <button
              onClick={handleSetup}
              disabled={actionLoading}
              className="flex items-center gap-2 px-4 py-2.5 bg-brand-500 hover:bg-brand-600 text-white text-sm font-semibold rounded-xl transition-colors cursor-pointer disabled:opacity-50"
            >
              {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
              Set Up Authenticator App
            </button>
          ) : (
            <>
              <button
                onClick={() => { clearMessages(); setTotpCode(''); setStep('disable'); }}
                className="flex items-center gap-2 px-4 py-2.5 bg-red-500/15 hover:bg-red-500/25 border border-red-500/30 text-red-300 text-sm font-semibold rounded-xl transition-colors cursor-pointer"
              >
                <ShieldOff className="w-4 h-4" />
                Disable MFA
              </button>
              <button
                onClick={() => { clearMessages(); setTotpCode(''); setStep('backup-regen'); }}
                className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-sm font-semibold rounded-xl transition-colors cursor-pointer"
              >
                <RefreshCw className="w-4 h-4" />
                Regenerate Backup Codes
              </button>
            </>
          )}
        </div>
      )}

      {/* ---- SETUP: Show QR Code ---- */}
      {step === 'setup' && (
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <QrCode className="w-4 h-4 text-brand-400" />
              Step 1 — Scan QR Code
            </h4>
            <button onClick={() => { setStep('idle'); setQrUri(null); setSecret(null); }} className="text-slate-500 hover:text-slate-300 cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </div>

          <p className="text-xs text-slate-400">Open <strong className="text-slate-300">Google Authenticator</strong> and tap <strong className="text-slate-300">+</strong> → <em>Scan a QR code</em>, then scan the code below.</p>

          {/* QR Code via Google Charts (no external package needed) */}
          {qrUri && (
            <div className="flex justify-center">
              <div className="bg-white p-3 rounded-xl">
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(qrUri)}`}
                  alt="MFA QR Code"
                  width={180}
                  height={180}
                  className="block"
                />
              </div>
            </div>
          )}

          {/* Manual entry fallback */}
          <div>
            <p className="text-xs text-slate-500 mb-1.5">Can't scan? Enter this key manually:</p>
            <div className="flex items-center gap-2">
              <code className={`flex-1 text-xs font-mono bg-slate-900 border border-slate-700 px-3 py-2 rounded-lg text-slate-300 tracking-widest ${showSecret ? '' : 'blur-sm select-none'}`}>
                {secret}
              </code>
              <button
                type="button"
                onClick={() => setShowSecret(!showSecret)}
                className="p-2 text-slate-500 hover:text-slate-300 cursor-pointer"
              >
                {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div className="border-t border-slate-800 pt-4">
            <p className="text-xs text-slate-400 mb-2"><strong className="text-slate-300">Step 2 —</strong> Enter the 6-digit code shown in the app to verify and activate MFA:</p>
            <div className="flex gap-2">
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={totpCode}
                onChange={e => setTotpCode(e.target.value.replace(/\D/g, ''))}
                className="flex-1 px-4 py-2.5 rounded-xl glass-input font-mono tracking-[0.5em] text-center text-lg"
                placeholder="000000"
                autoFocus
              />
              <button
                onClick={handleEnable}
                disabled={actionLoading || totpCode.length !== 6}
                className="px-4 py-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors cursor-pointer flex items-center gap-1.5"
              >
                {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                Activate
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- ENABLE SUCCESS: Show backup codes ---- */}
      {(step === 'enable' || step === 'backup-regen') && backupCodes && (
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Key className="w-4 h-4 text-amber-400" />
              Backup Codes — Save These Now
            </h4>
            <button
              onClick={() => { setStep('idle'); setBackupCodes(null); }}
              className="text-slate-500 hover:text-slate-300 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="p-3 bg-amber-500/10 border border-amber-500/25 rounded-xl text-xs text-amber-300">
            ⚠️ Store these codes securely. Each code can only be used once. They cannot be retrieved again.
          </div>

          <div className="grid grid-cols-2 gap-2">
            {backupCodes.map((code, i) => (
              <div key={i} className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm text-slate-200 tracking-widest text-center">
                {code}
              </div>
            ))}
          </div>

          <button
            onClick={copyBackupCodes}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-sm font-semibold rounded-xl transition-colors cursor-pointer"
          >
            <Copy className="w-4 h-4" />
            Copy All Codes
          </button>

          <button
            onClick={() => { setStep('idle'); setBackupCodes(null); }}
            className="w-full px-4 py-2.5 bg-brand-500 hover:bg-brand-600 text-white text-sm font-semibold rounded-xl transition-colors cursor-pointer"
          >
            Done — I've Saved My Codes
          </button>
        </div>
      )}

      {/* ---- DISABLE ---- */}
      {step === 'disable' && (
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-red-300 flex items-center gap-2">
              <ShieldOff className="w-4 h-4" />
              Disable Two-Factor Authentication
            </h4>
            <button onClick={() => { setStep('idle'); setTotpCode(''); setBackupCode(''); }} className="text-slate-500 hover:text-slate-300 cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </div>

          <p className="text-xs text-slate-400">
            {useBackupForDisable
              ? 'Enter one of your backup codes to confirm disabling MFA.'
              : 'Enter your current authenticator code to confirm disabling MFA.'}
          </p>

          {!useBackupForDisable ? (
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={totpCode}
              onChange={e => setTotpCode(e.target.value.replace(/\D/g, ''))}
              className="w-full px-4 py-2.5 rounded-xl glass-input font-mono tracking-[0.5em] text-center text-lg"
              placeholder="000000"
              autoFocus
            />
          ) : (
            <input
              type="text"
              maxLength={8}
              value={backupCode}
              onChange={e => setBackupCode(e.target.value.toUpperCase())}
              className="w-full px-4 py-2.5 rounded-xl glass-input font-mono tracking-widest text-center text-lg uppercase"
              placeholder="AB12CD34"
              autoFocus
            />
          )}

          <div className="flex gap-2">
            <button
              onClick={handleDisable}
              disabled={actionLoading || (!useBackupForDisable && totpCode.length !== 6) || (useBackupForDisable && backupCode.length !== 8)}
              className="flex-1 py-2.5 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-300 text-sm font-semibold rounded-xl transition-colors cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldOff className="w-4 h-4" />}
              Disable MFA
            </button>
          </div>

          <div className="text-center">
            <button
              type="button"
              onClick={() => { setUseBackupForDisable(!useBackupForDisable); setTotpCode(''); setBackupCode(''); }}
              className="text-brand-400 hover:text-brand-300 text-xs font-semibold cursor-pointer"
            >
              {useBackupForDisable ? 'Use Authenticator Code Instead' : 'Use a Backup Code Instead'}
            </button>
          </div>
        </div>
      )}

      {/* ---- BACKUP CODE REGEN: Enter TOTP to confirm ---- */}
      {step === 'backup-regen' && !backupCodes && (
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <RefreshCw className="w-4 h-4 text-amber-400" />
              Regenerate Backup Codes
            </h4>
            <button onClick={() => { setStep('idle'); setTotpCode(''); }} className="text-slate-500 hover:text-slate-300 cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </div>

          <p className="text-xs text-slate-400">Enter your current authenticator code to generate 10 new backup codes. Old codes will be permanently invalidated.</p>

          <div className="flex gap-2">
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={totpCode}
              onChange={e => setTotpCode(e.target.value.replace(/\D/g, ''))}
              className="flex-1 px-4 py-2.5 rounded-xl glass-input font-mono tracking-[0.5em] text-center text-lg"
              placeholder="000000"
              autoFocus
            />
            <button
              onClick={handleRegenBackupCodes}
              disabled={actionLoading || totpCode.length !== 6}
              className="px-4 py-2.5 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/30 text-amber-300 text-sm font-semibold rounded-xl transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
            >
              {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Generate
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
