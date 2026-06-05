import React from 'react';
import { Sparkles, Table } from 'lucide-react';
import { ImportPreviewResponse } from '../../services/leadImportApi';
import { UserResponse } from '../../services/userApi';

interface MappingPreviewProps {
  previewData: ImportPreviewResponse;
  columnMapping: Record<string, string>;
  onMappingChange: (field: string, val: string) => void;
  assignmentMode: 'AUTO' | 'SPECIFIC_USER' | 'NONE';
  setAssignmentMode: (mode: 'AUTO' | 'SPECIFIC_USER' | 'NONE') => void;
  assignedUserId: string | null;
  setAssignedUserId: (id: string | null) => void;
  employees: UserResponse[];
  isLoadingEmployees: boolean;
}

export const MappingPreview: React.FC<MappingPreviewProps> = ({
  previewData,
  columnMapping,
  onMappingChange,
  assignmentMode,
  setAssignmentMode,
  assignedUserId,
  setAssignedUserId,
  employees,
  isLoadingEmployees,
}) => {
  const fieldsConfig = [
    { key: 'title', label: 'Lead Title / Job Title', required: true, desc: 'Position name or title of the lead' },
    { key: 'last_name', label: 'Last Name', required: true, desc: 'Contact surname' },
    { key: 'first_name', label: 'First Name', required: false, desc: 'Contact given name' },
    { key: 'email', label: 'Email', required: false, desc: 'Primary contact email' },
    { key: 'phone', label: 'Phone', required: false, desc: 'Contact phone number' },
    { key: 'company_name', label: 'Company', required: false, desc: 'Employer company' },
    { key: 'value', label: 'Deal Value', required: false, desc: 'Est. opportunity dollar value' },
    { key: 'source', label: 'Lead Source', required: false, desc: 'Original marketing channel' },
  ];

  const getConfidenceBadgeClass = (confidence: number) => {
    if (confidence >= 1.0) {
      return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
    } else if (confidence >= 0.8) {
      return 'bg-brand-500/10 text-brand-300 border border-brand-500/20';
    } else if (confidence >= 0.6) {
      return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
    }
    return 'bg-slate-500/10 text-slate-400 border border-slate-500/20';
  };

  return (
    <div className="space-y-6">
      {/* Fields Mapping Config */}
      <div>
        <h4 className="text-sm font-bold text-slate-300 mb-3 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-brand-400" />
          Map File Headers to Lead Properties
        </h4>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {fieldsConfig.map((field) => {
            const mappedCol = columnMapping[field.key] || '';
            const suggestion = previewData.suggested_mapping[field.key];
            const hasSuggestion = suggestion && suggestion.column;
            
            return (
              <div 
                key={field.key} 
                className="p-3.5 bg-slate-950/20 border border-slate-800/80 rounded-xl space-y-2.5 flex flex-col justify-between"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-xs font-semibold text-slate-200 flex items-center gap-1">
                      {field.label}
                      {field.required && <span className="text-red-500 font-bold">*</span>}
                    </span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">{field.desc}</span>
                  </div>

                  {hasSuggestion && mappedCol === suggestion.column && (
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${getConfidenceBadgeClass(suggestion.confidence)}`}>
                      {suggestion.confidence >= 1.0 ? 'Exact' : suggestion.confidence >= 0.8 ? 'Alias' : 'Fuzzy'} ({(suggestion.confidence * 100).toFixed(0)}%)
                    </span>
                  )}
                </div>

                <select
                  value={mappedCol}
                  onChange={(e) => onMappingChange(field.key, e.target.value)}
                  className={`w-full px-3 py-2 bg-slate-900 border rounded-lg text-xs text-slate-300 focus:outline-none transition-all ${
                    field.required && !mappedCol 
                      ? 'border-red-950 text-red-400/80 focus:border-red-500' 
                      : 'border-slate-800 focus:border-brand-500/40'
                  }`}
                >
                  <option value="">
                    {field.required ? 'Select Required Column...' : 'Skip Column / Don\'t Import'}
                  </option>
                  {previewData.headers.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
      </div>

      {/* Data Row Previews */}
      <div className="space-y-2">
        <h4 className="text-sm font-bold text-slate-300 flex items-center gap-2">
          <Table className="w-4 h-4 text-indigo-400" />
          Source Data Preview
        </h4>
        
        <div className="border border-slate-850 rounded-xl overflow-hidden bg-slate-950/20 max-h-48 overflow-y-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/40 text-slate-400 font-semibold sticky top-0">
                {previewData.headers.map((h) => (
                  <th key={h} className="px-4 py-2 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {previewData.preview_rows.map((row, idx) => (
                <tr key={idx} className="hover:bg-slate-900/20 text-slate-300">
                  {previewData.headers.map((h) => (
                    <td key={h} className="px-4 py-2 truncate max-w-[150px]" title={row[h]}>
                      {row[h] !== null && row[h] !== undefined ? String(row[h]) : '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Lead Assignment Configuration */}
      <div className="p-5 bg-slate-950/20 border border-slate-800/80 rounded-2xl space-y-4">
        <div>
          <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Lead Assignment Mode</h4>
          <p className="text-[10px] text-slate-500 mt-0.5">
            Choose how you want to distribute the imported leads.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* NONE Option */}
          <label 
            className={`p-3.5 border rounded-xl flex flex-col justify-between cursor-pointer transition-all ${
              assignmentMode === 'NONE' 
                ? 'border-brand-500/50 bg-brand-500/5 text-slate-200' 
                : 'border-slate-800 hover:border-slate-700 bg-slate-900/10 text-slate-400'
            }`}
          >
            <div className="flex items-center gap-2">
              <input
                type="radio"
                name="assignmentMode"
                value="NONE"
                checked={assignmentMode === 'NONE'}
                onChange={() => {
                  setAssignmentMode('NONE');
                  setAssignedUserId(null);
                }}
                className="w-4 h-4 accent-brand-500 cursor-pointer bg-slate-950"
              />
              <span className="text-xs font-semibold">Unassigned</span>
            </div>
            <span className="text-[9px] text-slate-500 mt-1.5 block">
              Leads remain unassigned.
            </span>
          </label>

          {/* AUTO Option */}
          <label 
            className={`p-3.5 border rounded-xl flex flex-col justify-between cursor-pointer transition-all ${
              assignmentMode === 'AUTO' 
                ? 'border-brand-500/50 bg-brand-500/5 text-slate-200' 
                : 'border-slate-800 hover:border-slate-700 bg-slate-900/10 text-slate-400'
            }`}
          >
            <div className="flex items-center gap-2">
              <input
                type="radio"
                name="assignmentMode"
                value="AUTO"
                checked={assignmentMode === 'AUTO'}
                onChange={() => {
                  setAssignmentMode('AUTO');
                  setAssignedUserId(null);
                }}
                className="w-4 h-4 accent-brand-500 cursor-pointer bg-slate-950"
              />
              <span className="text-xs font-semibold">Round Robin</span>
            </div>
            <span className="text-[9px] text-slate-500 mt-1.5 block">
              Distribute to active employees equally.
            </span>
          </label>

          {/* SPECIFIC_USER Option */}
          <label 
            className={`p-3.5 border rounded-xl flex flex-col justify-between cursor-pointer transition-all ${
              assignmentMode === 'SPECIFIC_USER' 
                ? 'border-brand-500/50 bg-brand-500/5 text-slate-200' 
                : 'border-slate-800 hover:border-slate-700 bg-slate-900/10 text-slate-400'
            }`}
          >
            <div className="flex items-center gap-2">
              <input
                type="radio"
                name="assignmentMode"
                value="SPECIFIC_USER"
                checked={assignmentMode === 'SPECIFIC_USER'}
                onChange={() => setAssignmentMode('SPECIFIC_USER')}
                className="w-4 h-4 accent-brand-500 cursor-pointer bg-slate-950"
              />
              <span className="text-xs font-semibold">Assign to User</span>
            </div>
            <span className="text-[9px] text-slate-500 mt-1.5 block">
              Assign all leads to one selected user.
            </span>
          </label>
        </div>

        {/* Specific User Dropdown */}
        {assignmentMode === 'SPECIFIC_USER' && (
          <div className="space-y-2 pt-2 border-t border-slate-850/50">
            <label className="text-xs font-semibold text-slate-300">Select Assignee</label>
            {isLoadingEmployees ? (
              <div className="flex items-center gap-2 text-xs text-slate-500 py-1">
                <span className="w-3.5 h-3.5 border-2 border-slate-500 border-t-transparent rounded-full animate-spin"></span>
                Fetching active employees...
              </div>
            ) : employees.length === 0 ? (
              <div className="p-3 bg-slate-900/40 border border-slate-800 rounded-xl text-center text-xs text-slate-500">
                No active employee users found in your organization.
              </div>
            ) : (
              <select
                value={assignedUserId || ''}
                onChange={(e) => setAssignedUserId(e.target.value || null)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-brand-500/40"
              >
                <option value="">-- Choose User --</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.first_name || ''} {emp.last_name || ''} ({emp.email})
                  </option>
                ))}
              </select>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
