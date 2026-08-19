import { create } from 'zustand';
import { metadataApi, CustomFieldDefinition, CrmConfig, CustomObjectDefinitionLite } from '../services/metadataApi';
import { Pipeline, PipelineStage } from '../services/pipelineApi';

interface MetadataState {
  metadataVersion: number | null;
  customFields: CustomFieldDefinition[];
  /** Per-entity definition map (Phase 4.1): { lead: [...], contact: [...] }. */
  customFieldsByEntity: Record<string, CustomFieldDefinition[]>;
  /** Custom object definitions (Phase 4.2), eager from bootstrap. */
  customObjects: CustomObjectDefinitionLite[];
  pipelines: Pipeline[];
  crmConfig: CrmConfig | null;
  selectedPipelineId: string | null;
  isLoading: boolean;
  loaded: boolean;
  error: string | null;

  /** Fetch the org's metadata bootstrap. No-op if already loaded unless force=true. */
  fetchBootstrap: (force?: boolean) => Promise<void>;
  /** Force a re-fetch (call after any custom-field or pipeline mutation). */
  refresh: () => Promise<void>;
  selectPipeline: (id: string | null) => void;

  // Selectors
  getSelectedPipeline: () => Pipeline | null;
  getStagesForSelected: () => PipelineStage[];
  getPipelineForStage: (stageId: string | null | undefined) => Pipeline | null;
}

/** Pick the pipeline to select by default: the org default, else the first. */
const defaultPipelineId = (pipelines: Pipeline[], current: string | null): string | null => {
  if (current && pipelines.some((p) => p.id === current)) return current;
  const def = pipelines.find((p) => p.is_default);
  return def?.id ?? pipelines[0]?.id ?? null;
};

const sortStages = (stages: PipelineStage[]) =>
  [...stages].sort((a, b) => a.order_position - b.order_position);

export const useMetadataStore = create<MetadataState>((set, get) => ({
  metadataVersion: null,
  customFields: [],
  customFieldsByEntity: {},
  customObjects: [],
  pipelines: [],
  crmConfig: null,
  selectedPipelineId: null,
  isLoading: false,
  loaded: false,
  error: null,

  fetchBootstrap: async (force = false) => {
    if (get().loaded && !force) return;
    set({ isLoading: true, error: null });
    try {
      const data = await metadataApi.bootstrap();
      const pipelines = data.pipelines.map((p) => ({ ...p, stages: sortStages(p.stages || []) }));
      set({
        metadataVersion: data.metadata_version,
        customFields: data.custom_fields,
        customFieldsByEntity: data.custom_fields_by_entity ?? { lead: data.custom_fields },
        customObjects: data.custom_objects ?? [],
        pipelines,
        selectedPipelineId: defaultPipelineId(pipelines, get().selectedPipelineId),
        crmConfig: data.crm_config ?? {
          industry: 'healthcare_dental',
          template: 'healthcare_dental',
          enabled_modules: ['dashboard', 'leads', 'patients', 'appointments', 'treatments', 'treatment_plans', 'recall', 'dentists', 'clinical_reports', 'billing', 'communications', 'reports']
        },
        isLoading: false,
        loaded: true,
      });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to load organization metadata',
        isLoading: false,
      });
    }
  },

  refresh: async () => {
    await get().fetchBootstrap(true);
  },

  selectPipeline: (id) => set({ selectedPipelineId: id }),

  getSelectedPipeline: () => {
    const { pipelines, selectedPipelineId } = get();
    return pipelines.find((p) => p.id === selectedPipelineId) ?? null;
  },

  getStagesForSelected: () => {
    const p = get().getSelectedPipeline();
    return p ? sortStages(p.stages) : [];
  },

  getPipelineForStage: (stageId) => {
    if (!stageId) return null;
    return get().pipelines.find((p) => p.stages.some((s) => s.id === stageId)) ?? null;
  },
}));
