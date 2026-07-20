import { api } from './api';

export interface DomainEvent {
  id: string;
  event_type: string;
  entity_type: string | null;
  entity_id: string | null;
  source: string;
  status: string;
  subscriber_count: number;
  delivered_count: number;
  failed_count: number;
  duration_ms: number | null;
  published_at: string | null;
}

export interface EventDelivery {
  id: string;
  event_id: string;
  subscription_id: string | null;
  subscriber: string;
  event_type: string;
  status: string;
  attempts: number;
  error: string | null;
  duration_ms: number | null;
  is_dead_letter: boolean;
  delivered_at: string | null;
}

export interface EventSubscription {
  id: string;
  name: string;
  event_pattern: string;
  subscriber_type: string;
  config: any | null;
  is_active: boolean;
  max_attempts: number;
  delivered_count: number;
  failed_count: number;
  created_at: string | null;
}

export interface EventCatalog {
  families: string[];
  event_types: Record<string, string[]>;
  all_event_types: string[];
  subscriber_types: string[];
}

export interface EventStats {
  total_events: number;
  deliveries: number;
  failed_deliveries: number;
  success_rate: number;
  dead_letter: number;
  avg_publish_ms: number;
  by_type: Record<string, number>;
}

export interface EventDashboard {
  total_events: number;
  success_rate: number;
  dead_letter: number;
  subscriptions: number;
  recent: DomainEvent[];
}

export const eventApi = {
  catalog: async () => (await api.get<EventCatalog>('/events/catalog')).data,
  dashboard: async () => (await api.get<EventDashboard>('/events/dashboard')).data,
  stats: async () => (await api.get<EventStats>('/events/stats')).data,

  publishCustom: async (payload: { name: string; payload?: any; entity_type?: string; entity_id?: string }) =>
    (await api.post<DomainEvent>('/events/publish', payload)).data,

  events: async (params: { event_type?: string; limit?: number } = {}) =>
    (await api.get<DomainEvent[]>('/events/events', { params })).data,
  deliveries: async (eventId: string) => (await api.get<EventDelivery[]>(`/events/events/${eventId}/deliveries`)).data,

  deadLetter: async (params: { limit?: number } = {}) =>
    (await api.get<EventDelivery[]>('/events/dead-letter', { params })).data,
  requeue: async (deliveryId: string) =>
    (await api.post<{ requeued: boolean; delivered: boolean }>(`/events/deliveries/${deliveryId}/requeue`, {})).data,

  listSubscriptions: async () => (await api.get<EventSubscription[]>('/events/subscriptions')).data,
  createSubscription: async (payload: any) => (await api.post<EventSubscription>('/events/subscriptions', payload)).data,
  updateSubscription: async (id: string, payload: any) => (await api.patch<EventSubscription>(`/events/subscriptions/${id}`, payload)).data,
  removeSubscription: async (id: string) => { await api.delete(`/events/subscriptions/${id}`); },
};
