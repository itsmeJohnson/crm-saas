import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useUserStore } from '../../store/userStore';

export const Pagination: React.FC = () => {
  const { pagination, setPagination, users } = useUserStore();
  const { skip, limit } = pagination;

  const currentPage = Math.floor(skip / limit) + 1;
  const hasMore = users.length === limit;

  const handlePrev = () => {
    if (skip > 0) {
      setPagination({ skip: Math.max(0, skip - limit) });
    }
  };

  const handleNext = () => {
    if (hasMore) {
      setPagination({ skip: skip + limit });
    }
  };

  return (
    <div className="flex items-center justify-between mt-6 px-2">
      <div className="text-sm text-slate-400">
        Showing Page <span className="font-semibold text-slate-200">{currentPage}</span>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={handlePrev}
          disabled={skip === 0}
          className={`flex items-center gap-1.5 px-3.5 py-2 border rounded-xl text-sm font-medium transition-all cursor-pointer ${
            skip === 0
              ? 'border-slate-800 bg-slate-900/30 text-slate-600 cursor-not-allowed'
              : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50'
          }`}
        >
          <ChevronLeft className="w-4 h-4" />
          Previous
        </button>
        <button
          onClick={handleNext}
          disabled={!hasMore}
          className={`flex items-center gap-1.5 px-3.5 py-2 border rounded-xl text-sm font-medium transition-all cursor-pointer ${
            !hasMore
              ? 'border-slate-800 bg-slate-900/30 text-slate-600 cursor-not-allowed'
              : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50'
          }`}
        >
          Next
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
