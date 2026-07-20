import { api } from './api';

export interface Capability { intent: string; label: string; examples: string[]; }
export interface CopilotCapabilities {
  capabilities: Capability[]; action_types: string[]; voice_ready: boolean; powered_by: string;
}

export interface PendingAction { type: string; [k: string]: any; }

export interface CopilotReply {
  reply: string;
  speech: string;
  intent: string;
  data: any;
  pending_action: PendingAction | null;
  requires_confirmation: boolean;
  conversation_id: string | null;
}

export interface CopilotConversation {
  id: string; title: string; message_count: number; last_message_at: string | null; created_at: string | null;
}
export interface CopilotMessage {
  id: string; role: string; content: string; created_at: string | null;
}

export const copilotApi = {
  capabilities: async () => (await api.get<CopilotCapabilities>('/copilot/capabilities')).data,
  ask: async (message: string, conversationId?: string | null) =>
    (await api.post<CopilotReply>('/copilot/ask', { message, conversation_id: conversationId || undefined })).data,
  execute: async (action: PendingAction) =>
    (await api.post<{ status: string; action_type: string; result: any; reply: string; speech: string }>(
      '/copilot/execute', { action })).data,
  conversations: async () => (await api.get<CopilotConversation[]>('/copilot/conversations')).data,
  messages: async (id: string) => (await api.get<CopilotMessage[]>(`/copilot/conversations/${id}/messages`)).data,
};
