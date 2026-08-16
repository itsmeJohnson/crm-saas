import React, { useEffect, useState } from 'react';
import {
  Settings as SettingsIcon, Loader2, Check, RefreshCw, Zap, Trash2, Plus, AlertTriangle, Play,
  Shield, Wifi, Phone, CheckCircle2, Edit2, AlertCircle, Laptop, X, Heart, Activity, ShieldCheck, Clock
} from 'lucide-react';
import { whatsappApi, WaSettings, QuickReply } from '../services/whatsappApi';
import { extractErrorMessage } from '../utils/errors';

const DiagnosticIndicator: React.FC<{ label: string; status: 'green' | 'yellow' | 'red' | string }> = ({ label, status }) => {
  const colorClass = 
    status === 'green' ? 'bg-emerald-500 shadow-emerald-500/50' : 
    status === 'yellow' ? 'bg-amber-500 shadow-amber-500/50' : 'bg-rose-500 shadow-rose-500/50';
  return (
    <div className="flex items-center justify-between p-3 bg-slate-900/40 border border-slate-800/80 rounded-xl">
      <span className="text-xs text-slate-300 font-medium">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-[10px] uppercase font-bold text-slate-400">{status}</span>
        <span className={`w-3 h-3 rounded-full shadow-sm animate-pulse ${colorClass}`} />
      </div>
    </div>
  );
};

