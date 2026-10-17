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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/25 text-indigo-600 dark:text-indigo-400">
              <Radio className="w-5 h-5 animate-pulse" />
            </span>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                Live Call Floor & Recordings
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Real-time telecaller status monitor and call recording library
              </p>
            </div>
          </div>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center p-1 bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl self-start sm:self-auto shadow-2xs">
          <button
            onClick={() => setActiveTab('floor')}
            className={`min-h-[38px] px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 cursor-pointer ${
              activeTab === 'floor'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Active Telecallers</span>
            <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${
              activeTab === 'floor' ? 'bg-white/20 text-white' : 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
            }`}>{agents.length}</span>
          </button>

          <button
            onClick={() => setActiveTab('vault')}
            className={`min-h-[38px] px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 cursor-pointer ${
              activeTab === 'vault'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            <Volume2 className="w-3.5 h-3.5" />
            <span>Call Recordings</span>
            {!isPrivileged && <Lock className="w-3 h-3 text-amber-500 ml-1" />}
          </button>
        </div>
      </div>

      {/* KPI Status Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="crm-metric-card flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Active Calling</p>
            <p className="text-2xl font-black text-indigo-600 dark:text-indigo-400 mt-1">{activeCallingCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
            <PhoneCall className="w-5 h-5 animate-pulse" />
          </div>
        </div>

        <div className="crm-metric-card flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Ringing</p>
            <p className="text-2xl font-black text-amber-500 dark:text-amber-400 mt-1">{ringingCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-500 dark:text-amber-400">
            <PhoneForwarded className="w-5 h-5" />
          </div>
        </div>

        <div className="crm-metric-card flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Idle / Ready</p>
            <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-1">{idleCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="crm-metric-card flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">On Break</p>
            <p className="text-2xl font-black text-rose-500 dark:text-rose-400 mt-1">{breakCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-500 dark:text-rose-400">
            <Coffee className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* TAB 1: Active Telecallers Floor */}
      {activeTab === 'floor' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 px-1">
            <span className="font-semibold uppercase tracking-wider">Active Telecallers On Floor</span>
            <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
              Live Status Sync
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {agents.length === 0 ? (
              <div className="col-span-full p-8 text-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm">
                <Users className="w-8 h-8 text-slate-400 dark:text-slate-500 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">No telecallers active on the floor</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Logged-in agents taking calls or available will appear here in real time.</p>
              </div>
            ) : (
              agents.map((agent) => {
                const isCalling = agent.state === 'ACTIVE_CALLING' || agent.state === 'ON_CALL';
                const isRinging = agent.state === 'RINGING';
                const isBreak = agent.state === 'BREAK';

                return (
                  <div
                    key={agent.user_id}
                    className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-indigo-400 dark:hover:border-slate-700 shadow-sm transition space-y-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h4 className="text-sm font-bold text-slate-900 dark:text-white truncate">{agent.name}</h4>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">{agent.email}</p>
                      </div>

                      {/* State Pill */}
                      <span
                        className={`crm-status-pill text-[10px] font-bold ${
                          isCalling
                            ? 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-500/30 animate-pulse'
                            : isRinging
                            ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30 animate-pulse'
                            : isBreak
                            ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30'
                            : 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          isCalling ? 'bg-indigo-500' : isRinging ? 'bg-amber-500' : isBreak ? 'bg-rose-500' : 'bg-emerald-500'
                        }`} />
                        {agent.state.replace('_', ' ')}
                      </span>
                    </div>

                    {/* Calling Detail */}
                    <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200/80 dark:border-slate-800 space-y-1.5 text-xs">
                      <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
                        <span>Current Lead</span>
                        <span className="font-semibold text-slate-900 dark:text-slate-200 truncate max-w-[140px]">
                          {agent.current_lead_name || '—'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
                        <span>Status Duration</span>
                        <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400">
                          {formatSecs(agent.state_duration_seconds || 0)}
                        </span>
                      </div>
                    </div>

                    {/* Stats footer */}
                    <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-100 dark:border-slate-800">
                      <span>Calls Today: <strong className="text-slate-900 dark:text-white">{agent.calls_today}</strong></span>
                      <span>Talk Time: <strong className="text-emerald-600 dark:text-emerald-400">{formatSecs(agent.total_talk_time_seconds)}</strong></span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Call Recordings */}
      {activeTab === 'vault' && (
        <div className="space-y-4">
          {!isPrivileged ? (
            <div className="p-8 text-center bg-amber-500/5 dark:bg-slate-900 border border-amber-500/30 rounded-2xl space-y-2">
              <Lock className="w-8 h-8 text-amber-500 dark:text-amber-400 mx-auto" />
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">Call Recordings Restricted</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 max-w-md mx-auto">
                Call recording playback is restricted to Team Leads and Managers for quality and compliance.
              </p>
            </div>
          ) : (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
              <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-transparent">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <Shield className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    Call Recordings Library
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Review and listen to completed call recordings</p>
                </div>
                <button
                  onClick={fetchVaultRecordings}
                  className="min-h-[36px] px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/80 flex items-center gap-1.5 cursor-pointer shadow-2xs"
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
                      <th>Disposition</th>
                      <th>Duration</th>
                      <th>Date & Time</th>
                      <th className="text-right">Playback</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recordings.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="text-center py-8 text-slate-500 dark:text-slate-400 text-xs">
                          No call recordings captured yet.
                        </td>
                      </tr>
                    ) : (
                      recordings.map((rec) => (
                        <tr key={rec.id} className="crm-table-row">
                          <td className="font-semibold text-slate-900 dark:text-white">{rec.caller_name}</td>
                          <td>
                            <div>
                              <p className="font-semibold text-slate-900 dark:text-slate-200">{rec.lead_name}</p>
                              <p className="font-mono text-[11px] text-indigo-600 dark:text-indigo-400">{rec.phone_masked}</p>
                            </div>
                          </td>
                          <td>
                            <span className="crm-status-pill bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700">
                              {rec.outcome}
                            </span>
                          </td>
                          <td className="font-mono text-xs text-slate-700 dark:text-slate-300">{formatSecs(rec.duration_seconds)}</td>
                          <td className="text-slate-500 dark:text-slate-400 text-xs">
                            {new Date(rec.timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                          </td>
                          <td className="text-right">
                            <button
                              onClick={() => handlePlayToggle(rec.id, rec.recording_url)}
                              className={`min-h-[36px] px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ml-auto cursor-pointer ${
                                playingId === rec.id
                                  ? 'bg-rose-600 text-white shadow-md shadow-rose-600/30'
                                  : 'bg-indigo-50 hover:bg-indigo-600 text-indigo-600 hover:text-white border border-indigo-200 dark:bg-indigo-600/20 dark:text-indigo-400 dark:border-indigo-500/30 dark:hover:bg-indigo-600 dark:hover:text-white'
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
                                  <span>Play</span>
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
