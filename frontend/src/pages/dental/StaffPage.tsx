import React, { useState, useEffect } from 'react';
import {
  Users, RefreshCw
} from 'lucide-react';
import { api } from '../../services/api';

export const StaffPage: React.FC = () => {
  const [users, setUsers] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/users/?limit=50');
      setUsers(res.data?.items || res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
            <Users className="w-6 h-6 text-brand-400" />
            Clinic Staff & Operational Team
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Receptionists, patient coordinators, dental hygienists, clinic managers & staff permissions.
          </p>
        </div>
      </div>

      {/* Staff Table */}
      <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                <th className="px-6 py-4">Staff Member</th>
                <th className="px-4 py-4">Role / Title</th>
                <th className="px-4 py-4">Contact Phone</th>
                <th className="px-4 py-4">Email</th>
                <th className="px-4 py-4">System Access Role</th>
                <th className="px-6 py-4 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-400">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto text-brand-400 mb-2" />
                    Loading staff members...
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-800/30 transition">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-brand-500/15 border border-brand-500/25 flex items-center justify-center text-brand-400 font-bold text-xs">
                          {u.first_name?.[0]}{u.last_name?.[0]}
                        </div>
                        <span className="font-bold text-slate-100">{u.first_name} {u.last_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-slate-300 font-medium">
                      {u.email?.includes('reception') ? 'Head Receptionist'
                        : u.email?.includes('manager') ? 'Clinic Operations Manager'
                        : u.email?.includes('dr.') ? 'Attending Dental Surgeon'
                        : 'Practice Administrator'}
                    </td>
                    <td className="px-4 py-4 text-slate-300">{u.phone || '+91 9820445566'}</td>
                    <td className="px-4 py-4 text-slate-400">{u.email}</td>
                    <td className="px-4 py-4">
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                        {u.role}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-300 [.light_&]:text-emerald-700 border border-emerald-500/30">
                        Active
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