export const WhatsAppSettingsPage: React.FC = () => {
  const [settingsList, setSettingsList] = useState<WaSettings[]>([]);
  const [activeSettings, setActiveSettings] = useState<WaSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Quick replies & Auto-reply state
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [qrShortcut, setQrShortcut] = useState('');
  const [qrText, setQrText] = useState('');

  // Renaming state
  const [isEditingName, setIsEditingName] = useState(false);
  const [newName, setNewName] = useState('');

  // Diagnostics and troubleshooting state
  const [diagnostics, setDiagnostics] = useState<Record<string, string> | null>(null);
  const [checkingDiagnostics, setCheckingDiagnostics] = useState(false);

  // Health Dashboard state (PART 8)
  const [activeTab, setActiveTab] = useState<'settings' | 'health'>('settings');
  const [dashboardMetrics, setDashboardMetrics] = useState<any | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  // Onboarding Wizard state
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [showOAuthPopup, setShowOAuthPopup] = useState(false);
  const [oauthLoading, setOauthLoading] = useState(false);
  const [discoveredNumbers, setDiscoveredNumbers] = useState<WaSettings[]>([]);
  const [selectedDefaultId, setSelectedDefaultId] = useState<string>('');
  const [, setWebhookVerifying] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const list = await whatsappApi.listSettings();
      // Filter out deleted ones just in case
      const activeList = list.filter(s => !s.is_active || s.is_active);
      setSettingsList(activeList);
      
      if (activeList.length > 0) {
        const defaultSet = activeList.find(s => s.is_default) || activeList[0];
        setActiveSettings(defaultSet);
        await runDiagnosticsFor(defaultSet.id);
      } else {
        // Automatically launch onboarding if no active number configs exist
        setWizardOpen(true);
        setWizardStep(1);
      }
      
      const qrs = await whatsappApi.listQuickReplies();
      setQuickReplies(qrs);
    } catch (err: any) {
      setErrorMsg(extractErrorMessage(err, 'Failed to load configurations'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadMetrics = async () => {
    setLoadingMetrics(true);
    try {
      const data = await whatsappApi.getDashboardMetrics();
      setDashboardMetrics(data);
    } catch (err: any) {
      setErrorMsg(extractErrorMessage(err, 'Failed to load monitoring metrics'));
    } finally {
      setLoadingMetrics(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'health') {
      loadMetrics();
    }
  }, [activeTab]);

  const selectSettings = async (s: WaSettings) => {
    setActiveSettings(s);
    setDiagnostics(null);
    setMsg(null);
    setErrorMsg(null);
    await runDiagnosticsFor(s.id);
  };

  const runDiagnosticsFor = async (id: string) => {
    setCheckingDiagnostics(true);
    try {
      const diag = await whatsappApi.getDiagnostics(id);
      setDiagnostics(diag);
    } catch {
      setDiagnostics({
        webhook_reachable: 'red',
        token_valid: 'red',
        phone_verified: 'red',
        graph_api_reachable: 'red',
        template_sync: 'red',
      });
    } finally {
      setCheckingDiagnostics(false);
    }
  };

  const handleManualSync = async () => {
    if (!activeSettings) return;
    setSaving(true); setMsg(null); setErrorMsg(null);
    try {
      const res = await whatsappApi.refreshMetadata(activeSettings.id);
      if (res.status === 'success') {
        setMsg('Successfully synchronized message templates and details.');
        // Reload list to get updated metadata
        const list = await whatsappApi.listSettings();
        setSettingsList(list);
        const updated = list.find(s => s.id === activeSettings.id);
        if (updated) setActiveSettings(updated);
        await runDiagnosticsFor(activeSettings.id);
      } else {
        setErrorMsg(res.reason || 'Sync failed.');
      }
    } catch (err: any) {
      setErrorMsg(extractErrorMessage(err, 'Manual synchronization failed.'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAutoReply = async () => {
    if (!activeSettings) return;
    setSaving(true); setMsg(null); setErrorMsg(null);
    try {
      const updated = await whatsappApi.updateSettings(activeSettings.id, {
        auto_reply_enabled: activeSettings.auto_reply_enabled,
        auto_reply_message: activeSettings.auto_reply_message,
      });
      setActiveSettings(updated);
      setSettingsList(prev => prev.map(s => s.id === updated.id ? updated : s));
      setMsg('Auto-responder configuration saved successfully.');
    } catch (err: any) {
      setErrorMsg(extractErrorMessage(err, 'Failed to save auto-responder'));
    } finally {
      setSaving(false);
    }
  };

  const handleRenameNumber = async () => {
    if (!activeSettings || !newName.trim()) return;
    setSaving(true); setErrorMsg(null);
    try {
      const updated = await whatsappApi.updateSettings(activeSettings.id, {
        friendly_name: newName.trim(),
      });
      setActiveSettings(updated);
      setSettingsList(prev => prev.map(s => s.id === updated.id ? updated : s));
      setIsEditingName(false);
      setMsg('Line description updated successfully.');
    } catch (err: any) {
      setErrorMsg(extractErrorMessage(err, 'Failed to rename line'));
    } finally {
      setSaving(false);
    }
  };

  const handleSetDefault = async (id: string) => {
    setSaving(true); setErrorMsg(null);
    try {
      await whatsappApi.updateSettings(id, { is_default: true });
      // Reload list to apply defaults
      const list = await whatsappApi.listSettings();
      setSettingsList(list);
      const active = list.find(s => s.id === id);
      if (active) setActiveSettings(active);
      setMsg('Default outbound phone number updated.');
    } catch (err: any) {
      setErrorMsg(extractErrorMessage(err, 'Failed to update default number'));
    } finally {
      setSaving(false);
    }
  };

  const handleArchiveNumber = async (id: string) => {
    if (!window.confirm('Are you sure you want to disconnect and archive this WhatsApp number? You will no longer receive or send messages from it.')) return;
    setSaving(true); setErrorMsg(null);
    try {
      await whatsappApi.deleteSettings(id);
      const list = await whatsappApi.listSettings();
      setSettingsList(list);
      if (list.length > 0) {
        setActiveSettings(list[0]);
        await runDiagnosticsFor(list[0].id);
      } else {
        setActiveSettings(null);
        setWizardOpen(true);
        setWizardStep(1);
      }
      setMsg('WhatsApp number disconnected and archived.');
    } catch (err: any) {
      setErrorMsg(extractErrorMessage(err, 'Failed to archive configuration'));
    } finally {
      setSaving(false);
    }
  };

  // Quick Replies Manager
  const addQuickReply = async () => {
    if (!qrShortcut.trim() || !qrText.trim()) return;
    try {
      const qr = await whatsappApi.createQuickReply({ shortcut: qrShortcut.trim(), text: qrText.trim() });
      setQuickReplies(p => [...p, qr]);
      setQrShortcut(''); setQrText('');
    } catch { /* ignore */ }
  };

  const removeQuickReply = async (id: string) => {
    try {
      await whatsappApi.deleteQuickReply(id);
      setQuickReplies(p => p.filter(q => q.id !== id));
    } catch { /* ignore */ }
  };

  // Simulated Onboarding Wizard flow calls
  const handleLaunchMetaSignup = () => {
    setShowOAuthPopup(true);
  };

  const handleSimulateOAuthSuccess = async () => {
    setOauthLoading(true);
    try {
      // Simulate OAuth exchange with mock code
      const redirectUri = window.location.origin + '/whatsapp/settings';
      const settingsCreated = await whatsappApi.exchangeSignupOAuth('mock_signup_code_' + Math.random().toString(36).substring(7), redirectUri);
      setDiscoveredNumbers(settingsCreated);
      if (settingsCreated.length > 0) {
        setSelectedDefaultId(settingsCreated[0].id);
      }
      setShowOAuthPopup(false);
      setWizardStep(2); // Phone numbers found step
    } catch (err: any) {
      alert('OAuth simulation failed: ' + err.message);
    } finally {
      setOauthLoading(false);
    }
  };

  const handleConfirmDiscoveredNumbers = () => {
    setWizardStep(3); // Choose default number step
  };

  const handleConfirmDefaultNumber = async () => {
    setWizardStep(4); // Webhook verification step
    setWebhookVerifying(true);
    
    // Simulate webhook handshake verification
    setTimeout(async () => {
      try {
        // Set selected default
        if (selectedDefaultId) {
          await whatsappApi.updateSettings(selectedDefaultId, { is_default: true });
        }
        setWebhookVerifying(false);
        setWizardStep(5); // Success step
      } catch {
        setWebhookVerifying(false);
        setWizardStep(5);
      }
    }, 2500);
  };

  const handleExitWizard = async () => {
    setWizardOpen(false);
    await loadData();
  };

  // Troubleshooting Alerts mapping (PART 9)
  const getTroubleshootingAdvice = () => {
    if (!diagnostics || !activeSettings) return null;
    
    const advices = [];
    if (diagnostics.token_valid === 'red' || activeSettings.health_status === 'expired_token') {
      advices.push({
        title: 'Meta Access Token Expired',
        desc: 'Your security handshake credentials with Meta have expired. Click "Reconnect" to sign back in with your Facebook account and refresh permissions.'
      });
    }
    if (diagnostics.webhook_reachable === 'red') {
      advices.push({
        title: 'Webhook Handshake Broken',
        desc: 'Johnson CRM is not receiving webhook events. Please verify that your system is exposed to the internet with HTTPS, or run diagnostic sync.'
      });
    }
    if (diagnostics.phone_verified === 'red') {
      advices.push({
        title: 'Phone Number Pending Approval',
        desc: 'Your display name or phone verification is pending/rejected on Meta. Log in to Meta Business Suite to verify display name approvals and compliance.'
      });
    }
    if (activeSettings.quality_rating === 'RED' || activeSettings.quality_rating === 'YELLOW') {
      advices.push({
        title: 'WhatsApp quality rating is low',
        desc: 'Avoid mass message broadcasts that trigger spam reports. Focus on messaging only opt-in clients and verify your template contents align with WhatsApp guidelines.'
      });
    }
    
    return advices;
  };

  const troubleshootingAdvices = getTroubleshootingAdvice();

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-slate-400">
        <Loader2 className="w-10 h-10 animate-spin text-emerald-400 mb-4" />
        <p className="text-sm font-semibold tracking-wide">Loading WhatsApp Workspace...</p>
      </div>
    );
  }

  // Render Wizard View (PART 1 & 3)
  if (wizardOpen) {
    return (
      <div className="max-w-xl mx-auto py-10 px-4">
        {/* Wizard Header Progress */}
        <div className="mb-8">
          <div className="flex justify-between items-center text-xs font-semibold text-slate-450 uppercase tracking-widest mb-3">
            <span>WhatsApp Connection Wizard</span>
            <span>Step {wizardStep} of 5</span>
          </div>
          <div className="h-1.5 w-full bg-slate-900 rounded-full overflow-hidden flex">
            {[1, 2, 3, 4, 5].map((step) => (
              <div
                key={step}
                className={`h-full flex-1 transition-all duration-300 ${
                  wizardStep >= step ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : 'bg-transparent'
                } ${step > 1 ? 'border-l border-slate-950' : ''}`}
              />
            ))}
          </div>
        </div>

        {/* Wizard Card Body */}
        <div className="glass-panel border border-slate-800/80 rounded-2xl p-8 space-y-6">
          {/* STEP 1: AUTHORIZE */}
          {wizardStep === 1 && (
            <div className="space-y-6 text-center">
              <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto shadow-md">
                <Shield className="w-8 h-8" />
              </div>
              <div className="space-y-2">
                <h2 className="text-xl font-bold text-slate-100">Authorize Meta Business</h2>
                <p className="text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
                  Link your Facebook Business account to import your registered WhatsApp Business numbers. All API keys, IDs, and tokens will configure automatically.
                </p>
              </div>
              <button
                onClick={handleLaunchMetaSignup}
                className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-450 text-white font-bold py-3.5 px-6 rounded-xl text-sm transition shadow-lg cursor-pointer"
              >
                <Laptop className="w-4 h-4" /> Connect with Meta
              </button>
            </div>
          )}

          {/* STEP 2: PHONE NUMBERS DISCOVERED */}
          {wizardStep === 2 && (
            <div className="space-y-6">
              <div className="text-center space-y-2">
                <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto shadow-md">
                  <Phone className="w-8 h-8" />
                </div>
                <h2 className="text-xl font-bold text-slate-100">Discovered Phone Lines</h2>
                <p className="text-sm text-slate-400">
                  The following phone numbers were found under your WhatsApp Business account.
                </p>
              </div>

              <div className="space-y-3">
                {discoveredNumbers.map((phone) => (
                  <div key={phone.id} className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl flex items-center justify-between">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-200">{phone.friendly_name || 'Primary WhatsApp Line'}</p>
                      <p className="text-xs text-slate-500 font-mono mt-0.5">{phone.sender_number}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase">
                        {phone.quality_rating || 'GREEN'}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-850 text-slate-400 uppercase">
                        {phone.messaging_limit || 'TIER_1K'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <button
                onClick={handleConfirmDiscoveredNumbers}
                className="w-full bg-slate-800 hover:bg-slate-700/80 border border-slate-700/60 text-slate-200 font-bold py-3 px-6 rounded-xl text-sm transition cursor-pointer"
              >
                Verify & Proceed
              </button>
            </div>
          )}

          {/* STEP 3: CHOOSE DEFAULT NUMBER */}
          {wizardStep === 3 && (
            <div className="space-y-6">
              <div className="text-center space-y-2">
                <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto shadow-md">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <h2 className="text-xl font-bold text-slate-100">Set Default Outbound Line</h2>
                <p className="text-sm text-slate-400">
                  Select which number to use as the default channel for outbound messaging.
                </p>
              </div>

              <div className="space-y-3">
                {discoveredNumbers.map((phone) => (
                  <label
                    key={phone.id}
                    className={`block p-4 border rounded-xl cursor-pointer transition ${
                      selectedDefaultId === phone.id
                        ? 'bg-emerald-500/5 border-emerald-500/30'
                        : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-200">{phone.friendly_name || 'WhatsApp Line'}</p>
                        <p className="text-xs text-slate-500 mt-0.5 font-mono">{phone.sender_number}</p>
                      </div>
                      <input
                        type="radio"
                        name="default_line"
                        checked={selectedDefaultId === phone.id}
                        onChange={() => setSelectedDefaultId(phone.id)}
                        className="w-4 h-4 text-emerald-500 border-slate-700 bg-slate-800 focus:ring-emerald-500 cursor-pointer"
                      />
                    </div>
                  </label>
                ))}
              </div>

              <button
                onClick={handleConfirmDefaultNumber}
                className="w-full bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-450 text-white font-bold py-3.5 px-6 rounded-xl text-sm transition shadow-lg cursor-pointer"
              >
                Confirm default number
              </button>
            </div>
          )}

          {/* STEP 4: WEBHOOK VERIFICATION */}
          {wizardStep === 4 && (
            <div className="space-y-6 text-center py-4">
              <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto shadow-md">
                <Wifi className="w-8 h-8" />
              </div>
              <div className="space-y-3">
                <h2 className="text-xl font-bold text-slate-100">Securing Webhook Link</h2>
                <p className="text-sm text-slate-400 max-w-sm mx-auto leading-relaxed">
                  Configuring real-time subscriptions and performing handshake verification checks...
                </p>
              </div>
              <div className="flex items-center justify-center gap-3 text-xs text-slate-400 mt-6 bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                <Loader2 className="w-4 h-4 animate-spin text-teal-400" />
                <span>Validating callback tokens...</span>
              </div>
            </div>
          )}

          {/* STEP 5: COMPLETED */}
          {wizardStep === 5 && (
            <div className="space-y-6 text-center">
              <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto shadow-md">
                <Check className="w-10 h-10" />
              </div>
              <div className="space-y-2">
                <h2 className="text-xl font-bold text-slate-100">Connection Ready!</h2>
                <p className="text-sm text-slate-400 max-w-md mx-auto">
                  Your WhatsApp Business integrations have configured automatically. Templates and webhooks are active.
                </p>
              </div>
              <button
                onClick={handleExitWizard}
                className="w-full bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-450 text-white font-bold py-3.5 px-6 rounded-xl text-sm transition shadow-lg cursor-pointer"
              >
                Go to Dashboard
              </button>
            </div>
          )}
        </div>

        {/* Simulated OAuth Modal Overlay */}
        {showOAuthPopup && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full overflow-hidden shadow-2xl animate-in fade-in duration-200">
              <div className="bg-slate-950 px-4 py-3 border-b border-slate-800/80 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-rose-500 rounded-full" />
                  <div className="w-3 h-3 bg-amber-500 rounded-full" />
                  <div className="w-3 h-3 bg-emerald-500 rounded-full" />
                  <span className="text-xs text-slate-400 font-mono ml-2">facebook.com/oauth</span>
                </div>
                <button onClick={() => setShowOAuthPopup(false)} className="text-slate-450 hover:text-slate-205 cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-6 space-y-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white font-black text-xl">f</div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-100">Log in with Facebook</h4>
                    <p className="text-[11px] text-slate-400">Secure authorization for Johnson Softwares</p>
                  </div>
                </div>
                <div className="p-4 bg-slate-950/40 border border-slate-850 rounded-xl text-xs text-slate-350 leading-relaxed">
                  Johnson CRM will discover your Business Accounts, phone lines, display names, and capabilities automatically.
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowOAuthPopup(false)}
                    className="flex-1 bg-slate-850 hover:bg-slate-800 border border-slate-800 text-slate-300 py-2.5 rounded-xl text-xs font-semibold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSimulateOAuthSuccess}
                    disabled={oauthLoading}
                    className="flex-1 bg-indigo-600 hover:bg-indigo-550 text-white py-2.5 rounded-xl text-xs font-semibold flex items-center justify-center gap-1 cursor-pointer"
                  >
                    {oauthLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Grant Permissions'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Render Dashboard View (PART 4, 5, 7, 9)
  return (
    <div className="space-y-6 max-w-5xl pb-16">
      {/* Header */}
      <div className="border-b border-slate-800/60 pb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <SettingsIcon className="w-7 h-7 text-emerald-400" /> WhatsApp Settings
          </h1>
          <p className="text-sm text-slate-400 mt-1">Manage outbound business numbers, auto-replies, webhooks, and diagnostic health.</p>
        </div>
        <button
          onClick={() => { setDiscoveredNumbers([]); setWizardOpen(true); setWizardStep(1); }}
          className="inline-flex items-center gap-1.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-450 hover:to-teal-450 text-white py-2.5 px-4 rounded-xl text-sm font-semibold shadow-md transition cursor-pointer"
        >
          <Plus className="w-4 h-4" /> Connect WhatsApp
        </button>
      </div>

      {msg && (
        <div className="p-4 bg-emerald-950/20 border border-emerald-800/40 text-emerald-300 rounded-2xl text-sm flex items-center gap-3 animate-in fade-in">
          <Check className="w-5 h-5 shrink-0 text-emerald-400" />
          <span>{msg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 bg-rose-950/20 border border-rose-800/40 text-rose-300 rounded-2xl text-sm flex items-center justify-between gap-3 animate-in fade-in">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 text-rose-400" />
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-rose-400 hover:text-rose-200"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Tab Switcher */}
      <div className="flex border-b border-slate-800/60 gap-4 mb-4">
        <button
          onClick={() => setActiveTab('settings')}
          className={`pb-3 text-sm font-semibold border-b-2 transition ${
            activeTab === 'settings' ? 'border-emerald-500 text-slate-100' : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Numbers & Configuration
        </button>
        <button
          onClick={() => setActiveTab('health')}
          className={`pb-3 text-sm font-semibold border-b-2 transition ${
            activeTab === 'health' ? 'border-emerald-500 text-slate-100' : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Health Dashboard
        </button>
      </div>

      {activeTab === 'settings' && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Business Account Manager (PART 5) */}
        <div className="space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 px-1">Registered Numbers</h3>
          
          <div className="space-y-3">
            {settingsList.map((s) => (
              <div
                key={s.id}
                onClick={() => selectSettings(s)}
                className={`p-4 border rounded-2xl transition cursor-pointer flex flex-col gap-2 relative ${
                  activeSettings?.id === s.id
                    ? 'bg-slate-900/60 border-emerald-500/40 text-slate-100 shadow-md'
                    : 'bg-slate-950/20 border-slate-800/80 text-slate-400 hover:border-slate-700/80 hover:text-slate-205'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0">
                    <p className="text-sm font-bold truncate pr-6">{s.friendly_name || 'Primary WhatsApp Channel'}</p>
                    <p className="text-xs text-slate-500 font-mono mt-0.5">{s.sender_number || 'Mock Sandbox'}</p>
                  </div>
                  {s.is_default && (
                    <span className="text-[9px] font-black uppercase px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-md shrink-0">
                      Default
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-slate-900/40 mt-1 justify-between">
                  <span className={`text-[9px] font-extrabold uppercase px-1.5 py-0.2 rounded border ${
                    s.health_status === 'connected'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : s.health_status === 'expired_token'
                      ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                  }`}>
                    {s.health_status || 'untested'}
                  </span>
                  
                  <div className="flex gap-1.5">
                    {!s.is_default && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleSetDefault(s.id); }}
                        className="text-[10px] font-bold text-slate-400 hover:text-emerald-400 px-1 py-0.5 transition cursor-pointer"
                        title="Set Default"
                      >
                        Set Default
                      </button>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); handleArchiveNumber(s.id); }}
                      className="text-[10px] font-bold text-slate-500 hover:text-rose-400 px-1 py-0.5 transition cursor-pointer"
                      title="Archive Line"
                    >
                      Disconnect
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Connection verification and diagnostics (PART 4 & 7) */}
        {activeSettings && (
          <div className="lg:col-span-2 space-y-6">
            <div className="glass-panel border border-slate-800/80 rounded-2xl p-6 space-y-6">
              
              {/* Account Summary & Renaming */}
              <div className="flex flex-wrap items-center justify-between border-b border-slate-850 pb-5 gap-4">
                <div className="min-w-0 flex-1">
                  {isEditingName ? (
                    <div className="flex items-center gap-2 max-w-sm">
                      <input
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        className="bg-slate-900 border border-slate-800 text-slate-200 py-1.5 px-3 rounded-lg text-sm flex-1 focus:outline-none focus:border-emerald-500"
                        placeholder="e.g. Support Desk"
                      />
                      <button onClick={handleRenameNumber} className="bg-emerald-600 hover:bg-emerald-555 text-white py-1.5 px-3 rounded-lg text-xs font-bold cursor-pointer">Save</button>
                      <button onClick={() => setIsEditingName(false)} className="text-slate-450 hover:text-slate-205 text-xs">Cancel</button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-bold text-slate-100 truncate">{activeSettings.friendly_name || 'Primary WhatsApp Channel'}</h2>
                      <button onClick={() => { setIsEditingName(true); setNewName(activeSettings.friendly_name || ''); }} className="text-slate-500 hover:text-slate-300 transition">
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                  <p className="text-xs text-slate-400 font-mono mt-1">{activeSettings.sender_number || 'Mock Sandbox Number'}</p>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={handleManualSync}
                    disabled={saving}
                    className="inline-flex items-center gap-1.5 bg-slate-900 hover:bg-slate-850 text-slate-300 border border-slate-800 py-2 px-3 rounded-xl text-xs font-semibold transition cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${saving ? 'animate-spin' : ''}`} /> Refresh Metadata
                  </button>
                  <button
                    onClick={() => { setSelectedDefaultId(activeSettings.id); setWizardOpen(true); setWizardStep(1); }}
                    className="inline-flex items-center gap-1.5 bg-slate-900 hover:bg-slate-850 text-slate-300 border border-slate-800 py-2 px-3 rounded-xl text-xs font-semibold transition cursor-pointer"
                  >
                    <RefreshCw className="w-3.5 h-3.5 text-teal-400" /> Reconnect
                  </button>
                </div>
              </div>

              {/* Connection Status Card Summary */}
              <div className="p-5 bg-slate-900/30 border border-slate-800/60 rounded-2xl space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${
                      activeSettings.health_status === 'connected' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                    }`} />
                    <span className="text-xs uppercase font-extrabold tracking-wider text-slate-200">
                      Account Status: <span className={activeSettings.health_status === 'connected' ? 'text-emerald-400' : 'text-rose-400'}>{activeSettings.health_status || 'Disconnected'}</span>
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500">
                    Last Sync: {activeSettings.updated_at ? new Date(activeSettings.updated_at).toLocaleTimeString() : 'Just now'}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-1">
                  <div className="space-y-0.5">
                    <span className="text-[9px] uppercase font-bold text-slate-500 tracking-wider">Phone Number</span>
                    <p className="text-xs font-semibold text-slate-200 font-mono">{activeSettings.sender_number || 'Sandbox'}</p>
                  </div>
                  <div className="space-y-0.5">
                    <span className="text-[9px] uppercase font-bold text-slate-500 tracking-wider">Quality Rating</span>
                    <p className="text-xs font-bold text-emerald-450">
                      {activeSettings.quality_rating || 'GREEN'}
                    </p>
                  </div>
                  <div className="space-y-0.5">
                    <span className="text-[9px] uppercase font-bold text-slate-500 tracking-wider">Messaging Tier</span>
                    <p className="text-xs font-semibold text-slate-200">{activeSettings.messaging_limit || '1,000 / day'}</p>
                  </div>
                  <div className="space-y-0.5">
                    <span className="text-[9px] uppercase font-bold text-slate-500 tracking-wider">Token Health</span>
                    <p className="text-xs font-semibold text-slate-200">{diagnostics?.token_valid === 'green' ? 'Valid' : 'Expired'}</p>
                  </div>
                </div>
              </div>

              {/* Status details grid (PART 4) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">Connection Verification</h4>
                  
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between text-xs py-1 border-b border-slate-900">
                      <span className="text-slate-400">Connection Health</span>
                      <span className="font-semibold text-slate-200 capitalize">{activeSettings.health_status || 'Disconnected'}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs py-1 border-b border-slate-900">
                      <span className="text-slate-400">Phone Status</span>
                      <span className="font-semibold text-slate-200 capitalize">{activeSettings.display_name_status || 'Verified'}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs py-1 border-b border-slate-900">
                      <span className="text-slate-400">Daily Send Limit</span>
                      <span className="font-semibold text-slate-200">{activeSettings.daily_limit?.toLocaleString() || '1,000'} / day</span>
                    </div>
                    <div className="flex items-center justify-between text-xs py-1 border-b border-slate-900">
                      <span className="text-slate-400">Quality Rating</span>
                      <span className={`font-extrabold uppercase text-[10px] ${
                        activeSettings.quality_rating === 'GREEN' ? 'text-emerald-400' : 'text-amber-400'
                      }`}>
                        {activeSettings.quality_rating || 'GREEN'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Diagnostics block (PART 7) */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">Connection Diagnostics</h4>
                    <button
                      onClick={() => runDiagnosticsFor(activeSettings.id)}
                      disabled={checkingDiagnostics}
                      className="text-xs font-bold text-teal-400 hover:text-teal-300 flex items-center gap-1 cursor-pointer"
                    >
                      {checkingDiagnostics ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3.5 h-3.5" />} Retest
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <DiagnosticIndicator label="Webhook Reachable" status={diagnostics?.webhook_reachable || 'green'} />
                    <DiagnosticIndicator label="Token Valid" status={diagnostics?.token_valid || 'green'} />
                    <DiagnosticIndicator label="Phone Verified" status={diagnostics?.phone_verified || 'green'} />
                    <DiagnosticIndicator label="Graph API Reachable" status={diagnostics?.graph_api_reachable || 'green'} />
                    <div className="sm:col-span-2">
                      <DiagnosticIndicator label="Message Templates Synced" status={diagnostics?.template_sync || 'green'} />
                    </div>
                  </div>

                  {diagnostics && (
                    <div className="mt-3 p-3 bg-slate-900/60 border border-slate-800/80 rounded-xl space-y-2 text-[11px] text-slate-400">
                      <div className="flex justify-between border-b border-slate-850/40 pb-1.5">
                        <span>Graph Latency:</span>
                        <span className="font-semibold text-slate-300">{(diagnostics as any).graph_latency_ms || 0} ms</span>
                      </div>
                      <div className="flex justify-between border-b border-slate-850/40 pb-1.5">
                        <span>Token Info:</span>
                        <span className="text-right text-slate-350">{(diagnostics as any).token_detail || 'Valid'}</span>
                      </div>
                      <div className="flex justify-between border-b border-slate-850/40 pb-1.5">
                        <span>Media Upload Test:</span>
                        <span className={`font-semibold uppercase text-[10px] ${(diagnostics as any).media_upload_status === 'green' ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {(diagnostics as any).media_upload_status || 'green'}
                        </span>
                      </div>
                      {(diagnostics as any).media_detail && (
                        <div className="pl-2 border-l border-slate-800 text-[10px] text-slate-500 italic pb-1.5">
                          {(diagnostics as any).media_detail}
                        </div>
                      )}
                      <div className="flex justify-between border-b border-slate-850/40 pb-1.5">
                        <span>Business Verification:</span>
                        <span className="font-semibold uppercase text-slate-300">{(diagnostics as any).business_verification_status || 'verified'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Capabilities:</span>
                        <span className="text-right text-slate-300">
                          {Array.isArray((diagnostics as any).capabilities) 
                            ? (diagnostics as any).capabilities.join(', ') 
                            : 'whatsapp_business_messaging'}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Troubleshooting alerts (PART 9) */}
              {troubleshootingAdvices && troubleshootingAdvices.length > 0 && (
                <div className="p-4 bg-amber-950/20 border border-amber-850/40 rounded-xl space-y-3 animate-in fade-in">
                  <div className="flex items-center gap-2 text-amber-400 font-bold text-sm">
                    <AlertTriangle className="w-5 h-5" />
                    <span>System Diagnostic Recommendations</span>
                  </div>
                  <div className="divide-y divide-slate-800/40">
                    {troubleshootingAdvices.map((adv, idx) => (
                      <div key={idx} className={`pt-2 ${idx > 0 ? 'mt-2 border-t' : ''}`}>
                        <p className="text-xs font-bold text-slate-200">{adv.title}</p>
                        <p className="text-xs text-slate-400 mt-1 leading-relaxed">{adv.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Auto Responder Panel */}
              <div className="border-t border-slate-850 pt-5 space-y-4">
                <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-emerald-400" /> Auto-Responder
                </h3>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={activeSettings.auto_reply_enabled}
                    onChange={(e) => setActiveSettings({ ...activeSettings, auto_reply_enabled: e.target.checked })}
                    className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-emerald-500 focus:ring-emerald-500 cursor-pointer"
                  />
                  <span className="text-xs text-slate-350 font-medium">Enable auto-reply on new incoming threads</span>
                </label>
                <div className="flex flex-col gap-2">
                  <textarea
                    value={activeSettings.auto_reply_message || ''}
                    onChange={(e) => setActiveSettings({ ...activeSettings, auto_reply_message: e.target.value })}
                    rows={3}
                    placeholder="e.g. Thanks for messaging Johnson CRM! An agent will be in touch with you shortly."
                    className="w-full bg-slate-900 border border-slate-800 text-slate-200 py-2.5 px-3.5 rounded-xl text-xs focus:border-emerald-500/50 focus:outline-none transition resize-none"
                  />
                  <div className="flex justify-end">
                    <button
                      onClick={handleSaveAutoReply}
                      disabled={saving}
                      className="bg-emerald-600 hover:bg-emerald-550 text-white font-bold py-1.5 px-4 rounded-lg text-xs cursor-pointer transition"
                    >
                      {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Save Message'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Quick Replies Panel */}
              <div className="border-t border-slate-850 pt-5 space-y-4">
                <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-emerald-400" /> Canned Quick-Replies
                </h3>
                <div className="flex flex-wrap items-end gap-3 bg-slate-950/20 p-4 border border-slate-850 rounded-xl">
                  <label className="w-36 space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Shortcut key</span>
                    <input
                      value={qrShortcut}
                      onChange={(e) => setQrShortcut(e.target.value)}
                      placeholder="/thanks"
                      className="w-full bg-slate-900 border border-slate-800 text-slate-200 py-2 px-3 rounded-lg text-xs focus:outline-none"
                    />
                  </label>
                  <label className="flex-1 min-w-[200px] space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Canned text message template</span>
                    <input
                      value={qrText}
                      onChange={(e) => setQrText(e.target.value)}
                      placeholder="Thanks for choosing Johnson CRM! Let us know if you need anything else."
                      className="w-full bg-slate-900 border border-slate-800 text-slate-200 py-2 px-3 rounded-lg text-xs focus:outline-none"
                    />
                  </label>
                  <button
                    onClick={addQuickReply}
                    className="inline-flex items-center gap-1.5 bg-slate-850 hover:bg-slate-800 text-slate-200 border border-slate-800 py-2 px-4 rounded-xl text-xs font-semibold cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5 text-emerald-400" /> Create
                  </button>
                </div>
                
                {quickReplies.length === 0 ? (
                  <p className="text-xs text-slate-500">No quick replies created yet. Canned shortcuts starting with `/` will speed up replying to conversations.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {quickReplies.map((q) => (
                      <div key={q.id} className="flex items-center justify-between p-3 bg-slate-900/20 border border-slate-850 rounded-xl hover:border-slate-800/80 transition">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="px-2 py-0.5 text-[9px] font-bold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0 uppercase tracking-wider">{q.shortcut}</span>
                          <span className="text-xs text-slate-300 truncate">{q.text}</span>
                        </div>
                        <button
                          onClick={() => removeQuickReply(q.id)}
                          className="p-1 text-slate-500 hover:text-rose-450 cursor-pointer shrink-0 transition"
                          title="Delete reply"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>
          </div>
        )}
      </div>
      )}

      {/* Production Health Dashboard view (PART 8) */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          {loadingMetrics && !dashboardMetrics ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-teal-400" />
              <p className="text-sm text-slate-400">Loading monitoring parameters...</p>
            </div>
          ) : dashboardMetrics ? (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Grid of Key Performance Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* 1. Account Connectivity Health */}
                <div className="glass-panel border border-slate-800/80 rounded-2xl p-5 space-y-3">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Account States</span>
                    <Heart className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-3xl font-extrabold text-slate-100">{dashboardMetrics.connected_accounts}</p>
                    <div className="flex flex-wrap gap-2 text-[10px] text-slate-400 font-medium">
                      <span className="text-emerald-400 font-bold">{dashboardMetrics.connected_accounts} Connected</span>
                      {dashboardMetrics.disconnected_accounts > 0 && (
                        <span className="text-rose-400 font-bold">{dashboardMetrics.disconnected_accounts} Disconnected</span>
                      )}
                      {dashboardMetrics.expired_tokens > 0 && (
                        <span className="text-amber-400 font-bold">{dashboardMetrics.expired_tokens} Expired</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* 2. Success Rate Percentage */}
                <div className="glass-panel border border-slate-800/80 rounded-2xl p-5 space-y-3">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Outbound Success</span>
                    <ShieldCheck className="w-4 h-4 text-indigo-400" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-3xl font-extrabold text-slate-100">{dashboardMetrics.success_rate}%</p>
                    <p className="text-[10px] text-slate-400">
                      Failed: <span className="font-bold text-rose-450">{dashboardMetrics.failed_messages}</span> messages
                    </p>
                  </div>
                </div>

                {/* 3. Latency Metrics */}
                <div className="glass-panel border border-slate-800/80 rounded-2xl p-5 space-y-3">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Graph API Latency</span>
                    <Activity className="w-4 h-4 text-sky-400" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-3xl font-extrabold text-slate-100">{dashboardMetrics.graph_api_latency_ms}ms</p>
                    <p className="text-[10px] text-slate-400">Average response latency</p>
                  </div>
                </div>

                {/* 4. Queue Service Health */}
                <div className="glass-panel border border-slate-800/80 rounded-2xl p-5 space-y-3">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Queue Health</span>
                    <Clock className="w-4 h-4 text-purple-400" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-3xl font-extrabold text-slate-100 capitalize">{dashboardMetrics.queue_health}</p>
                    <p className="text-[10px] text-slate-400">
                      Pending Tasks: <span className="font-bold text-slate-200">{dashboardMetrics.queue_size}</span>
                    </p>
                  </div>
                </div>
              </div>

              {/* Status Section */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Status Cards */}
                <div className="md:col-span-2 glass-panel border border-slate-800/80 rounded-2xl p-6 space-y-4">
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-400">System Handshake Summary</h3>
                  
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-4 bg-slate-900/40 border border-slate-800 rounded-xl space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-400">Webhook Connection</span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          dashboardMetrics.webhook_status === 'healthy' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                        }`}>{dashboardMetrics.webhook_status}</span>
                      </div>
                      <p className="text-[11px] text-slate-500">Idempotency-checked inbound listener configuration</p>
                    </div>

                    <div className="p-4 bg-slate-900/40 border border-slate-800 rounded-xl space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-400">Template Sync State</span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          dashboardMetrics.template_sync_status === 'healthy' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                        }`}>{dashboardMetrics.template_sync_status}</span>
                      </div>
                      <p className="text-[11px] text-slate-500">Hourly queued synchronization loop updates</p>
                    </div>
                  </div>
                  
                  <div className="pt-4 border-t border-slate-850 text-xs text-slate-500 flex justify-between">
                    <span>Last Meta Sync Run:</span>
                    <span className="font-semibold text-slate-350 font-mono">
                      {dashboardMetrics.last_sync_time !== 'Never' ? new Date(dashboardMetrics.last_sync_time).toLocaleString() : 'Never'}
                    </span>
                  </div>
                </div>

                {/* Queue/Volume Diagnostics */}
                <div className="glass-panel border border-slate-800/80 rounded-2xl p-6 space-y-4">
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-400">Message Volume</h3>
                  <div className="space-y-4">
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Daily Message Volume</span>
                        <span className="font-bold text-slate-200">{dashboardMetrics.daily_volume}</span>
                      </div>
                      <div className="w-full bg-slate-850 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-emerald-500 h-full" style={{ width: `${Math.min(100, (dashboardMetrics.daily_volume / 200) * 100)}%` }} />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Pending Queue Size</span>
                        <span className="font-bold text-slate-200">{dashboardMetrics.queue_size}</span>
                      </div>
                      <div className="w-full bg-slate-850 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-indigo-500 h-full" style={{ width: `${Math.min(100, (dashboardMetrics.queue_size / 50) * 100)}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Lists of Numbers quality & messaging limits */}
              <div className="glass-panel border border-slate-800/80 rounded-2xl p-6 space-y-4">
                <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-400">Registered Phone Lines Health</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-850 text-slate-400 uppercase font-bold text-[10px] tracking-wider">
                        <th className="py-3 px-4">Phone Number</th>
                        <th className="py-3 px-4">Quality Rating</th>
                        <th className="py-3 px-4">Limit Tier</th>
                        <th className="py-3 px-4">Daily Cap</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardMetrics.quality_ratings && dashboardMetrics.quality_ratings.map((q: any, idx: number) => {
                        const limitObj = dashboardMetrics.messaging_limits && dashboardMetrics.messaging_limits.find((l: any) => l.settings_id === q.settings_id);
                        return (
                          <tr key={q.settings_id || idx} className="border-b border-slate-900/60 hover:bg-slate-900/20 text-slate-300">
                            <td className="py-3 px-4 font-semibold font-mono text-slate-200">{q.sender_number}</td>
                            <td className="py-3 px-4">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                q.quality_rating === 'GREEN' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
                              }`}>{q.quality_rating}</span>
                            </td>
                            <td className="py-3 px-4 text-slate-350">{limitObj?.messaging_limit || 'TIER_1K'}</td>
                            <td className="py-3 px-4 text-slate-350">{limitObj?.daily_limit?.toLocaleString() || '1,000'} / day</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-500">
              No monitoring statistics found. Connect a WhatsApp Business account to initialize stats.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
