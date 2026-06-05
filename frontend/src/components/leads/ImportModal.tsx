import React, { useState } from 'react';
import { useLeadImportStore } from '../../store/leadImportStore';
import { useAuthStore } from '../../store/authStore';
import { 
  X, Upload, AlertCircle, Loader2, CheckCircle2, 
  ArrowRight, ArrowLeft
} from 'lucide-react';
import { UploadZone } from './UploadZone';
import { MappingPreview } from './MappingPreview';
import { FailedRowsDownload } from './FailedRowsDownload';
import { ImportPreviewResponse, LeadImportResponse } from '../../services/leadImportApi';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

type ImportStep = 'upload' | 'preview_mapping' | 'summary';

export const ImportModal: React.FC<ImportModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const { user } = useAuthStore();
  const { 
    uploadImportFile, 
    previewGoogleSheets, 
    processImport, 
    downloadTemplate, 
    downloadFailedRows 
  } = useLeadImportStore();

  const [step, setStep] = useState<ImportStep>('upload');
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

  if (!isOpen) return null;

  // RBAC protection
  if (!user || (user.role !== 'OrgAdmin' && user.role !== 'Manager')) {
    return null;
  }

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
      setStep('preview_mapping');
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
      setErrorMsg('Last Name is a required field and is missing');
      return;
    }
    if (!columnMapping['title']) {
      setErrorMsg('Job Title/Lead Title is a required field and is missing');
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
      setStep('summary');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to process lead import');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadFailedRows = async (importId: string) => {
    try {
      const blob = await downloadFailedRows(importId);
      const filename = `failed_rows_${importId}.csv`;
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
    if (step === 'summary' && importResult && importResult.successful_rows > 0) {
      onSuccess();
    }
    onClose();
  };

  const getStepProgressWidth = () => {
    if (step === 'upload') return '33%';
    if (step === 'preview_mapping') return '66%';
    return '100%';
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm transition-opacity" onClick={handleClose}></div>

      {/* Modal Container */}
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-800/80 rounded-2xl shadow-2xl flex flex-col max-h-[90vh] z-10 overflow-hidden">
        {/* Progress Bar */}
        <div className="w-full bg-slate-950 h-1">
          <div 
            className="bg-gradient-to-r from-brand-500 to-indigo-500 h-full transition-all duration-300"
            style={{ width: getStepProgressWidth() }}
          />
        </div>

        {/* Header */}
        <div className="px-6 py-4.5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/25 flex items-center justify-center">
              <Upload className="w-5 h-5 text-brand-300" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-100">Bulk Import Leads</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {step === 'upload' && 'Upload file or share Google Sheets URL'}
                {step === 'preview_mapping' && 'Verify headers mapping and preview rows'}
                {step === 'summary' && 'Import processing summary and logs'}
              </p>
            </div>
          </div>
          <button 
            type="button"
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
          {/* Step 1: Upload */}
          {step === 'upload' && (
            <UploadZone
              sourceType={sourceType}
              setSourceType={setSourceType}
              selectedFile={selectedFile}
              setSelectedFile={setSelectedFile}
              sheetsUrl={sheetsUrl}
              setSheetsUrl={setSheetsUrl}
              onDownloadTemplate={downloadTemplateFile}
              setErrorMsg={setErrorMsg}
            />
          )}

          {/* Step 2: Mapping & Preview */}
          {step === 'preview_mapping' && previewData && (
            <MappingPreview
              previewData={previewData}
              columnMapping={columnMapping}
              onMappingChange={handleMappingChange}
              autoAssign={autoAssign}
              setAutoAssign={setAutoAssign}
            />
          )}

          {/* Step 3: Result Summary */}
          {step === 'summary' && importResult && (
            <div className="space-y-6">
              {/* Success Banner */}
              <div className="p-6 bg-slate-950/30 border border-slate-800/60 rounded-2xl flex flex-col sm:flex-row items-center gap-4 text-center sm:text-left">
                <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div className="flex-1 space-y-1">
                  <h4 className="text-base font-bold text-slate-100">Import Batch Processed</h4>
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
              <FailedRowsDownload
                importId={importResult.id}
                failedRowsCount={importResult.failed_rows}
                errorSummary={importResult.error_summary}
                onDownloadFailedRows={handleDownloadFailedRows}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 flex items-center justify-end gap-2.5 bg-slate-950/20">
          {step === 'upload' && (
            <>
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-900/80 active:bg-slate-900/60 rounded-xl text-xs font-semibold text-slate-300 transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
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

          {step === 'preview_mapping' && (
            <>
              <button
                type="button"
                onClick={() => { setStep('upload'); setErrorMsg(null); }}
                className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-900/80 active:bg-slate-900/60 rounded-xl text-xs font-semibold text-slate-300 transition-all cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back
              </button>
              <button
                type="button"
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

          {step === 'summary' && (
            <button
              type="button"
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
export default ImportModal;
