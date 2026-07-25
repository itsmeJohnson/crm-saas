import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from 'lucide-react';

interface Props {
  /** value in local `YYYY-MM-DDTHH:mm` form (same as a native datetime-local), or '' */
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const pad = (n: number) => String(n).padStart(2, '0');

const parse = (v: string): Date | null => {
  if (!v) return null;
  const d = new Date(v);
  return isNaN(d.getTime()) ? null : d;
};

/**
 * Custom date + time picker used where the native `datetime-local` popup is
 * confusing — it never auto-closes and covers the surrounding controls. This
 * one closes on an explicit "Done" button or a click outside, and keeps the
 * date grid and time together in one small panel. Emits the same
 * `YYYY-MM-DDTHH:mm` string a native datetime-local would, so callers are
 * unchanged.
 */
export const DateTimePicker: React.FC<Props> = ({ value, onChange, placeholder = 'Select date & time', className = '' }) => {
  const [open, setOpen] = useState(false);
  const selected = useMemo(() => parse(value), [value]);
  // Month currently shown in the grid (first of month).
  const [view, setView] = useState<Date>(() => {
    const base = selected || new Date();
    return new Date(base.getFullYear(), base.getMonth(), 1);
  });
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      const base = selected || new Date();
      setView(new Date(base.getFullYear(), base.getMonth(), 1));
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const emit = (d: Date) => onChange(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`);

  const pickDay = (day: number) => {
    const base = selected || new Date();
    // Default a fresh pick to the current time; keep the time if one is set.
    const h = selected ? selected.getHours() : base.getHours();
    const m = selected ? selected.getMinutes() : base.getMinutes();
    emit(new Date(view.getFullYear(), view.getMonth(), day, h, m));
  };

  const setTime = (h: number, m: number) => {
    const d = selected || new Date();
    emit(new Date(d.getFullYear(), d.getMonth(), d.getDate(), h, m));
  };

  const year = view.getFullYear();
  const month = view.getMonth();
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();
  const isToday = (d: number) => today.getFullYear() === year && today.getMonth() === month && today.getDate() === d;
  const isSelected = (d: number) =>
    !!selected && selected.getFullYear() === year && selected.getMonth() === month && selected.getDate() === d;

  const label = selected
    ? `${selected.getDate()} ${MONTHS[selected.getMonth()]} ${selected.getFullYear()}, ${pad(selected.getHours())}:${pad(selected.getMinutes())}`
    : placeholder;

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-left focus:outline-none focus:border-brand-500/50 cursor-pointer"
      >
        <CalendarIcon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
        <span className={selected ? 'text-slate-200' : 'text-slate-500'}>{label}</span>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-64 p-3 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl">
          <div className="flex items-center justify-between mb-2">
            <button type="button" onClick={() => setView(new Date(year, month - 1, 1))}
                    className="p-1 text-slate-400 hover:text-slate-200 cursor-pointer" aria-label="Previous month">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-semibold text-slate-200">{MONTHS[month]} {year}</span>
            <button type="button" onClick={() => setView(new Date(year, month + 1, 1))}
                    className="p-1 text-slate-400 hover:text-slate-200 cursor-pointer" aria-label="Next month">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-0.5 mb-1">
            {WEEKDAYS.map((w, i) => <div key={i} className="text-center text-[10px] text-slate-500 py-1">{w}</div>)}
          </div>
          <div className="grid grid-cols-7 gap-0.5">
            {Array.from({ length: firstWeekday }).map((_, i) => <div key={`b${i}`} />)}
            {Array.from({ length: daysInMonth }).map((_, i) => {
              const day = i + 1;
              const sel = isSelected(day);
              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => pickDay(day)}
                  className={`h-7 rounded-md text-xs cursor-pointer transition-colors ${
                    sel ? 'bg-brand-500 text-white font-semibold'
                        : isToday(day) ? 'text-brand-400 hover:bg-slate-800'
                        : 'text-slate-300 hover:bg-slate-800'}`}
                >
                  {day}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-800">
            <span className="text-[10px] uppercase tracking-wider text-slate-500">Time</span>
            <select
              aria-label="Hour"
              value={selected ? selected.getHours() : 9}
              onChange={(e) => setTime(parseInt(e.target.value, 10), selected ? selected.getMinutes() : 0)}
              className="bg-slate-950/60 border border-slate-800 rounded-md text-xs text-slate-200 py-1 px-1.5 cursor-pointer"
            >
              {Array.from({ length: 24 }).map((_, h) => <option key={h} value={h}>{pad(h)}</option>)}
            </select>
            <span className="text-slate-400">:</span>
            <select
              aria-label="Minute"
              value={selected ? selected.getMinutes() : 0}
              onChange={(e) => setTime(selected ? selected.getHours() : 9, parseInt(e.target.value, 10))}
              className="bg-slate-950/60 border border-slate-800 rounded-md text-xs text-slate-200 py-1 px-1.5 cursor-pointer"
            >
              {Array.from({ length: 60 }).map((_, m) => <option key={m} value={m}>{pad(m)}</option>)}
            </select>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="ml-auto px-3 py-1 bg-brand-500 hover:bg-brand-600 text-white rounded-md text-xs font-semibold cursor-pointer"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
