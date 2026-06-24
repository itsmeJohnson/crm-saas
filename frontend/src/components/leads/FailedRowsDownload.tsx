import React from 'react';
import { AlertTriangle, Download } from 'lucide-react';

interface ErrorSummaryItem {
  row: number;
  email: string | null;
  reason: string;
}

interface FailedRowsDownloadProps {
  importId: string;
  failedRowsCount: number;
  errorSummary: ErrorSummaryItem[] | null;
  onDownloadFailedRows: (importId: string) => void;
}

export const FailedRowsDownload: React.FC<FailedRowsDownloadProps> = ({
  importId,
  failedRowsCount,
  errorSummary,
  onDownloadFailedRows,
}) => {
  if (failedRowsCount === 0 || !errorSummary || errorSummary.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          Row Validation Errors ({failedRowsCount})
        </h4>
        <button
          type="button"
          onClick={() => onDownloadFailedRows(importId)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer shadow-md"
        >
          <Download className="w-3.5 h-3.5 text-slate-400" />
          Download Error Report
        </button>
      </div>

      <div className="border border-slate-850 rounded-xl overflow-hidden bg-slate-950/20 max-h-48 overflow-y-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/40 text-slate-400 font-semibold sticky top-0">
              <th className="px-4 py-2 w-16">Row</th>
              <th className="px-4 py-2 w-48">Identifier Email</th>
              <th className="px-4 py-2">Failure Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {errorSummary.map((err, idx) => (
              <tr key={idx} className="hover:bg-slate-900/20 text-slate-300">
                <td className="px-4 py-2 font-medium text-slate-400">{err.row}</td>
                <td className="px-4 py-2 font-semibold truncate max-w-[150px]">
                  {err.email || 'N/A'}
                </td>
                <td className="px-4 py-2 text-red-400/80">{err.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
