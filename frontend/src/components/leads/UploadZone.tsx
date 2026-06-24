import React, { useRef, useState } from 'react';
import { FileSpreadsheet, Link2, Download } from 'lucide-react';

interface UploadZoneProps {
  sourceType: 'file' | 'google_sheets';
  setSourceType: (type: 'file' | 'google_sheets') => void;
  selectedFile: File | null;
  setSelectedFile: (file: File | null) => void;
  sheetsUrl: string;
  setSheetsUrl: (url: string) => void;
  onDownloadTemplate: (format: 'csv' | 'xlsx') => void;
  setErrorMsg: (msg: string | null) => void;
}

export const UploadZone: React.FC<UploadZoneProps> = ({
  sourceType,
  setSourceType,
  selectedFile,
  setSelectedFile,
  sheetsUrl,
  setSheetsUrl,
  onDownloadTemplate,
  setErrorMsg,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setErrorMsg(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
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

  return (
    <div className="space-y-6">
      {/* Selector Tabs */}
      <div className="flex bg-slate-950/45 p-1 border border-slate-800/80 rounded-xl w-fit">
        <button
          type="button"
          onClick={() => {
            setSourceType('file');
            setErrorMsg(null);
          }}
          className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            sourceType === 'file'
              ? 'bg-slate-900 text-slate-200 shadow-sm border border-slate-800/60'
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          Local File Upload
        </button>
        <button
          type="button"
          onClick={() => {
            setSourceType('google_sheets');
            setErrorMsg(null);
          }}
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
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-all gap-4 ${
            isDragging
              ? 'border-brand-500 bg-brand-500/5'
              : 'border-slate-800 hover:border-slate-700 bg-slate-950/15 hover:bg-slate-950/30'
          }`}
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
                : 'Supports CSV and Excel (.xlsx) formats up to 5MB'}
            </p>
          </div>
        </div>
      ) : (
        /* Google Sheets URL Input */
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-400 block">
            Google Sheets Public Export Link
          </label>
          <div className="relative">
            <Link2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="url"
              placeholder="https://docs.google.com/spreadsheets/d/your-spreadsheet-id/edit?usp=sharing"
              value={sheetsUrl}
              onChange={(e) => {
                setSheetsUrl(e.target.value);
                setErrorMsg(null);
              }}
              className="w-full pl-11 pr-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-brand-500/50 transition-all"
            />
          </div>
          <p className="text-[10px] text-slate-500 leading-normal">
            <span className="font-semibold text-slate-400">Important:</span> Google Sheet must be shared as "Anyone with link can view" so that our backend can fetch and map row content.
          </p>
        </div>
      )}

      {/* Template Downloads */}
      <div className="p-4 bg-slate-950/20 border border-slate-800/80 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h4 className="text-sm font-semibold text-slate-300">Need a baseline layout?</h4>
          <p className="text-xs text-slate-500 mt-0.5">
            Download our standardized leads template with correct headers.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onDownloadTemplate('csv')}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-slate-400" />
            CSV Template
          </button>
          <button
            type="button"
            onClick={() => onDownloadTemplate('xlsx')}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-slate-400" />
            Excel Template
          </button>
        </div>
      </div>
    </div>
  );
};
