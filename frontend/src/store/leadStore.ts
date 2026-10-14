import { create } from 'zustand';
import {
  leadApi,
  LeadResponse,
  SalesKPISummary,
  KanbanBoardResponse,
} from '../services/leadApi';

/** Serialize non-empty custom-field filters to a JSON string for the API, or undefined. */
const serializeCustomFilters = (cf: Record<string, string>): string | undefined => {
  const entries = Object.entries(cf).filter(([, v]) => v !== undefined && v !== null && v !== '');
  return entries.length > 0 ? JSON.stringify(Object.fromEntries(entries)) : undefined;
};

interface Filters {
  search: string;
  status: string;
  assigned_user_id: string;
  name: string;
  city: string;
  source: string;
  priority: string;
  min_value: string;
  max_value: string;
  include_archived: boolean;
  custom_fields: Record<string, string>;
}

interface Pagination {
  skip: number;
  limit: number;
}

interface LeadState {
  leads: LeadResponse[];
  totalCount: number;
  isLoading: boolean;
  error: string | null;
  filters: Filters;
  pagination: Pagination;
  kpiSummary: SalesKPISummary | null;
  isKpiLoading: boolean;
  kanbanBoard: KanbanBoardResponse | null;
  isKanbanLoading: boolean;
  loadingStageId: string | null;

  setFilters: (filters: Partial<Filters>) => void;
  setPagination: (pagination: Partial<Pagination>) => void;
  resetFilters: () => void;
  fetchLeads: (signal?: AbortSignal) => Promise<void>;
  fetchKPISummary: () => Promise<void>;
  fetchKanbanBoard: (pipelineId?: string) => Promise<void>;
  loadMoreStageCards: (stageId: string) => Promise<void>;
  moveKanbanCard: (leadId: string, toStageId: string) => Promise<void>;
  createLead: (payload: Parameters<typeof leadApi.createLead>[0]) => Promise<LeadResponse>;
  updateLead: (leadId: string, payload: Parameters<typeof leadApi.updateLead>[1]) => Promise<LeadResponse>;
  deleteLead: (leadId: string) => Promise<void>;
  archiveLead: (leadId: string) => Promise<void>;
  restoreLead: (leadId: string) => Promise<void>;
  bulkUpdate: (payload: Parameters<typeof leadApi.bulkUpdate>[0]) => Promise<void>;
  exportLeads: (format: 'csv' | 'xlsx') => Promise<void>;
  assignLeadsBulk: (payload: Parameters<typeof leadApi.assignLeadsBulk>[0]) => Promise<void>;
  transferLeads: (payload: Parameters<typeof leadApi.transferLeads>[0]) => Promise<void>;
}

