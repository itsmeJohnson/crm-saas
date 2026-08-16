import { api } from './api';

export interface PipelineStage {
  id: string;
  organization_id: string;
  pipeline_id?: string;
  name: string;
  order_position: number;
  is_system_default: boolean;
  color?: string;
  probability?: number;
  is_won?: boolean;
  is_lost?: boolean;
  is_active?: boolean;
  created_at: string;
  updated_at: string;
}

export interface Pipeline {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  stages: PipelineStage[];
}

export interface StageInput {
  pipeline_id?: string;
  name?: string;
  order_position?: number | null;
  is_system_default?: boolean;
  color?: string;
  probability?: number;
  is_won?: boolean;
  is_lost?: boolean;
  is_active?: boolean;
}

export const pipelineApi = {
  // ── Legacy flat-stage endpoints (kept for dialer / call-disposition consumers) ──
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

  // ── Multi-pipeline entity endpoints ──
  listAll: async () => {
    const response = await api.get<Pipeline[]>('/pipelines/all');
    return response.data;
  },

  createPipelineEntity: async (payload: {
    name: string;
    description?: string | null;
    is_default?: boolean;
    is_active?: boolean;
  }) => {
    const response = await api.post<Pipeline>('/pipelines/all', payload);
    return response.data;
  },

  updatePipelineEntity: async (pipelineId: string, payload: {
    name?: string;
    description?: string | null;
    is_default?: boolean;
    is_active?: boolean;
  }) => {
    const response = await api.patch<Pipeline>(`/pipelines/all/${pipelineId}`, payload);
    return response.data;
  },

  deletePipelineEntity: async (pipelineId: string, reassignmentPipelineId?: string) => {
    const params = reassignmentPipelineId ? { reassignment_pipeline_id: reassignmentPipelineId } : {};
    const response = await api.delete<{ status: string; message: string }>(`/pipelines/all/${pipelineId}`, { params });
    return response.data;
  },

  // ── REST-consistent stage ops (scoped to a pipeline via pipeline_id) ──
  createStage: async (payload: StageInput) => {
    const response = await api.post<PipelineStage>('/pipelines/stages', payload);
    return response.data;
  },

  updateStage: async (stageId: string, payload: StageInput) => {
    const response = await api.patch<PipelineStage>(`/pipelines/stages/${stageId}`, payload);
    return response.data;
  },

  deleteStage: async (stageId: string, fallbackStageId?: string) => {
    const params = fallbackStageId ? { fallback_stage_id: fallbackStageId } : {};
    const response = await api.delete<{ status: string; message: string }>(`/pipelines/stages/${stageId}`, { params });
    return response.data;
  },

  reorderStages: async (orders: { stage_id: string; new_position: number }[]) => {
    const response = await api.post<PipelineStage[]>('/pipelines/stages/reorder', { orders });
    return response.data;
  },
};
