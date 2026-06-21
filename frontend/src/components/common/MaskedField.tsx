import React from 'react';
import { Lock } from 'lucide-react';

interface MaskedFieldProps {
  value: string | null | undefined;
  fallback?: string;
}

/**
 * MaskedField renders a phone number (or any field) with visual cues if it is masked.
 * 
 * DESIGN ALIGNMENT & SECURITY:
 * Because phone masking is done natively on the server layer before the response crosses the network edge,
 * the frontend client only ever receives the masked string (e.g., '+91********10') for telecallers.
 * Thus, even if a user inspects the DOM, react state, or network request payloads, they cannot access
 * the raw number, relying entirely on the server-masked payload.
 */
export const MaskedField: React.FC<MaskedFieldProps> = ({ value, fallback = '-' }) => {
  if (!value) {
    return <span className="text-slate-400">{fallback}</span>;
  }

  const isMasked = value.includes('*');

  return (
    <div className="inline-flex items-center gap-1.5 font-mono text-sm tracking-wide">
      {isMasked ? (
        <>
          <span className="text-slate-400 font-medium select-none bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded border border-slate-200/50 dark:border-slate-700/50">
            {value}
          </span>
          <span className="relative group flex items-center justify-center text-indigo-500 bg-indigo-50 dark:bg-indigo-950/40 p-1 rounded-full border border-indigo-100/50 dark:border-indigo-900/30">
            <Lock className="w-3.5 h-3.5" />
            <span className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-1.5 hidden group-hover:block w-max bg-slate-900 text-white text-[10px] px-2 py-1 rounded shadow-lg pointer-events-none select-none font-sans z-50">
              Protected Number
            </span>
          </span>
        </>
      ) : (
        <span className="text-slate-700 dark:text-slate-300 font-medium">
          {value}
        </span>
      )}
    </div>
  );
};