export const useLeadStore = create<LeadState>((set, get) => ({
  leads: [],
  totalCount: 0,
  isLoading: false,
  error: null,
  filters: {
    search: '',
    status: 'All',
    assigned_user_id: 'All',
    name: '',
    city: '',
    source: '',
    priority: 'All',
    min_value: '',
    max_value: '',
    include_archived: false,
    custom_fields: {},
  },
  pagination: {
    skip: 0,
    limit: 25,
  },
  kpiSummary: null,
  isKpiLoading: false,
  kanbanBoard: null,
  isKanbanLoading: false,
  loadingStageId: null,

  setFilters: (newFilters) => {
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
      pagination: { ...state.pagination, skip: 0 },
    }));
    get().fetchLeads();
  },

  setPagination: (newPagination) => {
    set((state) => ({
      pagination: { ...state.pagination, ...newPagination },
    }));
    get().fetchLeads();
  },

  resetFilters: () => {
    set({
      filters: {
        search: '', status: 'All', assigned_user_id: 'All', name: '', city: '',
        source: '', priority: 'All', min_value: '', max_value: '', include_archived: false,
        custom_fields: {},
      },
      pagination: { skip: 0, limit: 25 },
    });
    get().fetchLeads();
  },

  fetchLeads: async (signal?: AbortSignal) => {
    set({ isLoading: true, error: null });
    try {
      const { skip, limit } = get().pagination;
      const f = get().filters;
      const params = {
        skip,
        limit,
        search: f.search.trim() || undefined,
        status: f.status === 'All' ? undefined : f.status,
        assigned_user_id: f.assigned_user_id === 'All' ? undefined : f.assigned_user_id,
        name: f.name.trim() || undefined,
        city: f.city.trim() || undefined,
        source: f.source.trim() || undefined,
        priority: f.priority === 'All' ? undefined : f.priority,
        min_value: f.min_value !== '' ? Number(f.min_value) : undefined,
        max_value: f.max_value !== '' ? Number(f.max_value) : undefined,
        include_archived: f.include_archived || undefined,
        custom_fields: serializeCustomFilters(f.custom_fields),
      };
      const result = await leadApi.getLeadsPaginated(params, signal);
      set({ leads: result.leads, totalCount: result.totalCount, isLoading: false });
    } catch (err: any) {
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') {
        return; // Request was aborted due to new keystroke/debounce, do not set error state
      }
      set({
        error: err.response?.data?.detail || 'Failed to fetch leads',
        isLoading: false,
      });
    }
  },

  fetchKPISummary: async () => {
    set({ isKpiLoading: true });
    try {
      const summary = await leadApi.getSalesKPISummary();
      set({ kpiSummary: summary, isKpiLoading: false });
    } catch (err) {
      set({ isKpiLoading: false });
    }
  },

  fetchKanbanBoard: async (pipelineId?: string) => {
    set({ isKanbanLoading: true });
    try {
      const board = await leadApi.getKanbanBoard(pipelineId, 10);
      set({ kanbanBoard: board, isKanbanLoading: false });
    } catch (err) {
      set({ isKanbanLoading: false });
    }
  },

  loadMoreStageCards: async (stageId: string) => {
    const currentBoard = get().kanbanBoard;
    if (!currentBoard) return;
    const stage = currentBoard.stages.find((s) => s.stage_id === stageId);
    if (!stage || !stage.has_more) return;

    set({ loadingStageId: stageId });
    try {
      const skip = stage.cards.length;
      const res = await leadApi.getKanbanStageCards(stageId, skip, 10);
      set((state) => {
        if (!state.kanbanBoard) return state;
        const updatedStages = state.kanbanBoard.stages.map((s) => {
          if (s.stage_id === stageId) {
            return {
              ...s,
              cards: [...s.cards, ...res.cards],
              has_more: res.has_more,
            };
          }
          return s;
        });
        return {
          kanbanBoard: {
            ...state.kanbanBoard,
            stages: updatedStages,
          },
          loadingStageId: null,
        };
      });
    } catch (err) {
      set({ loadingStageId: null });
    }
  },

  moveKanbanCard: async (leadId: string, toStageId: string) => {
    const currentBoard = get().kanbanBoard;
    if (!currentBoard) return;

    // Find the lead card
    let targetCard: LeadResponse | null = null;
    for (const st of currentBoard.stages) {
      const found = st.cards.find((c) => c.id === leadId);
      if (found) {
        targetCard = found;
        break;
      }
    }
    if (!targetCard) return;

    // Optimistic local update
    const previousBoard = currentBoard;
    const updatedStages = currentBoard.stages.map((st) => {
      if (st.cards.some((c) => c.id === leadId)) {
        return {
          ...st,
          cards: st.cards.filter((c) => c.id !== leadId),
          total_count: Math.max(0, st.total_count - 1),
          total_value: Math.max(0, st.total_value - (Number(targetCard?.value) || 0)),
        };
      }
      if (st.stage_id === toStageId) {
        return {
          ...st,
          cards: [{ ...targetCard!, stage_id: toStageId }, ...st.cards],
          total_count: st.total_count + 1,
          total_value: st.total_value + (Number(targetCard?.value) || 0),
        };
      }
      return st;
    });

    set({ kanbanBoard: { ...currentBoard, stages: updatedStages } });

    try {
      await leadApi.updateLead(leadId, { stage_id: toStageId });
      // Refresh real aggregates in background
      get().fetchKPISummary();
    } catch (err) {
      // Rollback on error
      set({ kanbanBoard: previousBoard });
      throw err;
    }
  },


  createLead: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await leadApi.createLead(payload);
      set({ isLoading: false });
      await Promise.all([get().fetchLeads(), get().fetchKPISummary(), get().fetchKanbanBoard()]);
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to create lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  updateLead: async (leadId, payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await leadApi.updateLead(leadId, payload);
      set({ isLoading: false });
      await Promise.all([get().fetchLeads(), get().fetchKPISummary(), get().fetchKanbanBoard()]);
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to update lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  deleteLead: async (leadId) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.deleteLead(leadId);
      set({ isLoading: false });
      await Promise.all([get().fetchLeads(), get().fetchKPISummary(), get().fetchKanbanBoard()]);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to delete lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  archiveLead: async (leadId) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.archiveLead(leadId);
      set({ isLoading: false });
      await Promise.all([get().fetchLeads(), get().fetchKPISummary(), get().fetchKanbanBoard()]);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to archive lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  restoreLead: async (leadId) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.restoreLead(leadId);
      set({ isLoading: false });
      await Promise.all([get().fetchLeads(), get().fetchKPISummary(), get().fetchKanbanBoard()]);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to restore lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  bulkUpdate: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.bulkUpdate(payload);
      set({ isLoading: false });
      await Promise.all([get().fetchLeads(), get().fetchKPISummary(), get().fetchKanbanBoard()]);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed bulk update';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  exportLeads: async (format) => {
    const f = get().filters;
    const params = {
      format,
      search: f.search.trim() || undefined,
      status: f.status === 'All' ? undefined : f.status,
      assigned_user_id: f.assigned_user_id === 'All' ? undefined : f.assigned_user_id,
      name: f.name.trim() || undefined,
      city: f.city.trim() || undefined,
      source: f.source.trim() || undefined,
      priority: f.priority === 'All' ? undefined : f.priority,
      min_value: f.min_value !== '' ? Number(f.min_value) : undefined,
      max_value: f.max_value !== '' ? Number(f.max_value) : undefined,
      include_archived: f.include_archived || undefined,
    };
    const blob = await leadApi.exportLeads(params);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `leads_export.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  assignLeadsBulk: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.assignLeadsBulk(payload);
      set({ isLoading: false });
      await get().fetchLeads();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed bulk assignment';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  transferLeads: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.transferLeads(payload);
      set({ isLoading: false });
      await get().fetchLeads();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed lead transfer';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },
}));
