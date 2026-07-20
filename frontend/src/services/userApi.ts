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
  seat_number?: string | null;
  inactive_reason?: string | null;
  phone?: string | null;
}

export interface ReplaceEmployeeRequest {
  old_user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  reporting_to_id?: string | null;
  password?: string;
  role: string;
  phone?: string;
}

export interface SeatUtilizationResponse {
  licensed_seats: number;
  active_users: number;
  inactive_assigned_seats: number;
  available_new_seats: number;
  replace_employee_available: number;
}

export interface SeatHistoryResponse {
  id: string;
  seat_number: string;
  user_id: string | null;
  user_name: string | null;
  action: string;
  created_at: string;
  performed_by_name: string | null;
  remarks: string | null;
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

  toggleUserStatus: async (userId: string, isActive: boolean, inactiveReason?: string | null) => {
    const params: any = { is_active: isActive };
    if (inactiveReason) {
      params.inactive_reason = inactiveReason;
    }
    const response = await api.patch<UserResponse>(`/users/${userId}/status`, null, { params });
    return response.data;
  },

  getSeatUtilization: async () => {
    const response = await api.get<SeatUtilizationResponse>('/users/seat-utilization');
    return response.data;
  },

  getSeatHistory: async () => {
    const response = await api.get<SeatHistoryResponse[]>('/users/seat-history');
    return response.data;
  },

  getInactiveEmployees: async () => {
    const response = await api.get<UserResponse[]>('/users/inactive-employees');
    return response.data;
  },

  replaceEmployee: async (payload: ReplaceEmployeeRequest) => {
    const response = await api.post<UserResponse>('/users/replace-employee', payload);
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
