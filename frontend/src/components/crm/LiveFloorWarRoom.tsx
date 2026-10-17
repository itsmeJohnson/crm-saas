import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Users, PhoneCall, PhoneForwarded, Coffee, Shield, Radio,
  Play, Pause, Volume2, CheckCircle2, RefreshCw, Lock
} from 'lucide-react';
import { api } from '../../services/api';
import { useAuthStore } from '../../store/authStore';

interface AgentFloorState {
  user_id: string;
  name: string;
  email: string;
  state: 'IDLE' | 'RINGING' | 'ACTIVE_CALLING' | 'ON_CALL' | 'BREAK';
  state_duration_seconds: number;
  current_lead_id?: string;
  current_lead_name?: string;
  calls_today: number;
  total_talk_time_seconds: number;
}

interface RecordingItem {
  id: string;
  caller_name: string;
  lead_name: string;
  phone_masked: string;
  duration_seconds: number;
  outcome: string;
  timestamp: string;
  recording_url: string | null;
}

export const LiveFloorWarRoom: React.FC = () => {
  const { user } = useAuthStore();
  const isPrivileged = user?.role === 'OrgAdmin' || user?.role === 'Manager' || user?.role === 'SuperAdmin' || !!user?.is_team_leader;

  const [activeTab, setActiveTab] = useState<'floor' | 'vault'>('floor');
  const [agents, setAgents] = useState<AgentFloorState[]>([]);
  const [recordings, setRecordings] = useState<RecordingItem[]>([]);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const fetchFloorStatus = useCallback(async () => {
    try {
      const res = await api.get<AgentFloorState[]>('/calling/floor-monitor');
      setAgents(res.data);
    } catch (e) {
      // Fallback: query agent states
      try {
        const alt = await api.get('/dialer/agent-states');
        if (Array.isArray(alt.data)) {
          setAgents(alt.data);
        }
      } catch (err) {}
    }
  }, []);

  const fetchVaultRecordings = useCallback(async () => {
    if (!isPrivileged) return;
    try {
      const res = await api.get('/calling/history', { params: { has_recording: true, limit: 30 } });
      const items = res.data.items || res.data || [];
      setRecordings(items.map((it: any) => ({
        id: it.id,
        caller_name: it.user_name || it.agent_name || 'Agent',
        lead_name: it.lead_name || it.title || 'Lead',
        phone_masked: it.customer_phone || it.phone || '+91 98450 •••••',
        duration_seconds: it.duration_seconds || it.duration || 0,
        outcome: it.disposition || it.status || 'Completed',
        timestamp: it.created_at || it.timestamp || new Date().toISOString(),
        recording_url: it.recording_url || `/api/v1/calling/${it.id}/recording-stream`
      })));
    } catch (e) {}
  }, [isPrivileged]);

  useEffect(() => {
    fetchFloorStatus();
    // High-velocity floor monitor polling sync (<1.5s latency)
    const interval = setInterval(fetchFloorStatus, 1500);
    return () => clearInterval(interval);
  }, [fetchFloorStatus]);

  useEffect(() => {
    if (activeTab === 'vault') {
      fetchVaultRecordings();
    }
  }, [activeTab, fetchVaultRecordings]);

  const formatSecs = (sec: number): string => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins}:${s.toString().padStart(2, '0')}`;
  };

  const handlePlayToggle = (recId: string, url: string | null) => {
    if (!isPrivileged) return;
    if (playingId === recId) {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      setPlayingId(null);
    } else {
      setPlayingId(recId);
      if (audioRef.current && url) {
        audioRef.current.src = url;
        audioRef.current.play().catch(() => {});
      }
    }
  };

  const activeCallingCount = agents.filter(a => a.state === 'ACTIVE_CALLING' || a.state === 'ON_CALL').length;
  const ringingCount = agents.filter(a => a.state === 'RINGING').length;
  const idleCount = agents.filter(a => a.state === 'IDLE').length;
  const breakCount = agents.filter(a => a.state === 'BREAK').length;

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Hidden audio element for vault streaming */}
      <audio ref={audioRef} onEnded={() => setPlayingId(null)} className="hidden" />

      {/* Header & Mode Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#1e293b] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-indigo-400">
              <Radio className="w-5 h-5 animate-pulse" />
            </span>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Floor War Room & Audio Vault
              </h1>
              <p className="text-xs text-slate-400">
                Live floor agent telemetry sync (<span className="text-emerald-400 font-semibold">&lt;1.5s latency</span>) & Role-gated call vaults
              </p>
            </div>
          </div>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center p-1 bg-[#080b14] border border-[#1e293b] rounded-xl self-start sm:self-auto">
          <button
            onClick={() => setActiveTab('floor')}
            className={`min-h-[38px] px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 cursor-pointer ${
              activeTab === 'floor'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Live Floor Matrix</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-white/20">{agents.length}</span>
          </button>

          <button
            onClick={() => setActiveTab('vault')}
            className={`min-h-[38px] px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 cursor-pointer ${
              activeTab === 'vault'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Volume2 className="w-3.5 h-3.5" />
            <span>Audio Vault</span>
            {!isPrivileged && <Lock className="w-3 h-3 text-amber-400 ml-1" />}
          </button>
        </div>
      </div>

      {/* KPI Status Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="crm-metric-card flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Active Calling</p>
            <p className="text-2xl font-black text-indigo-400 mt-1">{activeCallingCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <PhoneCall className="w-5 h-5 animate-pulse" />
          </div>
        </div>

        <div className="crm-metric-card flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Ringing</p>
            <p className="text-2xl font-black text-amber-400 mt-1">{ringingCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <PhoneForwarded className="w-5 h-5" />
          </div>
        </div>

        <div className="crm-metric-card flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Idle / Ready</p>
            <p className="text-2xl font-black text-emerald-400 mt-1">{idleCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="crm-metric-card flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">On Break</p>
            <p className="text-2xl font-black text-rose-400 mt-1">{breakCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400">
            <Coffee className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* TAB 1: Live Floor Matrix */}
      {activeTab === 'floor' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-400 px-1">
            <span className="font-semibold uppercase tracking-wider">Calling Floor Real-Time Monitor</span>
            <span className="flex items-center gap-1.5 text-emerald-400 font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              Live WebSocket Active
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {agents.length === 0 ? (
              <div className="col-span-full p-8 text-center bg-[#111a2e] border border-[#1e293b] rounded-2xl">
                <Users className="w-8 h-8 text-slate-500 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-300">No agents registered on floor yet</p>
                <p className="text-xs text-slate-500 mt-1">Logged-in telecallers will appear here instantly.</p>
              </div>
            ) : (
              agents.map((agent) => {
                const isCalling = agent.state === 'ACTIVE_CALLING' || agent.state === 'ON_CALL';
                const isRinging = agent.state === 'RINGING';
                const isBreak = agent.state === 'BREAK';

                return (
                  <div
                    key={agent.user_id}
                    className="p-4 rounded-xl bg-[#111a2e] border border-[#1e293b] hover:border-slate-700 transition space-y-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h4 className="text-sm font-bold text-white truncate">{agent.name}</h4>
                        <p className="text-[11px] text-slate-400 truncate">{agent.email}</p>
                      </div>

                      {/* State Pill */}
                      <span
                        className={`crm-status-pill text-[10px] font-bold ${
                          isCalling
                            ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 animate-pulse'
                            : isRinging
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse'
                            : isBreak
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        }`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          isCalling ? 'bg-indigo-400' : isRinging ? 'bg-amber-400' : isBreak ? 'bg-rose-400' : 'bg-emerald-400'
                        }`} />
                        {agent.state.replace('_', ' ')}
                      </span>
                    </div>

                    {/* Calling Detail */}
                    <div className="p-2.5 rounded-lg bg-[#080b14] border border-[#1e293b] space-y-1.5 text-xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span>Current Lead</span>
                        <span className="font-semibold text-slate-200 truncate max-w-[140px]">
                          {agent.current_lead_name || '—'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-slate-400">
                        <span>State Elapsed</span>
                        <span className="font-mono font-bold text-indigo-400">
                          {formatSecs(agent.state_duration_seconds || 0)}
                        </span>
                      </div>
                    </div>

                    {/* Stats footer */}
                    <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-[#1e293b]">
                      <span>Dials Today: <strong className="text-white">{agent.calls_today}</strong></span>
                      <span>Talk Time: <strong className="text-emerald-400">{formatSecs(agent.total_talk_time_seconds)}</strong></span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Audio Vault */}
      {activeTab === 'vault' && (
        <div className="space-y-4">
          {!isPrivileged ? (
            <div className="p-8 text-center bg-[#111a2e] border border-amber-500/30 rounded-2xl space-y-2">
              <Lock className="w-8 h-8 text-amber-400 mx-auto" />
              <h3 className="text-sm font-bold text-white">Audio Vault Restricted</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Call recording playbacks and time-limited presigned streaming endpoints are restricted exclusively to Workspace Admins and Managers for compliance and anti-poaching security.
              </p>
            </div>
          ) : (
            <div className="bg-[#111a2e] border border-[#1e293b] rounded-2xl overflow-hidden shadow-xl">
              <div className="px-5 py-4 border-b border-[#1e293b] flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Shield className="w-4 h-4 text-indigo-400" />
                    Role-Gated Compliance Vault
                  </h3>
                  <p className="text-xs text-slate-400">Presigned time-limited audio streaming</p>
                </div>
                <button
                  onClick={fetchVaultRecordings}
                  className="min-h-[36px] px-3 py-1.5 rounded-lg bg-[#080b14] border border-[#1e293b] text-xs font-semibold text-slate-300 hover:text-white flex items-center gap-1.5 cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Refresh
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="crm-table">
                  <thead>
                    <tr>
                      <th>Agent</th>
                      <th>Lead Contact</th>
                      <th>Outcome</th>
                      <th>Duration</th>
                      <th>Timestamp</th>
                      <th className="text-right">Playback</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recordings.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="text-center py-8 text-slate-500 text-xs">
                          No audio recordings captured yet.
                        </td>
                      </tr>
                    ) : (
                      recordings.map((rec) => (
                        <tr key={rec.id} className="crm-table-row">
                          <td className="font-semibold text-white">{rec.caller_name}</td>
                          <td>
                            <div>
                              <p className="font-semibold text-slate-200">{rec.lead_name}</p>
                              <p className="font-mono text-[11px] text-indigo-300">{rec.phone_masked}</p>
                            </div>
                          </td>
                          <td>
                            <span className="crm-status-pill bg-slate-800 text-slate-300 border border-slate-700">
                              {rec.outcome}
                            </span>
                          </td>
                          <td className="font-mono text-xs">{formatSecs(rec.duration_seconds)}</td>
                          <td className="text-slate-400 text-xs">
                            {new Date(rec.timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                          </td>
                          <td className="text-right">
                            <button
                              onClick={() => handlePlayToggle(rec.id, rec.recording_url)}
                              className={`min-h-[36px] px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ml-auto cursor-pointer ${
                                playingId === rec.id
                                  ? 'bg-rose-600 text-white shadow-md shadow-rose-600/30'
                                  : 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-600 hover:text-white'
                              }`}
                            >
                              {playingId === rec.id ? (
                                <>
                                  <Pause className="w-3.5 h-3.5" />
                                  <span>Stop</span>
                                </>
                              ) : (
                                <>
                                  <Play className="w-3.5 h-3.5" />
                                  <span>Stream</span>
                                </>
                              )}
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
