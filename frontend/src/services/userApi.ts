import { api } from './api';

export interface UserResponse {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  is_invited: boolean;
  organization_id: string;
  reporting_to_id?: string | null;
  created_at: string;
  updated_at: string;
  is_team_leader?: boolean;
}

export interface InvitationResponse {
  id: string;
  email: string;
  role: string;
  organization_id: string;
  token: string;
  expires_at: string;
  accepted: boolean;
  revoked: boolean;
  created_by: string;
  created_at: string;
}

export const userApi = {
  getUsers: async (params: { skip?: number; limit?: number; search?: string; role?: string; is_active?: boolean }) => {
    const response = await api.get<UserResponse[]>('/users/', { params });
    return response.data;
  },

  createUser: async (payload: {
    email: string;
    first_name?: string;
    last_name?: string;
    role: string;
    password?: string;
    organization_id: string;
    reporting_to_id?: string | null;
  }) => {
    const response = await api.post<UserResponse>('/users/', payload);
    return response.data;
  },

  updateUser: async (userId: string, payload: {
    email?: string;
    first_name?: string | null;
    last_name?: string | null;
    role?: string;
    is_active?: boolean;
    password?: string;
    reporting_to_id?: string | null;
  }) => {
    const response = await api.patch<UserResponse>(`/users/${userId}`, payload);
    return response.data;
  },

  deleteUser: async (userId: string) => {
    const response = await api.delete<UserResponse>(`/users/${userId}`);
    return response.data;
  },

  toggleUserStatus: async (userId: string, isActive: boolean) => {
    const response = await api.patch<UserResponse>(`/users/${userId}/status`, null, {
      params: { is_active: isActive }
    });
    return response.data;
  },

  inviteUser: async (payload: { email: string; role: string }) => {
    const response = await api.post<InvitationResponse>('/users/invitations', payload);
    return response.data;
  },

  getInvitations: async () => {
    const response = await api.get<InvitationResponse[]>('/users/invitations');
    return response.data;
  },

  acceptInvitation: async (payload: {
    token: string;
    password?: string;
    first_name: string;
    last_name: string;
  }) => {
    const response = await api.post<UserResponse>('/users/invitations/accept', payload);
    return response.data;
  }
};
