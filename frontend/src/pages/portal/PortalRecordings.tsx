import React, { useState, useEffect } from 'react';
import { portalApi } from '../../services/portalApi';
import {
  PhoneCall, Play, Pause, Trash2, Download, Search,
  AlertTriangle, Loader2, CheckCircle2, Volume2, ArrowUpDown
} from 'lucide-react';

export const PortalRecordings: React.FC = () => {
  const [recordings, setRecordings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [directionFilter, setDirectionFilter] = useState<'all' | 'inbound' | 'outbound'>('all');

  // Inline audio play state
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [audioInstance, setAudioInstance] = useState<HTMLAudioElement | null>(null);

  // Deletion modal state
  const [deleteTarget, setDeleteTarget] = useState<any | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchRecordings();
    return () => {
      // Clean up audio player on unmount
      if (audioInstance) {
        audioInstance.pause();
      }
    };
  }, [audioInstance]);

  const fetchRecordings = async () => {
    try {
      setLoading(true);
      const data = await portalApi.getRecordings();
      setRecordings(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load voice recordings.");
    } finally {
      setLoading(false);
    }
  };

  const handlePlayPause = (id: string, url: string) => {
    if (playingId === id) {
      if (audioInstance) {
        audioInstance.pause();
      }
      setPlayingId(null);
    } else {
      if (audioInstance) {
        audioInstance.pause();
      }
      const newAudio = new Audio(url);
      newAudio.play().catch((err) => {
        setError("Audio recording file URL failed to play.");
      });
      newAudio.onended = () => {
        setPlayingId(null);
      };
      setAudioInstance(newAudio);
      setPlayingId(id);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      setDeleting(true);
      setError(null);
      setSuccess(null);

      // Stop playing if it's the deleted one
      if (playingId === deleteTarget.id) {
        if (audioInstance) audioInstance.pause();
        setPlayingId(null);
      }

      await portalApi.deleteRecording(deleteTarget.id);
      setSuccess("Call recording successfully deleted from storage.");
      setDeleteTarget(null);
      fetchRecordings();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to delete call recording.");
    } finally {
      setDeleting(false);
    }
  };

  const formatDuration = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = sec % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const filteredRecordings = recordings.filter((rec) => {
    const query = searchQuery.toLowerCase();
    const matchesSearch = rec.subject.toLowerCase().includes(query) || 
                          rec.assigned_user.toLowerCase().includes(query);

    const matchesDirection = directionFilter === 'all' || 
                             rec.direction.toLowerCase() === directionFilter;

    return matchesSearch && matchesDirection;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8 text-left max-w-6xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
          Voice Call Recordings
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Review recorded client phone conversations, play calls inline, and manage storage retention policies.
        </p>
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

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-stretch">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search by call subject, agent description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
          />
        </div>

        <div className="bg-slate-900/60 border border-slate-800 p-1 rounded-xl flex gap-1 items-center">
          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider px-2">Direction</span>
          {(['all', 'inbound', 'outbound'] as const).map((dir) => (
            <button
              key={dir}
              onClick={() => setDirectionFilter(dir)}
              className={`px-3 py-1.5 rounded-lg text-[10px] font-bold capitalize transition-all cursor-pointer ${
                directionFilter === dir
                  ? 'bg-brand-500 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {dir}
            </button>
          ))}
        </div>
      </div>

      {/* Recordings Table Grid */}
      <div className="glass-panel border border-slate-900 rounded-2xl overflow-hidden">
        {filteredRecordings.length === 0 ? (
          <p className="p-8 text-slate-500 text-xs text-center">No call recordings found matching search criteria.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="bg-slate-950/40 text-slate-500 border-b border-slate-900 uppercase font-bold">
                  <th className="p-4 w-12 text-center">Play</th>
                  <th className="p-4">Call Subject</th>
                  <th className="p-4">Agent Assigned</th>
                  <th className="p-4">Direction</th>
                  <th className="p-4">Duration</th>
                  <th className="p-4">Timestamp</th>
                  <th className="p-4 text-center">Delete</th>
                </tr>
              </thead>
              <tbody>
                {filteredRecordings.map((rec) => (
                  <tr key={rec.id} className="border-b border-slate-900 hover:bg-slate-900/10 text-slate-300">
                    <td className="p-4 text-center">
                      <button
                        onClick={() => handlePlayPause(rec.id, rec.recording_url)}
                        className={`p-2 rounded-xl transition-all cursor-pointer ${
                          playingId === rec.id
                            ? 'bg-brand-500 text-white shadow shadow-brand-500/20'
                            : 'bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-slate-100'
                        }`}
                      >
                        {playingId === rec.id ? (
                          <Pause className="w-3.5 h-3.5" />
                        ) : (
                          <Play className="w-3.5 h-3.5 fill-current" />
                        )}
                      </button>
                    </td>
                    <td className="p-4 font-semibold text-slate-200">
                      {rec.subject}
                    </td>
                    <td className="p-4 text-slate-400">
                      User ID: {rec.assigned_user}
                    </td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 text-[9px] font-bold rounded uppercase border ${
                        rec.direction.toLowerCase() === 'inbound'
                          ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'
                          : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      }`}>
                        {rec.direction}
                      </span>
                    </td>
                    <td className="p-4 font-mono font-medium text-slate-300">
                      {formatDuration(rec.duration)}
                    </td>
                    <td className="p-4 text-slate-500">
                      {new Date(rec.date).toLocaleString()}
                    </td>
                    <td className="p-4 text-center">
                      <button
                        onClick={() => setDeleteTarget(rec)}
                        className="p-1.5 border border-slate-900 hover:border-red-500/20 text-slate-500 hover:text-red-400 rounded-lg transition-all cursor-pointer"
                        title="Delete Recording File"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <div className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-6 bg-slate-950">
            <div className="flex gap-4 items-start">
              <div className="p-3 bg-red-500/10 text-red-400 rounded-xl">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-slate-100">Revoke Call Recording?</h3>
                <p className="text-xs text-slate-500">
                  This will permanently delete the call recording file reference of subject <strong>"{deleteTarget.subject}"</strong> from cloud storage. This action is irreversible.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl cursor-pointer"
              >
                Keep File
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center justify-center gap-1.5 px-6 py-2 bg-red-500 hover:bg-red-600 text-white rounded-xl text-xs font-bold cursor-pointer"
              >
                {deleting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete Recording
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
