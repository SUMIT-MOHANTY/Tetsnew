/**
 * API Client
 *
 * Axios instance with interceptors, auth header injection, and error handling
 */

import axios, {
  AxiosInstance,
  AxiosError,
  AxiosRequestConfig,
  AxiosResponse,
} from 'axios';
import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query';
import { useAuthStore } from '../stores/authStore';

// =============================================================================
// Configuration
// =============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
const REQUEST_TIMEOUT = 30000;
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;

// =============================================================================
// Axios Instance
// =============================================================================

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// =============================================================================
// Request Interceptor
// =============================================================================

apiClient.interceptors.request.use(
  (config) => {
    // Attach JWT token from auth store
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Add request timestamp for debugging
    config.headers['X-Request-Time'] = new Date().toISOString();

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// =============================================================================
// Response Interceptor
// =============================================================================

apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Return data directly for convenience
    return response.data;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & {
      _retry?: boolean;
      _retryCount?: number;
    };

    if (!originalRequest) {
      return Promise.reject(error);
    }

    // Initialize retry count
    originalRequest._retryCount = originalRequest._retryCount || 0;

    // Handle 401 Unauthorized - Token expired
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Attempt to refresh token
        const refreshToken = useAuthStore.getState().refreshToken;
        if (refreshToken) {
          const response = await axios.post<{ access_token: string }>(
            `${API_BASE_URL}/refresh`,
            { refresh_token: refreshToken }
          );

          if (response.data && response.data.access_token) {
            const { access_token } = response.data;
            useAuthStore.getState().setToken(access_token);

            // Retry original request with new token
            originalRequest.headers = originalRequest.headers || {};
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
            return apiClient(originalRequest);
          }
        }
      } catch (refreshError) {
        // Refresh failed, logout user
        useAuthStore.getState().logout();
        // Emit an event for the app to handle navigation (avoids sandbox escape)
        window.dispatchEvent(new CustomEvent('auth:session_expired'));
        return Promise.reject(refreshError);
      }
    }

    // Handle 403 Forbidden - RBAC violation
    if (error.response?.status === 403) {
      console.error('Access denied:', error.response.data?.error?.message);
      // Could emit an event to show a toast notification
    }

    // Handle 5xx Server Errors - Retry with exponential backoff
    if (error.response?.status && error.response.status >= 500) {
      if (originalRequest._retryCount < MAX_RETRIES) {
        originalRequest._retryCount++;
        const delay = RETRY_DELAY * Math.pow(2, originalRequest._retryCount - 1);

        await new Promise((resolve) => setTimeout(resolve, delay));
        return apiClient(originalRequest);
      }
    }

    // Handle network errors - Retry
    if (!error.response && originalRequest._retryCount < MAX_RETRIES) {
      originalRequest._retryCount++;
      const delay = RETRY_DELAY * originalRequest._retryCount;

      await new Promise((resolve) => setTimeout(resolve, delay));
      return apiClient(originalRequest);
    }

    return Promise.reject(error);
  }
);

// =============================================================================
// Typed API Methods
// =============================================================================

export async function get<T>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.get<T>(url, config);
  return response as T;
}

export async function post<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.post<T>(url, data, config);
  return response as T;
}

export async function put<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.put<T>(url, data, config);
  return response as T;
}

export async function patch<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.patch<T>(url, data, config);
  return response as T;
}

export async function del<T>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.delete<T>(url, config);
  return response as T;
}

// =============================================================================
// TanStack Query Client
// =============================================================================

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      console.error('Query error:', error);
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      console.error('Mutation error:', error);
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
      retry: 2,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 1,
      retryDelay: 1000,
    },
  },
});

// =============================================================================
// Query Keys
// =============================================================================

export const queryKeys = {
  // Auth
  auth: {
    me: ['auth', 'me'] as const,
    users: ['auth', 'users'] as const,
    user: (id: string) => ['auth', 'users', id] as const,
  },

  // Initiatives
  initiatives: {
    all: ['initiatives'] as const,
    list: (filters?: Record<string, unknown>) =>
      ['initiatives', 'list', filters] as const,
    detail: (id: string) => ['initiatives', id] as const,
    health: (id: string) => ['initiatives', id, 'health'] as const,
  },

  // Milestones
  milestones: {
    all: ['milestones'] as const,
    byInitiative: (initiativeId: string) =>
      ['milestones', 'initiative', initiativeId] as const,
    detail: (id: string) => ['milestones', id] as const,
  },

  // Risks
  risks: {
    all: ['risks'] as const,
    byInitiative: (initiativeId: string) =>
      ['risks', 'initiative', initiativeId] as const,
    dashboard: ['risks', 'dashboard'] as const,
  },

  // Decisions
  decisions: {
    all: ['decisions'] as const,
    byInitiative: (initiativeId: string) =>
      ['decisions', 'initiative', initiativeId] as const,
    pending: ['decisions', 'pending'] as const,
  },

  // Dependencies
  dependencies: {
    all: ['dependencies'] as const,
    byInitiative: (initiativeId: string) =>
      ['dependencies', 'initiative', initiativeId] as const,
  },

  // Insights
  insights: {
    all: ['insights'] as const,
    list: (filters?: Record<string, unknown>) =>
      ['insights', 'list', filters] as const,
    detail: (id: string) => ['insights', id] as const,
    recommendations: ['insights', 'recommendations'] as const,
  },

  // Approvals
  approvals: {
    all: ['approvals'] as const,
    pending: ['approvals', 'pending'] as const,
    detail: (id: string) => ['approvals', id] as const,
    audit: (id: string) => ['approvals', id, 'audit'] as const,
  },

  // Adoption
  adoption: {
    signals: (initiativeId?: string) =>
      ['adoption', 'signals', initiativeId] as const,
    trends: (initiativeId: string) =>
      ['adoption', 'trends', initiativeId] as const,
    predictability: (initiativeId: string) =>
      ['adoption', 'predictability', initiativeId] as const,
    anomalies: ['adoption', 'anomalies'] as const,
    anomaly: (id: string) => ['adoption', 'anomalies', id] as const,
  },

  // Dashboard
  dashboard: {
    stats: ['dashboard', 'stats'] as const,
    health: ['dashboard', 'health'] as const,
  },
} as const;

// =============================================================================
// Error Handling Helpers
// =============================================================================

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError;
    return (
      (axiosError.response?.data as { error?: { message?: string } })?.error?.message ||
      axiosError.message ||
      'An unexpected error occurred'
    );
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
}

export function getErrorCode(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError;
    return (axiosError.response?.data as { error?: { code?: string } })?.error?.code || 'UNKNOWN_ERROR';
  }
  return 'UNKNOWN_ERROR';
}

export function isNetworkError(error: unknown): boolean {
  return axios.isAxiosError(error) && !error.response;
}

export function isAuthError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 401;
}

export function isForbiddenError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 403;
}
