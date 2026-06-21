import { describe, it, expect, vi, beforeEach } from 'vitest';
import { usePipelineStore } from '../pipelineStore';
import { pipelineApi } from '../../services/pipelineApi';

vi.mock('../../services/pipelineApi', () => ({
  pipelineApi: {
    getPipelines: vi.fn(),
    createPipeline: vi.fn(),
    reorderPipelines: vi.fn(),
    updatePipeline: vi.fn(),
    deletePipeline: vi.fn(),
  },
}));

describe('pipelineStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    usePipelineStore.setState({
      stages: [],
      isLoading: false,
      error: null,
    });
  });

  it('initializes with correct defaults', () => {
    const state = usePipelineStore.getState();
    expect(state.stages).toEqual([]);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('fetches pipeline stages successfully and sorts them by position', async () => {
    const mockStages = [
      { id: '2', name: 'Stage 2', order_position: 2, is_system_default: false },
      { id: '1', name: 'Stage 1', order_position: 1, is_system_default: true },
    ] as any[];
    vi.mocked(pipelineApi.getPipelines).mockResolvedValueOnce(mockStages);

    await usePipelineStore.getState().fetchStages();

    expect(usePipelineStore.getState().isLoading).toBe(false);
    expect(usePipelineStore.getState().stages).toEqual([
      { id: '1', name: 'Stage 1', order_position: 1, is_system_default: true },
      { id: '2', name: 'Stage 2', order_position: 2, is_system_default: false },
    ]);
  });

  it('creates a new stage and refreshes stages list', async () => {
    const newStage = { id: '3', name: 'Stage 3', order_position: 3, is_system_default: false } as any;
    vi.mocked(pipelineApi.createPipeline).mockResolvedValueOnce(newStage);
    vi.mocked(pipelineApi.getPipelines).mockResolvedValueOnce([newStage]);

    const result = await usePipelineStore.getState().createStage({ name: 'Stage 3' });

    expect(pipelineApi.createPipeline).toHaveBeenCalledWith({ name: 'Stage 3' });
    expect(pipelineApi.getPipelines).toHaveBeenCalled();
    expect(result).toEqual(newStage);
  });

  it('reorders stages successfully and sorts the returned stages', async () => {
    const orders = [{ stage_id: '1', new_position: 2 }, { stage_id: '2', new_position: 1 }];
    const reorderedStages = [
      { id: '2', name: 'Stage 2', order_position: 1, is_system_default: false },
      { id: '1', name: 'Stage 1', order_position: 2, is_system_default: true },
    ] as any[];
    vi.mocked(pipelineApi.reorderPipelines).mockResolvedValueOnce(reorderedStages);

    await usePipelineStore.getState().reorderStages(orders);

    expect(pipelineApi.reorderPipelines).toHaveBeenCalledWith({ orders });
    expect(usePipelineStore.getState().stages).toEqual(reorderedStages);
  });

  it('deletes a stage successfully and refreshes the list', async () => {
    vi.mocked(pipelineApi.deletePipeline).mockResolvedValueOnce({ status: 'deleted', message: 'deleted' });
    vi.mocked(pipelineApi.getPipelines).mockResolvedValueOnce([]);

    await usePipelineStore.getState().deleteStage('stage-id', 'fallback-id');

    expect(pipelineApi.deletePipeline).toHaveBeenCalledWith('stage-id', 'fallback-id');
    expect(pipelineApi.getPipelines).toHaveBeenCalled();
  });
});
