import { create } from 'zustand';
import { pipelineApi, PipelineStage } from '../services/pipelineApi';

interface PipelineState {
  stages: PipelineStage[];
  isLoading: boolean;
  error: string | null;
  fetchStages: () => Promise<void>;
  createStage: (payload: { name: string; order_position?: number | null; is_system_default?: boolean }) => Promise<PipelineStage>;
  reorderStages: (orders: { stage_id: string; new_position: number }[]) => Promise<void>;
  updateStage: (stageId: string, payload: { name?: string; order_position?: number | null; is_system_default?: boolean }) => Promise<PipelineStage>;
  deleteStage: (stageId: string, fallbackStageId?: string) => Promise<void>;
}

export const usePipelineStore = create<PipelineState>((set, get) => ({
  stages: [],
  isLoading: false,
  error: null,

  fetchStages: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await pipelineApi.getPipelines();
      // Sort by order_position ascending to be safe
      const sorted = data.sort((a, b) => a.order_position - b.order_position);
      set({ stages: sorted, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch pipeline stages',
        isLoading: false,
      });
    }
  },

  createStage: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await pipelineApi.createPipeline(payload);
      set({ isLoading: false });
      await get().fetchStages();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to create stage';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  reorderStages: async (orders) => {
    set({ isLoading: true, error: null });
    try {
      const data = await pipelineApi.reorderPipelines({ orders });
      const sorted = data.sort((a, b) => a.order_position - b.order_position);
      set({ stages: sorted, isLoading: false });
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to reorder stages';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  updateStage: async (stageId, payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await pipelineApi.updatePipeline(stageId, payload);
      set({ isLoading: false });
      await get().fetchStages();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to update stage';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  deleteStage: async (stageId, fallbackStageId) => {
    set({ isLoading: true, error: null });
    try {
      await pipelineApi.deletePipeline(stageId, fallbackStageId);
      set({ isLoading: false });
      await get().fetchStages();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to delete stage';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },
}));
