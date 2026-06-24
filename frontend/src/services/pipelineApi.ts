import { api } from './api';

export interface PipelineStage {
  id: string;
  organization_id: string;
  name: string;
  order_position: number;
  is_system_default: boolean;
  created_at: string;
  updated_at: string;
}

export const pipelineApi = {
  getPipelines: async () => {
    const response = await api.get<PipelineStage[]>('/pipelines/');
    return response.data;
  },

  createPipeline: async (payload: {
    name: string;
    order_position?: number | null;
    is_system_default?: boolean;
  }) => {
    const response = await api.post<PipelineStage>('/pipelines/', payload);
    return response.data;
  },

  reorderPipelines: async (payload: {
    orders: { stage_id: string; new_position: number }[];
  }) => {
    const response = await api.post<PipelineStage[]>('/pipelines/reorder', payload);
    return response.data;
  },

  updatePipeline: async (stageId: string, payload: {
    name?: string;
    order_position?: number | null;
    is_system_default?: boolean;
  }) => {
    const response = await api.patch<PipelineStage>(`/pipelines/${stageId}`, payload);
    return response.data;
  },

  deletePipeline: async (stageId: string, fallbackStageId?: string) => {
    const params = fallbackStageId ? { fallback_stage_id: fallbackStageId } : {};
    const response = await api.delete<{ status: string; message: string }>(`/pipelines/${stageId}`, { params });
    return response.data;
  },
};
