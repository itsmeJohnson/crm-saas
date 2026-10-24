import React, { useEffect, useState, useCallback } from 'react';
import { LogIn, LogOut, RotateCcw, Coffee } from 'lucide-react';
import { attendanceApi, MyToday } from '../../services/attendanceApi';
import { useAuthStore } from '../../store/authStore';

export const HeaderAttendanceControl: React.FC = () => {
  const { user } = useAuthStore();
  const [data, setData] = useState<MyToday | null>(null);
  const [loading, setLoading] = useState(false);
  const [showBreakMenu, setShowBreakMenu] = useState(false);
  const [showConfirmPunchOut, setShowConfirmPunchOut] = useState(false);

  const fetchAttendance = useCallback(async () => {
    try {
      const res = await attendanceApi.myToday();
      setData(res);
    } catch {
      // Ignore if user has no attendance profile
    }
  }, []);

  useEffect(() => {
    fetchAttendance();
    const handleUpdate = () => {
      fetchAttendance();
    };
    window.addEventListener('attendance-updated', handleUpdate);
    return () => window.removeEventListener('attendance-updated', handleUpdate);
  }, [fetchAttendance]);

  // Don't render for superadmins who do not track floor shifts
  if (user?.role === 'SuperAdmin' && user?.email !== 'samarthasankalpa@gmail.com') {
    return null;
  }

  const isPunchedIn = Boolean(data?.record?.clock_in_at && !data?.record?.clock_out_at);
  const isPunchedOutToday = Boolean(data?.record?.clock_in_at && data?.record?.clock_out_at);
  const isOnBreak = Boolean(data?.on_break);

  const handleClockIn = async () => {
    setLoading(true);
    try {
      if (isPunchedOutToday) {
        try {
          await attendanceApi.resumeShift();
        } catch {
          await attendanceApi.clockIn({ resume: true });
        }
      } else {
        await attendanceApi.clockIn();
      }
      window.dispatchEvent(new CustomEvent('attendance-updated'));
      await fetchAttendance();
    } catch (err: any) {
      alert(err?.response?.data?.detail || err?.message || 'Failed to punch in');
    } finally {
      setLoading(false);
    }
  };

  const handleClockOut = async () => {
    setLoading(true);
    setShowConfirmPunchOut(false);
    try {
      await attendanceApi.clockOut();
      window.dispatchEvent(new CustomEvent('attendance-updated'));
      await fetchAttendance();
    } catch (err: any) {
      alert(err?.response?.data?.detail || err?.message || 'Failed to punch out');
    } finally {
      setLoading(false);
    }
  };

  const handleStartBreak = async (reason: string) => {
    setLoading(true);
    setShowBreakMenu(false);
    try {
      await attendanceApi.breakStart(reason);
      window.dispatchEvent(new CustomEvent('attendance-updated'));
      await fetchAttendance();
    } catch (err: any) {
      alert(err?.response?.data?.detail || err?.message || 'Failed to start break');
    } finally {
      setLoading(false);
    }
  };

  const handleEndBreak = async () => {
    setLoading(true);
    try {
      await attendanceApi.breakEnd();
      window.dispatchEvent(new CustomEvent('attendance-updated'));
      await fetchAttendance();
    } catch (err: any) {
      alert(err?.response?.data?.detail || err?.message || 'Failed to resume from break');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex items-center gap-1.5">
      {/* Attendance Status Pill */}
      {isPunchedIn ? (
        isOnBreak ? (
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            <span>On Break</span>
            <button
              onClick={handleEndBreak}
              disabled={loading}
              title="Resume shift from break"
              className="ml-1 px-1.5 py-0.5 rounded bg-amber-500/30 hover:bg-amber-500/50 text-[10px] text-amber-200 transition"
            >
              Resume
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <div className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>On Duty</span>
            </div>

            {/* Break Trigger Dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowBreakMenu(!showBreakMenu)}
                disabled={loading}
                title="Shift break options"
                className="p-1 rounded-lg border border-[var(--border-color)] hover:bg-[var(--bg-card-hover)] text-[var(--text-secondary)] hover:text-amber-300 transition"
              >
                <Coffee className="w-3.5 h-3.5" />
              </button>

              {showBreakMenu && (
                <div className="absolute right-0 mt-1 w-36 bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-xl shadow-xl py-1 z-50 animate-fade-in text-xs">
                  <p className="px-3 py-1 text-[10px] uppercase font-bold text-[var(--text-muted)] tracking-wider">
                    Take Break
                  </p>
                  {['Tea', 'Lunch', 'Meeting', 'Personal'].map((reason) => (
                    <button
                      key={reason}
                      onClick={() => handleStartBreak(reason)}
                      className="w-full text-left px-3 py-1.5 hover:bg-[var(--bg-card-hover)] text-[var(--text-primary)] transition"
                    >
                      {reason} Break
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Quick Punch Out Trigger */}
            <button
              onClick={() => setShowConfirmPunchOut(true)}
              disabled={loading}
              title="Punch out / End shift"
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 transition disabled:opacity-50"
            >
              <LogOut className="w-3 h-3 text-rose-400" />
              <span className="hidden sm:inline">Punch Out</span>
            </button>
          </div>
        )
      ) : isPunchedOutToday ? (
        <div className="flex items-center gap-1.5">
          <div className="hidden sm:flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <span>Shift Ended</span>
          </div>
          <button
            onClick={handleClockIn}
            disabled={loading}
            title="Resume your shift"
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-gradient-to-r from-amber-500 to-emerald-600 hover:from-amber-400 hover:to-emerald-500 text-white shadow-sm transition disabled:opacity-50"
          >
            <RotateCcw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            <span>Resume Shift</span>
          </button>
        </div>
      ) : (
        <button
          onClick={handleClockIn}
          disabled={loading}
          title="Punch in to start working"
          className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-[11px] font-bold bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white shadow-sm shadow-emerald-500/20 transition disabled:opacity-50"
        >
          <LogIn className="w-3.5 h-3.5" />
          <span>{loading ? 'Punching In...' : 'Punch In'}</span>
        </button>
      )}

      {/* Confirmation Modal to Prevent Accidental Punch Out */}
      {showConfirmPunchOut && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass-panel border border-[var(--border-color)] rounded-2xl p-6 max-w-sm w-full bg-[var(--bg-surface)] shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-rose-400">
              <LogOut className="w-6 h-6" />
              <h3 className="text-base font-bold text-[var(--text-primary)]">End Shift (Punch Out)?</h3>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              This will mark your attendance record as completed for today and stop the dialer queue. You can resume later if needed.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowConfirmPunchOut(false)}
                className="px-4 py-2 text-xs font-semibold rounded-xl border border-[var(--border-color)] text-[var(--text-secondary)] hover:bg-[var(--bg-card-hover)] transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleClockOut}
                disabled={loading}
                className="px-4 py-2 text-xs font-semibold rounded-xl bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/30 transition disabled:opacity-50"
              >
                {loading ? 'Punching Out...' : 'Confirm Punch Out'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
