import React, { useEffect, useState } from 'react';
import { useLeadImportStore } from '../../store/leadImportStore';
import { useAuthStore } from '../../store/authStore';
import { ToggleLeft, ToggleRight, Loader2, Users } from 'lucide-react';

export const AssignmentSettings: React.FC = () => {
  const { user } = useAuthStore();
  const { 
    assignmentConfig, 
    fetchAssignmentConfig, 
    toggleAssignmentConfig, 
    isLoading 
  } = useLeadImportStore();
  const [isUpdating, setIsUpdating] = useState(false);

  useEffect(() => {
    if (user && (user.role === 'OrgAdmin' || user.role === 'Manager')) {
      fetchAssignmentConfig();
    }
  }, [user]);

  if (!user || (user.role !== 'OrgAdmin' && user.role !== 'Manager')) {
    return null;
  }

  const handleToggle = async () => {
    if (!assignmentConfig) return;
    setIsUpdating(true);
    try {
      await toggleAssignmentConfig(!assignmentConfig.is_active);
    } catch (err) {
      console.error(err);
    } finally {
      setIsUpdating(false);
    }
  };

  const isActive = assignmentConfig?.is_active ?? false;

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-slate-900/50 border border-slate-800/80 rounded-xl backdrop-blur-md">
      <Users className="w-4 h-4 text-indigo-400" />
      <div className="flex flex-col">
        <span className="text-xs font-semibold text-slate-300">Auto Assignment</span>
        <span className="text-[10px] text-slate-500">Round-robin to active reps</span>
      </div>
      <button
        type="button"
        onClick={handleToggle}
        disabled={isUpdating || isLoading}
        className="flex items-center transition-all focus:outline-none cursor-pointer disabled:opacity-50 ml-2"
        title={isActive ? 'Disable automatic assignment' : 'Enable automatic assignment'}
      >
        {isUpdating ? (
          <Loader2 className="w-6 h-6 text-brand-500 animate-spin" />
        ) : isActive ? (
          <ToggleRight className="w-8 h-8 text-emerald-500 hover:text-emerald-400 transition-colors" />
        ) : (
          <ToggleLeft className="w-8 h-8 text-slate-500 hover:text-slate-400 transition-colors" />
        )}
      </button>
    </div>
  );
};
export default AssignmentSettings;
