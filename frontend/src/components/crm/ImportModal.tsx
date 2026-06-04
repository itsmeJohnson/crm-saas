import React, { useState, useRef } from 'react';
import { useLeadStore } from '../../store/leadStore';
import { 
  X, Upload, AlertCircle, Loader2, Sparkles, CheckCircle2, 
  Download, ArrowRight, Table, Link2, FileSpreadsheet, AlertTriangle
} from 'lucide-react';
import { ImportPreviewResponse, LeadImportResponse } from '../../services/leadApi';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ImportModal: React.FC<ImportModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const { 
    uploadImportFile, 
    previewGoogleSheets, 
    processImport, 
    downloadTemplate, 
    downloadFailedRows 
  } = useLeadStore();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [sourceType, setSourceType] = useState<'file' | 'google_sheets'>('file');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sheetsUrl, setSheetsUrl] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  // Import Preview State
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [autoAssign, setAutoAssign] = useState(true);

  // Import Result State
  const [importResult, setImportResult] = useState<LeadImportResponse | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setErrorMsg(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (ext === 'csv' || ext === 'xlsx') {
        setSelectedFile(file);
        setErrorMsg(null);
      } else {
        setErrorMsg('Only CSV and XLSX files are supported');
      }
    }
  };

  const downloadTemplateFile = async (format: 'csv' | 'xlsx') => {
    try {
      const blob = await downloadTemplate(format);
      const filename = `leads_template.${format}`;
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to download template');
    }
  };

  const handleUploadOrFetch = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      let res: ImportPreviewResponse;
      if (sourceType === 'file') {
        if (!selectedFile) {
          setErrorMsg('Please select a file to import');
          setIsLoading(false);
          return;
        }
        res = await uploadImportFile(selectedFile);
      } else {
        if (!sheetsUrl.trim()) {
          setErrorMsg('Please enter a Google Sheets URL');
          setIsLoading(false);
          return;
        }
        res = await previewGoogleSheets(sheetsUrl.trim());
      }

      setPreviewData(res);
      
      // Initialize Column Mapping from suggested mapping
      const mapping: Record<string, string> = {};
      const fields = ['first_name', 'last_name', 'email', 'phone', 'company_name', 'title', 'value', 'source'];
      
      fields.forEach(field => {
        const suggestion = res.suggested_mapping[field];
        if (suggestion && suggestion.column) {
          mapping[field] = suggestion.column;
        } else {
          mapping[field] = '';
        }
      });
      
      setColumnMapping(mapping);
      setStep(2);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to parse import source');
    } finally {
      setIsLoading(false);
    }
  };

  const handleMappingChange = (field: string, val: string) => {
    setColumnMapping(prev => ({
      ...prev,
      [field]: val
    }));
  };

  const handleProcessImport = async () => {
    if (!previewData) return;
    
    // Validate that required fields are mapped
    if (!columnMapping['last_name']) {
      setErrorMsg('Last Name is a required field and must be mapped to a column');
      return;
    }
    if (!columnMapping['title']) {
      setErrorMsg('Job Title/Lead Title is a required field and must be mapped to a column');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    try {
      const res = await processImport({
        file_token: previewData.file_token,
        source_type: sourceType,
        column_mapping: columnMapping,
        auto_assign: autoAssign
      });
      setImportResult(res);
      setStep(3);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to process lead import');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadFailedRows = async () => {
    if (!importResult) return;
    try {
      const blob = await downloadFailedRows(importResult.id);
      const filename = `failed_rows_${importResult.id}.csv`;
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to download error report');
    }
  };

  const handleClose = () => {
    if (step === 3 && importResult && importResult.successful_rows > 0) {
      onSuccess();
    }
    onClose();
  };

  const fieldsConfig = [
    { key: 'title', label: 'Lead Title / Job Title', required: true, desc: 'Position name or title of the lead' },
    { key: 'last_name', label: 'Last Name', required: true, desc: 'Contact surname' },
    { key: 'first_name', label: 'First Name', required: false, desc: 'Contact given name' },
    { key: 'email', label: 'Email', required: false, desc: 'Primary contact email' },
    { key: 'phone', label: 'Phone', required: false, desc: 'Contact phone number' },
    { key: 'company_name', label: 'Company', required: false, desc: 'Employer company' },
    { key: 'value', label: 'Deal Value', required: false, desc: 'Est. opportunity dollar value' },
    { key: 'source', label: 'Lead Source', required: false, desc: 'Original marketing channel' }
  ];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm transition-opacity" onClick={handleClose}></div>

      {/* Modal Container */}
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-800/80 rounded-2xl shadow-2xl flex flex-col max-h-[90vh] z-10 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4.5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/25 flex items-center justify-center">
              <Upload className="w-5 h-5 text-brand-300" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-100">Bulk Import Leads</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {step === 1 && 'Upload file or share Google Sheets URL'}
                {step === 2 && 'Verify headers mapping and preview rows'}
                {step === 3 && 'Import processing summary and logs'}
              </p>
            </div>
          </div>
          <button 
            onClick={handleClose} 
            className="p-1.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-950/50 text-slate-400 hover:text-slate-200 rounded-xl transition-all cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Error Callout */}
        {errorMsg && (
          <div className="mx-6 mt-4 p-3 bg-red-950/20 border border-red-900/30 text-red-400 rounded-xl flex items-start gap-2.5 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Import Error:</span> {errorMsg}
            </div>
          </div>
        )}

        {/* Scrollable Body Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Step 1: Upload / Input */}
          {step === 1 && (
            <div className="space-y-6">
              {/* Selector Tabs */}
              <div className="flex bg-slate-950/40 p-1 border border-slate-800/80 rounded-xl w-fit">
                <button
                  onClick={() => { setSourceType('file'); setErrorMsg(null); }}
                  className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                    sourceType === 'file' 
                      ? 'bg-slate-900 text-slate-200 shadow-sm border border-slate-800/60' 
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  Local File Upload
                </button>
                <button
                  onClick={() => { setSourceType('google_sheets'); setErrorMsg(null); }}
                  className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                    sourceType === 'google_sheets' 
                      ? 'bg-slate-900 text-slate-200 shadow-sm border border-slate-800/60' 
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  Google Sheets Link
                </button>
              </div>

              {sourceType === 'file' ? (
                /* Drag & Drop Area */
                <div
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-800 hover:border-slate-700 bg-slate-950/15 hover:bg-slate-950/30 rounded-2xl p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-all gap-4"
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    accept=".csv, .xlsx"
                    className="hidden"
                  />
                  <div className="w-12 h-12 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center shadow-inner">
                    <FileSpreadsheet className="w-6 h-6 text-brand-400" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-200">
                      {selectedFile ? selectedFile.name : 'Choose a file or drag it here'}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      {selectedFile 
                        ? `${(selectedFile.size / 1024).toFixed(1)} KB` 
                        : 'Supports CSV and Excel (.xlsx) formats up to 10MB'}
                    </p>
                  </div>
                </div>
              ) : (
                /* Google Sheets URL Input */
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 block">Google Sheets Public Export Link</label>
                  <div className="relative">
                    <Link2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      type="url"
                      placeholder="https://docs.google.com/spreadsheets/d/your-spreadsheet-id/edit?usp=sharing"
                      value={sheetsUrl}
                      onChange={(e) => { setSheetsUrl(e.target.value); setErrorMsg(null); }}
                      className="w-full pl-11 pr-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-brand-500/50 transition-all"
                    />
                  </div>
                  <p className="text-[10px] text-slate-500 leading-normal">
                    <span className="font-semibold text-slate-400">Important:</span> Google Sheet must be shared as "Anyone with link can view" to allow our backend to fetch and map row content.
                  </p>
                </div>
              )}

              {/* Template Downloads */}
              <div className="p-4 bg-slate-950/20 border border-slate-800/80 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h4 className="text-sm font-semibold text-slate-300">Need a baseline layout?</h4>
                  <p className="text-xs text-slate-500 mt-0.5">Download our standardized leads template with correct headers.</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => downloadTemplateFile('csv')}
                    className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5 text-slate-400" />
                    CSV Template
                  </button>
                  <button
                    onClick={() => downloadTemplateFile('xlsx')}
                    className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5 text-slate-400" />
                    Excel Template
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Mapping & Preview */}
          {step === 2 && previewData && (
            <div className="space-y-6">
              {/* Fields Mapping Config */}
              <div>
                <h4 className="text-sm font-bold text-slate-300 mb-3 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-brand-400" />
                  Map File Headers to Lead Properties
                </h4>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {fieldsConfig.map(field => {
                    const mappedCol = columnMapping[field.key];
                    const suggestion = previewData.suggested_mapping[field.key];
                    const hasSuggestion = suggestion && suggestion.column;
                    
                    return (
                      <div 
                        key={field.key} 
                        className="p-3 bg-slate-950/20 border border-slate-800/80 rounded-xl space-y-2 flex flex-col justify-between"
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
                            <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${
                              suggestion.confidence >= 1.0 
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                                : 'bg-brand-500/10 text-brand-300 border border-brand-500/20'
                            }`}>
                              Auto Match ({(suggestion.confidence * 100).toFixed(0)}%)
                            </span>
                          )}
                        </div>

                        <select
                          value={mappedCol}
                          onChange={(e) => handleMappingChange(field.key, e.target.value)}
                          className={`w-full px-3 py-2 bg-slate-900 border rounded-lg text-xs text-slate-300 focus:outline-none transition-all ${
                            field.required && !mappedCol 
                              ? 'border-red-950 text-red-400/80 focus:border-red-500' 
                              : 'border-slate-800 focus:border-brand-500/40'
                          }`}
                        >
                          <option value="">{field.required ? 'Select Required Column...' : 'Skip Column / Don\'t Import'}</option>
                          {previewData.headers.map(h => (
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
                        {previewData.headers.map(h => (
                          <th key={h} className="px-4 py-2 whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {previewData.preview_rows.map((row, idx) => (
                        <tr key={idx} className="hover:bg-slate-900/20 text-slate-300">
                          {previewData.headers.map(h => (
                            <td key={h} className="px-4 py-2 truncate max-w-[150px]" title={row[h]}>
                              {row[h] || '—'}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Auto assignment settings */}
              <div className="p-4 bg-slate-950/20 border border-slate-800/80 rounded-2xl flex items-center gap-3">
                <input
                  type="checkbox"
                  id="auto_assign"
                  checked={autoAssign}
                  onChange={(e) => setAutoAssign(e.target.checked)}
                  className="w-4.5 h-4.5 accent-brand-500 rounded border-slate-800 text-brand-600 focus:ring-0 focus:ring-offset-0 bg-slate-950 cursor-pointer"
                />
                <div>
                  <label htmlFor="auto_assign" className="text-xs font-semibold text-slate-200 cursor-pointer block">
                    Trigger Auto Assignment Logic
                  </label>
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    Automatically distribute newly imported valid leads to active employees round-robin.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Result Summary */}
          {step === 3 && importResult && (
            <div className="space-y-6">
              {/* Success Banner */}
              <div className="p-6 bg-slate-950/30 border border-slate-800/60 rounded-2xl flex flex-col sm:flex-row items-center gap-4 text-center sm:text-left">
                <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div className="flex-1 space-y-1">
                  <h4 className="text-base font-bold text-slate-100">Import Batch Processed Successfully</h4>
                  <p className="text-xs text-slate-400 leading-normal">
                    Your file mapping has been run. Valid rows have been added, and any failures have been compiled.
                  </p>
                </div>
              </div>

              {/* Metric widgets */}
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 bg-slate-950/40 border border-slate-850 rounded-xl text-center">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Total Processed</span>
                  <span className="text-xl font-bold text-slate-200 block mt-1">{importResult.total_rows}</span>
                </div>
                <div className="p-4 bg-slate-950/40 border border-slate-850 rounded-xl text-center">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block text-emerald-400">Successful</span>
                  <span className="text-xl font-bold text-emerald-400 block mt-1">{importResult.successful_rows}</span>
                </div>
                <div className="p-4 bg-slate-950/40 border border-slate-850 rounded-xl text-center">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block text-red-400">Failed Rows</span>
                  <span className={`text-xl font-bold block mt-1 ${importResult.failed_rows > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                    {importResult.failed_rows}
                  </span>
                </div>
              </div>

              {/* Validation Failure summary report */}
              {importResult.failed_rows > 0 && importResult.error_summary && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-4">
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-amber-500" />
                      Row Validation Errors ({importResult.failed_rows})
                    </h4>
                    <button
                      onClick={handleDownloadFailedRows}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer"
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
                        {importResult.error_summary.map((err, idx) => (
                          <tr key={idx} className="hover:bg-slate-900/20 text-slate-300">
                            <td className="px-4 py-2 font-medium text-slate-400">{err.row}</td>
                            <td className="px-4 py-2 font-semibold truncate max-w-[150px]">{err.email || 'N/A'}</td>
                            <td className="px-4 py-2 text-red-400/80">{err.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 flex items-center justify-end gap-2.5 bg-slate-950/20">
          {step === 1 && (
            <>
              <button
                onClick={handleClose}
                className="px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-900/80 active:bg-slate-900/60 rounded-xl text-xs font-semibold text-slate-300 transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleUploadOrFetch}
                disabled={isLoading}
                className="flex items-center gap-1.5 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 rounded-xl text-xs font-semibold text-white transition-all shadow-md shadow-brand-500/10 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Analyzing Data...
                  </>
                ) : (
                  <>
                    Next
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </>
          )}

          {step === 2 && (
            <>
              <button
                onClick={() => { setStep(1); setErrorMsg(null); }}
                className="px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-900/80 active:bg-slate-900/60 rounded-xl text-xs font-semibold text-slate-300 transition-all cursor-pointer"
              >
                Back
              </button>
              <button
                onClick={handleProcessImport}
                disabled={isLoading}
                className="flex items-center gap-1.5 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 rounded-xl text-xs font-semibold text-white transition-all shadow-md shadow-brand-500/10 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Running Import...
                  </>
                ) : (
                  <>
                    Process Mapping
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </>
          )}

          {step === 3 && (
            <button
              onClick={handleClose}
              className="px-5 py-2.5 bg-slate-900 border border-slate-800 hover:bg-slate-900/80 rounded-xl text-xs font-semibold text-slate-200 transition-all cursor-pointer"
            >
              Done & Close
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
