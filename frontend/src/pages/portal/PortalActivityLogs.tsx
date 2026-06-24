import React, { useState, useEffect } from 'react';
import { portalApi } from '../../services/portalApi';
import {
  Activity, Search, Shield, ChevronDown, ChevronUp,
  AlertTriangle, Loader2, Calendar, HardDrive
} from 'lucide-react';

export const PortalActivityLogs: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const data = await portalApi.getActivityLogs();
      setLogs(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load audit logs.");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleExpand = (id: string) => {
    setExpandedLogId(expandedLogId === id ? null : id);
  };

  const filteredLogs = logs.filter((log) => {
    const query = searchQuery.toLowerCase();
    return (
      log.action.toLowerCase().includes(query) ||
      log.resource_type.toLowerCase().includes(query) ||
      (log.resource_id && log.resource_id.toLowerCase().includes(query))
    );
  });

  const renderDiffTable = (metadata: any) => {
    const changes = metadata?.changes;
    if (!changes || typeof changes !== 'object') {
      return (
        <div className="p-3.5 bg-slate-950/80 rounded-xl border border-slate-900/60 font-mono text-[10px] text-slate-500">
          Metadata: {JSON.stringify(metadata, null, 2)}
        </div>
      );
    }

    return (
      <div className="overflow-x-auto p-2 bg-slate-950/40 border border-slate-900 rounded-xl max-w-xl">
        <table className="w-full text-xs text-left">
          <thead>
            <tr className="text-slate-500 border-b border-slate-900/60 uppercase font-bold text-[9px]">
              <th className="p-2">Property</th>
              <th className="p-2">Old Value</th>
              <th className="p-2 text-brand-400">New Value</th>
            </tr>
          </thead>
          <tbody>
            {Object.keys(changes).map((key) => {
              const item = changes[key];
              return (
                <tr key={key} className="border-b border-slate-900/30 text-slate-300 font-mono text-[10px]">
                  <td className="p-2 font-semibold text-slate-400">{key}</td>
                  <td className="p-2 line-through text-slate-600 truncate max-w-[150px]">
                    {item.old !== null && item.old !== undefined ? String(item.old) : 'null'}
                  </td>
                  <td className="p-2 text-brand-400 font-bold truncate max-w-[150px]">
                    {item.new !== null && item.new !== undefined ? String(item.new) : 'null'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8 text-left max-w-6xl mx-auto font-sans">
      {/* Header */}
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
          Organization Activity Audit Logs
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Review security revisions, track tenant state change-diff comparisons, examine payment entries, and audit portal modifications.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          placeholder="Search by action, modified resource type..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
        />
      </div>

      {/* Audit Log Table Grid */}
      <div className="glass-panel border border-slate-900 rounded-2xl overflow-hidden">
        {filteredLogs.length === 0 ? (
          <p className="p-8 text-slate-500 text-xs text-center">No audit trail records found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="bg-slate-950/40 text-slate-500 border-b border-slate-900 uppercase font-bold">
                  <th className="p-4 w-8"></th>
                  <th className="p-4">Action Event</th>
                  <th className="p-4">Resource Level</th>
                  <th className="p-4">Reference Key</th>
                  <th className="p-4 text-right">Date Performed</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log) => {
                  const isExpanded = expandedLogId === log.id;
                  return (
                    <React.Fragment key={log.id}>
                      <tr
                        onClick={() => handleToggleExpand(log.id)}
                        className="border-b border-slate-900 hover:bg-slate-900/10 text-slate-300 cursor-pointer"
                      >
                        <td className="p-4 text-center">
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4 text-slate-500" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-slate-500" />
                          )}
                        </td>
                        <td className="p-4 font-mono font-semibold text-brand-400">
                          {log.action}
                        </td>
                        <td className="p-4 font-medium text-slate-400">
                          {log.resource_type}
                        </td>
                        <td className="p-4 font-mono text-slate-500">
                          {log.resource_id ? log.resource_id.substring(0, 16) + '...' : 'System'}
                        </td>
                        <td className="p-4 text-right text-slate-500">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-slate-950/20 border-b border-slate-900">
                          <td colSpan={5} className="p-5 pl-12 space-y-3">
                            <div className="space-y-1">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Comparative Changes Diff</span>
                              {renderDiffTable(log.metadata)}
                            </div>
                            {log.metadata?.ip && (
                              <div className="flex gap-4 text-[10px] text-slate-500">
                                <span>IP Address: <strong className="text-slate-400">{log.metadata.ip}</strong></span>
                                <span>Agent: <strong className="text-slate-400">{log.metadata.user_agent}</strong></span>
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
