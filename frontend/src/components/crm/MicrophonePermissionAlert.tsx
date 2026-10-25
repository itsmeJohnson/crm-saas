import React, { useState } from 'react';
import { Mic, MicOff, AlertCircle, CheckCircle2, X, HelpCircle, RefreshCw } from 'lucide-react';
import { useDialerStore } from '../../store/dialerStore';

interface MicrophonePermissionAlertProps {
  error: string | null;
  onClearError?: () => void;
  className?: string;
  compact?: boolean;
}

export const MicrophonePermissionAlert: React.FC<MicrophonePermissionAlertProps> = ({
  error,
  onClearError,
  className = '',
  compact = false,
}) => {
  const { requestMicrophonePermission, clearError } = useDialerStore();
  const [isRequesting, setIsRequesting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);

  if (!error && !isSuccess) return null;

  const handleDismiss = () => {
    setIsSuccess(false);
    clearError();
    if (onClearError) onClearError();
  };

  const handleRequestPermission = async () => {
    setIsRequesting(true);
    try {
      const granted = await requestMicrophonePermission();
      if (granted) {
        setIsSuccess(true);
        if (onClearError) onClearError();
        setTimeout(() => {
          setIsSuccess(false);
        }, 4000);
      } else {
        setShowInstructions(true);
      }
    } finally {
      setIsRequesting(false);
    }
  };

  if (isSuccess) {
    return (
      <div className={`p-3 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 rounded-xl text-emerald-800 dark:text-emerald-300 flex items-center justify-between text-xs animate-in fade-in duration-200 ${className}`}>
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="font-semibold">Microphone enabled! You can now place and receive calls.</span>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          className="p-1 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 rounded-md transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  const errStr = String(error || '').toLowerCase();
  const isMicError =
    errStr.includes('micro') ||
    errStr.includes('permission') ||
    errStr.includes('mediafailed') ||
    errStr.includes('audio');

  if (!isMicError) {
    return (
      <div className={`p-3 bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-700 dark:text-rose-400 rounded-xl text-xs flex items-center justify-between ${className}`}>
        <div className="flex items-center gap-2 pr-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          className="p-1 hover:bg-rose-100 dark:hover:bg-rose-500/20 rounded-md transition-colors shrink-0"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  if (compact) {
    return (
      <div className={`p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-200 text-xs space-y-2 ${className}`}>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 font-bold text-amber-100">
            <MicOff className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span>Microphone access required</span>
          </div>
          <button
            type="button"
            onClick={handleDismiss}
            className="text-amber-400 hover:text-amber-200 p-0.5 rounded cursor-pointer"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
        <p className="text-[11px] text-amber-300/80 leading-snug">
          To place calls, grant microphone access.
        </p>
        <button
          type="button"
          onClick={handleRequestPermission}
          disabled={isRequesting}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded-lg transition-colors cursor-pointer text-xs disabled:opacity-60"
        >
          {isRequesting ? (
            <>
              <RefreshCw className="w-3 h-3 animate-spin" />
              <span>Prompting Browser...</span>
            </>
          ) : (
            <>
              <Mic className="w-3.5 h-3.5" />
              <span>Enable Microphone</span>
            </>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className={`p-3.5 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950/40 dark:to-orange-950/30 border border-amber-200 dark:border-amber-500/30 rounded-xl shadow-xs text-xs text-amber-900 dark:text-amber-200 space-y-2.5 ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-amber-500/10 dark:bg-amber-500/20 border border-amber-500/30 flex items-center justify-center shrink-0 mt-0.5 text-amber-600 dark:text-amber-400">
            <MicOff className="w-4 h-4" />
          </div>
          <div>
            <h4 className="font-bold text-amber-950 dark:text-amber-100 text-xs flex items-center gap-1.5">
              Microphone Permission Needed
            </h4>
            <p className="text-[11px] text-amber-800 dark:text-amber-300/90 mt-0.5 leading-relaxed">
              To place calls and connect with customers, your browser needs microphone access.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleDismiss}
          className="text-amber-700/60 hover:text-amber-900 dark:text-amber-400/60 dark:hover:text-amber-200 p-1 hover:bg-amber-100 dark:hover:bg-amber-800/30 rounded-md transition-colors"
          title="Dismiss"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-0.5">
        <button
          type="button"
          onClick={handleRequestPermission}
          disabled={isRequesting}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white font-semibold rounded-lg shadow-xs transition-colors cursor-pointer text-xs disabled:opacity-60"
        >
          {isRequesting ? (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>Prompting Browser...</span>
            </>
          ) : (
            <>
              <Mic className="w-3.5 h-3.5" />
              <span>Enable Microphone</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={() => setShowInstructions(!showInstructions)}
          className="flex items-center gap-1 text-[11px] font-medium text-amber-800 dark:text-amber-300 hover:text-amber-950 dark:hover:text-amber-100 underline underline-offset-2 px-1.5 py-1 rounded transition-colors cursor-pointer"
        >
          <HelpCircle className="w-3 h-3" />
          <span>{showInstructions ? 'Hide instructions' : 'How to unblock in browser?'}</span>
        </button>
      </div>

      {showInstructions && (
        <div className="mt-2 p-2.5 bg-amber-100/70 dark:bg-amber-900/30 border border-amber-200/80 dark:border-amber-700/40 rounded-lg text-[11px] text-amber-900 dark:text-amber-200 space-y-1">
          <p className="font-semibold text-amber-950 dark:text-amber-100">If your browser previously blocked microphone access:</p>
          <ol className="list-decimal list-inside space-y-0.5 text-amber-800 dark:text-amber-300 pl-1">
            <li>Click the <span className="font-semibold">tune / lock icon 🔒</span> on the left side of your browser URL bar.</li>
            <li>Locate <span className="font-semibold">Microphone</span> and switch the toggle to <span className="font-semibold text-emerald-700 dark:text-emerald-400">Allow</span>.</li>
            <li>Click the <span className="font-semibold text-amber-700 dark:text-amber-300">"Enable Microphone"</span> button above to confirm.</li>
          </ol>
        </div>
      )}
    </div>
  );
};
