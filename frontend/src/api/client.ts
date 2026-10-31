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
import { mockDataStore } from '../mocks/dataStore';

// =============================================================================
// Configuration
// =============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
const REQUEST_TIMEOUT = 30000;
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;

// =============================================================================
// API Error Types
// =============================================================================

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
  meta?: {
    page?: number;
    page_size?: number;
    total?: number;
    total_pages?: number;
  };
}

// =============================================================================
// Mock API Handler
// =============================================================================

class MockAPIHandler {
  private delay = 300;

  private async simulateDelay(): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, this.delay));
  }

  private createResponse<T>(data: T): ApiResponse<T> {
    return {
      success: true,
      data,
    };
  }

  private createErrorResponse(error: ApiError): ApiResponse<never> {
    return {
      success: false,
      error,
    };
  }

  async handleRequest<T>(
    method: string,
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    await this.simulateDelay();

    const path = url.replace(/^\//, '');
    const segments = path.split('/');

    // Auth endpoints
    if (path === 'login') {
      const { email, password } = data as { email: string; password: string };
      const user = mockDataStore.getUserByEmail(email);
      if (user && password === 'password') {
        return this.createResponse({
          access_token: `mock-token-${user.id}`,
          refresh_token: `mock-refresh-${user.id}`,
          token_type: 'bearer',
          expires_in: 3600,
        }) as T;
      }
      throw new Error('Invalid credentials');
    }

    if (path === 'refresh') {
      return this.createResponse({
        access_token: 'mock-refreshed-token',
        token_type: 'bearer',
        expires_in: 3600,
      }) as T;
    }

    if (path === 'logout') {
      return this.createResponse(undefined) as T;
    }

    if (path === 'me') {
      const authHeader = config?.headers?.Authorization as string;
      if (authHeader) {
        const userId = authHeader.replace('Bearer mock-token-', '').replace('Bearer mock-refreshed-', '');
        const user = mockDataStore.getUserById(userId);
        if (user) return this.createResponse(user) as T;
      }
      const defaultUser = mockDataStore.mockUsers[0];
      return this.createResponse(defaultUser) as T;
    }

    // Users endpoints
    if (path === 'users') {
      return this.createResponse(mockDataStore.mockUsers) as T;
    }

    // Dashboard endpoints
    if (path === 'dashboard') {
      return this.createResponse(mockDataStore.mockDashboardStats) as T;
    }

    if (path === 'stats') {
      return this.createResponse(mockDataStore.mockDashboardStats) as T;
    }

    // Initiatives endpoints
    if (path === 'initiatives') {
      if (method === 'GET') {
        const params = config?.params || {};
        let initiatives = [...mockDataStore.mockInitiatives];
        
        if (params.status) {
          initiatives = initiatives.filter(i => params.status.includes(i.status));
        }
        if (params.priority) {
          initiatives = initiatives.filter(i => params.priority.includes(i.priority));
        }
        if (params.owner_id) {
          initiatives = initiatives.filter(i => i.owner_id === params.owner_id);
        }
        if (params.search) {
          const query = params.search.toLowerCase();
          initiatives = initiatives.filter(i => 
            i.name.toLowerCase().includes(query) || 
            i.code.toLowerCase().includes(query)
          );
        }

        const page = params.page || 1;
        const page_size = params.page_size || 10;
        const total = initiatives.length;
        const total_pages = Math.ceil(total / page_size);
        const start = (page - 1) * page_size;
        const paginatedItems = initiatives.slice(start, start + page_size);

        return this.createResponse({
          items: paginatedItems,
          total,
          page,
          page_size,
          total_pages,
        }) as T;
      }
      
      if (method === 'POST' && data) {
        const newInitiative = {
          ...data,
          id: `init-${Date.now()}`,
          status: 'ACTIVE',
          progress_percentage: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return this.createResponse(newInitiative) as T;
      }
    }

    // Single initiative endpoints
    const initiativeMatch = path.match(/^initiatives\/(.+)$/);
    if (initiativeMatch) {
      const initiativeId = initiativeMatch[1];
      
      if (initiativeId === 'health') {
        return this.createResponse(mockDataStore.mockPortfolioHealth) as T;
      }

      const initiative = mockDataStore.getInitiativeById(initiativeId);
      
      if (method === 'GET') {
        if (initiative) return this.createResponse(initiative) as T;
        throw new Error('Initiative not found');
      }
      
      if (method === 'PUT' && data) {
        if (initiative) {
          const updated = { ...initiative, ...data, updated_at: new Date().toISOString() };
          return this.createResponse(updated) as T;
        }
        throw new Error('Initiative not found');
      }
      
      if (method === 'DELETE') {
        return this.createResponse(undefined) as T;
      }
    }

    // Initiative block/unblock
    const blockMatch = path.match(/^initiatives\/(.+)\/block$/);
    if (blockMatch) {
      const initiativeId = blockMatch[1];
      const initiative = mockDataStore.getInitiativeById(initiativeId);
      if (initiative) {
        const updated = { 
          ...initiative, 
          status: method === 'POST' ? 'BLOCKED' : 'ACTIVE',
          updated_at: new Date().toISOString() 
        };
        return this.createResponse(updated) as T;
      }
      throw new Error('Initiative not found');
    }

    // Milestones endpoints
    if (path === 'milestones') {
      if (method === 'POST' && data) {
        const newMilestone = {
          ...data,
          id: `milestone-${Date.now()}`,
          status: 'NOT_STARTED',
          completion_percentage: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return this.createResponse(newMilestone) as T;
      }
    }

    const milestonesMatch = path.match(/^milestones\/by-initiative\/(.+)$/);
    if (milestonesMatch) {
      const initiativeId = milestonesMatch[1];
      const milestones = mockDataStore.getMilestonesByInitiative(initiativeId);
      return this.createResponse(milestones) as T;
    }

    const milestoneMatch = path.match(/^milestones\/(.+)$/);
    if (milestoneMatch) {
      const milestoneId = milestoneMatch[1];
      const milestone = mockDataStore.mockMilestones.find(m => m.id === milestoneId);
      
      if (method === 'PUT' && data) {
        if (milestone) {
          const updated = { ...milestone, ...data, updated_at: new Date().toISOString() };
          return this.createResponse(updated) as T;
        }
      }
      
      if (method === 'PATCH' && data) {
        if (milestone) {
          const updated = { 
            ...milestone, 
            status: 'COMPLETED',
            completion_percentage: 100,
            actual_date: new Date().toISOString().split('T')[0],
            updated_at: new Date().toISOString() 
          };
          return this.createResponse(updated) as T;
        }
      }
    }

    // Risks endpoints
    const risksByInitiativeMatch = path.match(/^risks\/by-initiative\/(.+)$/);
    if (risksByInitiativeMatch) {
      const initiativeId = risksByInitiativeMatch[1];
      const risks = mockDataStore.getRisksByInitiative(initiativeId);
      return this.createResponse(risks) as T;
    }

    if (path === 'risks') {
      if (method === 'POST' && data) {
        const newRisk = {
          ...data,
          id: `risk-${Date.now()}`,
          status: 'OPEN',
          identified_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return this.createResponse(newRisk) as T;
      }
    }

    const riskMatch = path.match(/^risks\/(.+)$/);
    if (riskMatch) {
      const riskId = riskMatch[1];
      const risk = mockDataStore.mockRisks.find(r => r.id === riskId);
      
      if (method === 'PUT' && data) {
        if (risk) {
          const updated = { ...risk, ...data, updated_at: new Date().toISOString() };
          return this.createResponse(updated) as T;
        }
      }
    }

    if (path === 'risks/dashboard/summary') {
      return this.createResponse(mockDataStore.mockRisks.length > 0 ? {
        total_risks: mockDataStore.mockRisks.length,
        open_risks: mockDataStore.mockRisks.filter(r => r.status === 'OPEN').length,
        critical_risks: mockDataStore.mockRisks.filter(r => r.severity === 'CRITICAL').length,
        high_risks: mockDataStore.mockRisks.filter(r => r.severity === 'HIGH').length,
        recently_identified: 0,
        recently_resolved: 0,
      } : mockDataStore.mockRisks[0] || {}) as T;
    }

    // Decisions endpoints
    const decisionsByInitiativeMatch = path.match(/^decisions\/by-initiative\/(.+)$/);
    if (decisionsByInitiativeMatch) {
      const initiativeId = decisionsByInitiativeMatch[1];
      const decisions = mockDataStore.getDecisionsByInitiative(initiativeId);
      return this.createResponse(decisions) as T;
    }

    if (path === 'decisions') {
      if (method === 'POST' && data) {
        const newDecision = {
          ...data,
          id: `decision-${Date.now()}`,
          status: 'PENDING',
          requested_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return this.createResponse(newDecision) as T;
      }
    }

    const decisionMatch = path.match(/^decisions\/(.+)$/);
    if (decisionMatch) {
      const decisionId = decisionMatch[1];
      const decision = mockDataStore.mockDecisions.find(d => d.id === decisionId);
      
      if (method === 'PUT' && data) {
        if (decision) {
          const updated = { ...decision, ...data, updated_at: new Date().toISOString() };
          return this.createResponse(updated) as T;
        }
      }
      
      if (method === 'POST' && path.includes('/approve')) {
        if (decision) {
          const updated = { 
            ...decision, 
            status: 'APPROVED',
            decided_at: new Date().toISOString(),
            updated_at: new Date().toISOString() 
          };
          return this.createResponse(updated) as T;
        }
      }
      
      if (method === 'POST' && path.includes('/reject')) {
        if (decision) {
          const updated = { 
            ...decision, 
            status: 'REJECTED',
            decided_at: new Date().toISOString(),
            updated_at: new Date().toISOString() 
          };
          return this.createResponse(updated) as T;
        }
      }
    }

    // Dependencies endpoints
    const dependenciesByInitiativeMatch = path.match(/^dependencies\/by-initiative\/(.+)$/);
    if (dependenciesByInitiativeMatch) {
      const initiativeId = dependenciesByInitiativeMatch[1];
      const dependencies = mockDataStore.getDependenciesByInitiative(initiativeId);
      return this.createResponse(dependencies) as T;
    }

    if (path === 'dependencies') {
      if (method === 'POST' && data) {
        const newDependency = {
          ...data,
          id: `dep-${Date.now()}`,
          status: 'ACTIVE',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return this.createResponse(newDependency) as T;
      }
    }

    const dependencyMatch = path.match(/^dependencies\/(.+)$/);
    if (dependencyMatch) {
      const dependencyId = dependencyMatch[1];
      const dependency = mockDataStore.mockDependencies.find(d => d.id === dependencyId);
      
      if (method === 'PUT' && data) {
        if (dependency) {
          const updated = { ...dependency, ...data, updated_at: new Date().toISOString() };
          return this.createResponse(updated) as T;
        }
      }
      
      if (method === 'DELETE') {
        return this.createResponse(undefined) as T;
      }
    }

    // Benefits endpoints
    const benefitsByInitiativeMatch = path.match(/^benefits\/by-initiative\/(.+)$/);
    if (benefitsByInitiativeMatch) {
      const initiativeId = benefitsByInitiativeMatch[1];
      const benefits = mockDataStore.getBenefitsByInitiative(initiativeId);
      return this.createResponse(benefits) as T;
    }

    if (path === 'benefits') {
      if (method === 'POST' && data) {
        const newBenefit = {
          ...data,
          id: `benefit-${Date.now()}`,
          status: 'PROJECTED',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return this.createResponse(newBenefit) as T;
      }
    }

    const benefitMatch = path.match(/^benefits\/(.+)$/);
    if (benefitMatch) {
      const benefitId = benefitMatch[1];
      const benefit = mockDataStore.mockBenefits.find(b => b.id === benefitId);
      
      if (method === 'PUT' && data) {
        if (benefit) {
          const updated = { ...benefit, ...data, updated_at: new Date().toISOString() };
          return this.createResponse(updated) as T;
        }
      }
      
      if (method === 'DELETE') {
        return this.createResponse(undefined) as T;
      }
      
      if (method === 'POST' && path.includes('/realize')) {
        if (benefit) {
          const updated = { 
            ...benefit, 
            status: 'REALIZED',
            realized_value: benefit.target_value,
            realized_at: new Date().toISOString(),
            updated_at: new Date().toISOString() 
          };
          return this.createResponse(updated) as T;
        }
      }
    }

    // Insights endpoints
    if (path === 'insights') {
      if (method === 'GET') {
        return this.createResponse(mockDataStore.mockInsights) as T;
      }
    }

    const insightMatch = path.match(/^insights\/(.+)$/);
    if (insightMatch) {
      const insightId = insightMatch[1];
      const insight = mockDataStore.mockInsights.find(i => i.id === insightId);
      
      if (method === 'GET') {
        if (insight) return this.createResponse(insight) as T;
        throw new Error('Insight not found');
      }
      
      if (method === 'POST' && path.includes('/dismiss')) {
        if (insight) {
          const updated = { 
            ...insight, 
            status: 'DISMISSED',
            updated_at: new Date().toISOString() 
          };
          return this.createResponse(updated) as T;
        }
      }
    }

    // Adoption endpoints
    if (path === 'adoption/signals') {
      if (method === 'GET') {
        return this.createResponse(mockDataStore.mockAdoptionSignals) as T;
      }
      if (method === 'POST' && data) {
        const newSignal = {
          ...data,
          id: `signal-${Date.now()}`,
          recorded_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
        };
        return this.createResponse(newSignal) as T;
      }
    }

    const signalsByInitiativeMatch = path.match(/^adoption\/signals\/(.+)$/);
    if (signalsByInitiativeMatch) {
      const initiativeId = signalsByInitiativeMatch[1];
      const signals = mockDataStore.mockAdoptionSignals.filter(s => s.initiative_id === initiativeId);
      return this.createResponse(signals) as T;
    }

    const trendsMatch = path.match(/^adoption\/trends\/(.+)$/);
    if (trendsMatch) {
      const initiativeId = trendsMatch[1];
      return this.createResponse({
        initiative_id: initiativeId,
        trend_direction: 'STABLE',
        confidence: 0.75,
        data_points: 12,
      }) as T;
    }

    const predictabilityMatch = path.match(/^adoption\/predictability\/(.+)$/);
    if (predictabilityMatch) {
      const initiativeId = predictabilityMatch[1];
      return this.createResponse({
        initiative_id: initiativeId,
        score: 78,
        trend: 'IMPROVING',
        factors: ['Consistent milestone completion', 'Regular status updates'],
      }) as T;
    }

    if (path === 'adoption/anomalies') {
      if (method === 'GET') {
        return this.createResponse(mockDataStore.mockAnomalies) as T;
      }
    }

    const anomalyMatch = path.match(/^adoption\/anomalies\/(.+)$/);
    if (anomalyMatch) {
      const anomalyId = anomalyMatch[1];
      const anomaly = mockDataStore.mockAnomalies.find(a => a.id === anomalyId);
      
      if (method === 'GET') {
        if (anomaly) return this.createResponse(anomaly) as T;
        throw new Error('Anomaly not found');
      }
      
      if (method === 'PATCH' && path.includes('/resolve')) {
        if (anomaly) {
          const updated = { 
            ...anomaly, 
            status: 'RESOLVED',
            resolved_at: new Date().toISOString(),
            updated_at: new Date().toISOString() 
          };
          return this.createResponse(updated) as T;
        }
      }
    }

    // Approvals endpoints
    if (path === 'approvals/pending') {
      const pending = mockDataStore.mockApprovalRequests.filter(r => r.status === 'PENDING');
      return this.createResponse(pending) as T;
    }

    const approvalMatch = path.match(/^approvals\/(.+)$/);
    if (approvalMatch) {
      const requestId = approvalMatch[1];
      const request = mockDataStore.mockApprovalRequests.find(r => r.id === requestId);
      
      if (method === 'GET') {
        if (request) return this.createResponse(request) as T;
        throw new Error('Approval request not found');
      }
      
      if (method === 'POST' && path.includes('/review')) {
        if (request) {
          const updated = { 
            ...request, 
            status: 'IN_REVIEW',
            updated_at: new Date().toISOString() 
          };
          return this.createResponse(updated) as T;
        }
      }
      
      if (method === 'POST' && path.includes('/decision')) {
        if (request) {
          const decision = (data as { decision: 'APPROVE' | 'REJECT' }).decision;
          const updated = { 
            ...request, 
            status: decision === 'APPROVE' ? 'APPROVED' : 'REJECTED',
            decided_at: new Date().toISOString(),
            updated_at: new Date().toISOString() 
          };
          return this.createResponse(updated) as T;
        }
      }
    }

    const auditTrailMatch = path.match(/^approvals\/(.+)\/audit-trail$/);
    if (auditTrailMatch) {
      const requestId = auditTrailMatch[1];
      return this.createResponse([
        {
          id: `audit-${Date.now()}`,
          request_id: requestId,
          action: 'CREATED',
          performed_by: 'system',
          performed_at: new Date().toISOString(),
          details: { message: 'Request created' },
        },
      ]) as T;
    }

    // Admin endpoints
    if (path === 'admin/stats') {
      return this.createResponse(mockDataStore.mockDashboardStats) as T;
    }

    if (path === 'admin/config') {
      if (method === 'GET') {
        return this.createResponse({
          terminology: {
            initiative: 'Initiative',
            milestone: 'Milestone',
            risk: 'Risk',
            decision: 'Decision',
            benefit: 'Benefit',
          },
          thresholds: {
            delay_tolerance_days: 7,
            risk_threshold: 'MEDIUM',
          },
        }) as T;
      }
      if (method === 'PUT' && data) {
        return this.createResponse(data) as T;
      }
    }

    if (path === 'admin/reset-demo') {
      if (method === 'POST') {
        return this.createResponse({ success: true, message: 'Demo data reset successfully' }) as T;
      }
    }

    if (path === 'admin/users') {
      return this.createResponse(mockDataStore.mockUsers) as T;
    }

    if (path === 'admin/health') {
      return this.createResponse({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        version: '1.0.0',
      }) as T;
    }

    // Default: return empty response
    console.warn(`Mock API: Unhandled request ${method} ${path}`);
    return this.createResponse({}) as T;
  }
}

const mockHandler = new MockAPIHandler();

// =============================================================================
// Axios Instance
// =============================================================================

const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for auth token injection
axiosInstance.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling and token refresh
axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError<ApiResponse<unknown>>) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // Handle 401 Unauthorized - attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = useAuthStore.getState().refreshToken;
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/refresh`, {
            refresh_token: refreshToken,
          });
          
          const { access_token } = response.data.data || response.data;
          useAuthStore.getState().setToken(access_token);
          
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
          }
          return axiosInstance(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, logout user
        useAuthStore.getState().logout();
        // Emit event for auth error handling instead of direct navigation
        window.dispatchEvent(new CustomEvent('auth:unauthorized', { detail: { redirectTo: '/login' } }));
        return Promise.reject(refreshError);
      }
    }

    // Transform error to standard format
    const apiError: ApiError = {
      code: error.response?.data?.error?.code || 'UNKNOWN_ERROR',
      message: error.response?.data?.error?.message || error.message || 'An unexpected error occurred',
      details: error.response?.data?.error?.details,
    };

    return Promise.reject(apiError);
  }
);

// =============================================================================
// API Client Methods
// =============================================================================

export const apiClient = {
  async request<T>(
    method: string,
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    // Use mock API if enabled
    if (USE_MOCK) {
      const response = await mockHandler.handleRequest<T>(method, url, data, config);
      return (response as unknown as ApiResponse<T>).data || response;
    }

    try {
      let response: AxiosResponse<ApiResponse<T>>;

      switch (method.toUpperCase()) {
        case 'GET':
          response = await axiosInstance.get(url, config);
          break;
        case 'POST':
          response = await axiosInstance.post(url, data, config);
          break;
        case 'PUT':
          response = await axiosInstance.put(url, data, config);
          break;
        case 'PATCH':
          response = await axiosInstance.patch(url, data, config);
          break;
        case 'DELETE':
          response = await axiosInstance.delete(url, config);
          break;
        default:
          throw new Error(`Unsupported HTTP method: ${method}`);
      }

      // Handle wrapped API responses
      if (response.data && typeof response.data === 'object' && 'success' in response.data) {
        const apiResponse = response.data as ApiResponse<T>;
        if (!apiResponse.success) {
          throw apiResponse.error || { code: 'UNKNOWN_ERROR', message: 'Request failed' };
        }
        return apiResponse.data as T;
      }

      return response.data as T;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw error.response?.data?.error || { code: 'NETWORK_ERROR', message: error.message };
      }
      throw error;
    }
  },

  get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.request<T>('GET', url, undefined, config);
  },

  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return this.request<T>('POST', url, data, config);
  },

  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return this.request<T>('PUT', url, data, config);
  },

  patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return this.request<T>('PATCH', url, data, config);
  },

  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.request<T>('DELETE', url, undefined, config);
  },
};

// =============================================================================
// Convenience exports
// =============================================================================

export const get = apiClient.get.bind(apiClient);
export const post = apiClient.post.bind(apiClient);
export const put = apiClient.put.bind(apiClient);
export const patch = apiClient.patch.bind(apiClient);
export const del = apiClient.delete.bind(apiClient);

// =============================================================================
// React Query Client Configuration
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
      retry: (failureCount, error) => {
        // Don't retry on 401 or 403
        const apiError = error as ApiError;
        if (apiError?.code === 'UNAUTHORIZED' || apiError?.code === 'FORBIDDEN') {
          return false;
        }
        return failureCount < MAX_RETRIES;
      },
      retryDelay: (attemptIndex) => Math.min(RETRY_DELAY * (2 ** attemptIndex), 30000),
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});

// =============================================================================
// Query Keys
// =============================================================================

export const queryKeys = {
  // Auth
  auth: {
    all: ['auth'] as const,
    me: () => [...queryKeys.auth.all, 'me'] as const,
    users: () => [...queryKeys.auth.all, 'users'] as const,
  },
  
  // Dashboard
  dashboard: {
    all: ['dashboard'] as const,
    stats: () => [...queryKeys.dashboard.all, 'stats'] as const,
    health: () => [...queryKeys.dashboard.all, 'health'] as const,
  },
  
  // Initiatives
  initiatives: {
    all: ['initiatives'] as const,
    list: (filters?: Record<string, unknown>) => [...queryKeys.initiatives.all, 'list', filters] as const,
    detail: (id: string) => [...queryKeys.initiatives.all, 'detail', id] as const,
    health: (id: string) => [...queryKeys.initiatives.all, 'health', id] as const,
  },
  
  // Milestones
  milestones: {
    all: ['milestones'] as const,
    byInitiative: (initiativeId: string) => [...queryKeys.milestones.all, 'byInitiative', initiativeId] as const,
    detail: (id: string) => [...queryKeys.milestones.all, 'detail', id] as const,
  },
  
  // Risks
  risks: {
    all: ['risks'] as const,
    byInitiative: (initiativeId: string) => [...queryKeys.risks.all, 'byInitiative', initiativeId] as const,
    detail: (id: string) => [...queryKeys.risks.all, 'detail', id] as const,
    dashboard: () => [...queryKeys.risks.all, 'dashboard'] as const,
  },
  
  // Decisions
  decisions: {
    all: ['decisions'] as const,
    byInitiative: (initiativeId: string) => [...queryKeys.decisions.all, 'byInitiative', initiativeId] as const,
    detail: (id: string) => [...queryKeys.decisions.all, 'detail', id] as const,
  },
  
  // Dependencies
  dependencies: {
    all: ['dependencies'] as const,
    byInitiative: (initiativeId: string) => [...queryKeys.dependencies.all, 'byInitiative', initiativeId] as const,
    detail: (id: string) => [...queryKeys.dependencies.all, 'detail', id] as const,
  },
  
  // Benefits
  benefits: {
    all: ['benefits'] as const,
    byInitiative: (initiativeId: string) => [...queryKeys.benefits.all, 'byInitiative', initiativeId] as const,
    detail: (id: string) => [...queryKeys.benefits.all, 'detail', id] as const,
  },
  
  // Insights
  insights: {
    all: ['insights'] as const,
    list: () => [...queryKeys.insights.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.insights.all, 'detail', id] as const,
    narrative: () => [...queryKeys.insights.all, 'narrative'] as const,
    recommendations: () => [...queryKeys.insights.all, 'recommendations'] as const,
  },
  
  // Adoption
  adoption: {
    all: ['adoption'] as const,
    signals: (initiativeId?: string) => [...queryKeys.adoption.all, 'signals', initiativeId] as const,
    trends: (initiativeId: string) => [...queryKeys.adoption.all, 'trends', initiativeId] as const,
    predictability: (initiativeId: string) => [...queryKeys.adoption.all, 'predictability', initiativeId] as const,
    anomalies: () => [...queryKeys.adoption.all, 'anomalies'] as const,
    anomaly: (id: string) => [...queryKeys.adoption.all, 'anomaly', id] as const,
  },
  
  // Approvals
  approvals: {
    all: ['approvals'] as const,
    pending: () => [...queryKeys.approvals.all, 'pending'] as const,
    detail: (id: string) => [...queryKeys.approvals.all, 'detail', id] as const,
    auditTrail: (id: string) => [...queryKeys.approvals.all, 'auditTrail', id] as const,
  },
  
  // Admin
  admin: {
    all: ['admin'] as const,
    stats: () => [...queryKeys.admin.all, 'stats'] as const,
    config: () => [...queryKeys.admin.all, 'config'] as const,
    users: () => [...queryKeys.admin.all, 'users'] as const,
    health: () => [...queryKeys.admin.all, 'health'] as const,
  },
};

export default apiClient;
