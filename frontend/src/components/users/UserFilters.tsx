import React from 'react';
import { Search, RotateCcw } from 'lucide-react';
import { useUserStore } from '../../store/userStore';

export const UserFilters: React.FC = () => {
  const { filters, setFilters, resetFilters } = useUserStore();

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFilters({ search: e.target.value });
  };

  const handleRoleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFilters({ role: e.target.value });
  };

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFilters({ status: e.target.value });
  };

  return (
    <div className="glass-panel p-5 rounded-2xl border border-slate-800/80 mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="flex-1 flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={filters.search}
            onChange={handleSearchChange}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
          />
        </div>

        {/* Role Filter */}
        <div className="w-full sm:w-48">
          <select
            value={filters.role}
            onChange={handleRoleChange}
            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
          >
            <option value="All">All Roles</option>
            <option value="OrgAdmin">Admins</option>
            <option value="Manager">Managers</option>
            <option value="Employee">Employees</option>
          </select>
        </div>

        {/* Status Filter */}
        <div className="w-full sm:w-48">
          <select
            value={filters.status}
            onChange={handleStatusChange}
            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
          >
            <option value="All">All Statuses</option>
            <option value="Active">Active</option>
            <option value="Inactive">Inactive</option>
          </select>
        </div>
      </div>

      {/* Reset Button */}
      <button
        onClick={resetFilters}
        className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50 rounded-xl text-sm font-medium text-slate-300 transition-all cursor-pointer"
      >
        <RotateCcw className="w-4 h-4 text-slate-400" />
        Reset Filters
      </button>
    </div>
  );
};
