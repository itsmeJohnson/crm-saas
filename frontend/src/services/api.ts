import axios from 'axios';
import { useAuthStore } from '../store/authStore';

export const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token && config.headers && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (token) {
      prom.resolve(token);
    } else {
      prom.reject(error);
    }
  });
  failedQueue = [];
};

/** Max automatic retries for a throttled (429) request before giving up. */
const RATE_LIMIT_MAX_RETRIES = 2;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // 429: honour the server's Retry-After and retry a bounded number of times.
    if (error.response?.status === 429 && originalRequest) {
      originalRequest._rlRetries = (originalRequest._rlRetries || 0) + 1;
      if (originalRequest._rlRetries <= RATE_LIMIT_MAX_RETRIES) {
        const headerVal = Number(error.response.headers?.['retry-after']);
        const waitSeconds = Number.isFinite(headerVal) && headerVal > 0 ? headerVal : 2;
        const jitter = Math.random() * 500;
        await new Promise((r) => setTimeout(r, waitSeconds * 1000 + jitter));
        return api(originalRequest);
      }
      error.isRateLimited = true;
    }

    const isAuthEndpoint = originalRequest?.url?.includes('/auth/login') ||
                           originalRequest?.url?.includes('/auth/refresh') ||
                           originalRequest?.url?.includes('/auth/forgot-password') ||
                           originalRequest?.url?.includes('/auth/reset-password') ||
                           originalRequest?.url?.includes('/auth/mfa/');

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = useAuthStore.getState().refreshToken;
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }

        const res = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken });
        const { access_token, refresh_token } = res.data;

        useAuthStore.getState().setTokens(access_token, refresh_token);
        processQueue(null, access_token);
        isRefreshing = false;

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;
        useAuthStore.getState().logout();
        return Promise.reject(error);
      }
    }
    
    if (
      (error.response?.status === 400 && error.response?.data?.detail === "Inactive user") ||
      (error.response?.status === 403 && error.response?.data?.detail === "User account is deactivated")
    ) {
      useAuthStore.getState().logout();
    }
    
    return Promise.reject(error);
  }
);
