import React, { useEffect, useState } from 'react';
import { useLeadImportStore } from '../../store/leadImportStore';
import { useAuthStore } from '../../store/authStore';
import { Download, ChevronLeft, ChevronRight, Loader2, AlertCircle, FileText } from 'lucide-react';

export const ImportHistoryTable: React.FC = () => {
  const { user } = useAuthStore();
  const {
    importHistory,
    historyPagination,
    setHistoryPagination,
    fetchImportHistory,
    downloadFailedRows,
    isLoading,
    error,
  } = useLeadImportStore();

  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  useEffect(() => {
    if (user && (user.role === 'OrgAdmin' || user.role === 'Manager')) {
      fetchImportHistory();
    }
  }, [user]);

  if (!user || (user.role !== 'OrgAdmin' && user.role !== 'Manager')) {
    return null;
  }

  const handlePrevPage = () => {
    if (historyPagination.skip > 0) {
      setHistoryPagination({ skip: Math.max(0, historyPagination.skip - historyPagination.limit) });
    }
  };

  const handleNextPage = () => {
    // If we have less records than the limit, we're likely on the last page.
    if (importHistory.length === historyPagination.limit) {
      setHistoryPagination({ skip: historyPagination.skip + historyPagination.limit });
    }
  };

  const handleDownloadFailed = async (importId: string, filename: string) => {
    setDownloadingId(importId);
    try {
      const blob = await downloadFailedRows(importId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `failed_rows_${filename.split('.')[0] || importId}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download error file', err);
    } finally {
      setDownloadingId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    const s = status.toUpperCase();
    switch (s) {
      case 'COMPLETED':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Completed</span>;
      case 'PARTIAL_SUCCESS':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">Partial Success</span>;
      case 'FAILED':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-500/10 text-red-400 border border-red-500/20">Failed</span>;
      case 'PROCESSING':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse">Processing</span>;
      case 'PREVIEW_READY':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">Preview Ready</span>;
      default:
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-500/10 text-slate-400 border border-slate-800">Pending</span>;
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-slate-200 flex items-center gap-2">
            <FileText className="w-4 h-4 text-brand-400" />
            Import History
          </h3>
          <p className="text-xs text-slate-500">Track and review bulk lead imports data.</p>
        </div>

        {isLoading && <Loader2 className="w-4 h-4 text-brand-500 animate-spin" />}
      </div>

      {error && (
        <div className="p-3 bg-red-950/20 border border-red-900/30 text-red-400 rounded-xl flex items-start gap-2.5 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <div className="border border-slate-800/80 rounded-xl overflow-hidden bg-slate-900/20">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400 font-semibold">
                <th className="px-4 py-3">Filename</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3 text-right">Rows (Success/Total)</th>
                <th className="px-4 py-3 text-right">Confidence</th>
                <th className="px-4 py-3 text-center">Failed Report</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/40 text-slate-300">
              {importHistory.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    No import jobs found.
                  </td>
                </tr>
              ) : (
                importHistory.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-900/10">
                    <td className="px-4 py-3 font-medium text-slate-200 max-w-[200px] truncate" title={item.filename}>
                      {item.filename}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">{getStatusBadge(item.status)}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-slate-400">
                      {formatDate(item.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap font-medium">
                      <span className="text-emerald-400">{item.successful_rows}</span>
                      <span className="text-slate-500"> / {item.total_rows}</span>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-indigo-400">
                      {item.mapping_confidence !== null ? `${(item.mapping_confidence * 100).toFixed(0)}%` : '—'}
                    </td>
                    <td className="px-4 py-3 text-center whitespace-nowrap">
                      {item.failed_rows > 0 ? (
                        <button
                          type="button"
                          disabled={downloadingId === item.id}
                          onClick={() => handleDownloadFailed(item.id, item.filename)}
                          className="inline-flex items-center justify-center p-1.5 bg-slate-950/40 hover:bg-slate-950 hover:text-red-400 border border-slate-850 rounded-lg text-slate-400 transition-all cursor-pointer disabled:opacity-50"
                          title="Download Failed Rows Report"
                        >
                          {downloadingId === item.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Download className="w-3.5 h-3.5" />
                          )}
                        </button>
                      ) : (
                        <span className="text-slate-600 font-medium">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="px-4 py-3 border-t border-slate-800/80 bg-slate-950/20 flex items-center justify-between text-xs text-slate-500">
          <span>
            Showing page {Math.floor(historyPagination.skip / historyPagination.limit) + 1}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handlePrevPage}
              disabled={historyPagination.skip === 0 || isLoading}
              className="flex items-center justify-center p-1 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg text-slate-400 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleNextPage}
              disabled={importHistory.length < historyPagination.limit || isLoading}
              className="flex items-center justify-center p-1 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg text-slate-400 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
export default ImportHistoryTable;
