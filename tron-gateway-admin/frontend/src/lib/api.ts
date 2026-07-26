import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/authStore';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Axios 인스턴스 생성
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// 요청 인터셉터 - 토큰 자동 추가
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const accessToken = useAuthStore.getState().accessToken;
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 응답 인터셉터 - 토큰 갱신 처리
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // 401 에러 시 토큰 갱신 시도
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = useAuthStore.getState().refreshToken;
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token } = response.data;
          useAuthStore.getState().setAuth({
            ...response.data,
            admin: useAuthStore.getState().admin!,
          });

          // 원래 요청 재시도
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          // 리프레시 실패 시 로그아웃
          useAuthStore.getState().logout();
          window.location.href = '/login';
          return Promise.reject(refreshError);
        }
      }
    }

    return Promise.reject(error);
  }
);

// ==========================================
// API 함수들
// ==========================================

// 인증
export const authApi = {
  login: (username: string, password: string, totp_code?: string) =>
    api.post('/api/auth/login', { username, password, totp_code }),

  logout: (refreshToken?: string, logoutAll?: boolean) =>
    api.post('/api/auth/logout', null, {
      params: { refresh_token: refreshToken, logout_all: logoutAll },
    }),

  refresh: (refreshToken: string) =>
    api.post('/api/auth/refresh', { refresh_token: refreshToken }),

  me: () => api.get('/api/auth/me'),

  changePassword: (currentPassword: string, newPassword: string) =>
    api.post('/api/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
};

// 대시보드
export const dashboardApi = {
  getStats: () => api.get('/api/dashboard/stats'),

  getChartData: (days: number = 7) =>
    api.get('/api/dashboard/chart/transactions', { params: { days } }),

  getRecentTransactions: (limit: number = 50, type?: 'deposit' | 'withdrawal') =>
    api.get('/api/dashboard/transactions/recent', { params: { limit, tx_type: type } }),

  getDeposits: (params?: { user_id?: number; status?: string; swept?: boolean; page?: number; limit?: number; start_date?: string; end_date?: string }) =>
    api.get('/api/dashboard/deposits', { params }),

  getWithdrawals: (params?: { user_id?: number; status?: string; page?: number; limit?: number; start_date?: string; end_date?: string }) =>
    api.get('/api/dashboard/withdrawals', { params }),

  getWallets: (params?: { user_id?: number; page?: number; limit?: number }) =>
    api.get('/api/dashboard/wallets', { params }),

  getWalletDetail: (userId: number) =>
    api.get(`/api/dashboard/wallets/${userId}`),
};

// 지갑
export const walletApi = {
  create: (userId: number) =>
    api.post('/api/wallet/create', { user_id: userId }),

  getBalance: (userId: number) =>
    api.get(`/api/wallet/${userId}`),
};

// 파트너
export const partnerApi = {
  list: (params?: { is_active?: boolean; page?: number; limit?: number }) =>
    api.get('/api/partners', { params }),

  get: (partnerId: number) => api.get(`/api/partners/${partnerId}`),

  create: (data: { name: string; code: string; description?: string; webhook_url?: string; fee_rate?: number }) =>
    api.post('/api/partners', data),

  update: (partnerId: number, data: Partial<{ name: string; description: string; webhook_url: string; fee_rate: number; is_active: boolean }>) =>
    api.patch(`/api/partners/${partnerId}`, data),

  delete: (partnerId: number) => api.delete(`/api/partners/${partnerId}`),

  regenerateSecret: (partnerId: number) =>
    api.post(`/api/partners/${partnerId}/regenerate-api-secret`),
};

// 관리자
export const adminApi = {
  list: (params?: { partner_id?: number; role?: string; page?: number; limit?: number }) =>
    api.get('/api/auth/admins', { params }),

  get: (adminId: number) => api.get(`/api/auth/admins/${adminId}`),

  create: (data: { username: string; password: string; email?: string; full_name?: string; role: string; partner_id?: number }) =>
    api.post('/api/auth/admins', data),

  update: (adminId: number, data: Partial<{ full_name: string; phone: string; is_active: boolean; role: string; password: string; partner_id: number }>) =>
    api.patch(`/api/auth/admins/${adminId}`, data),

  delete: (adminId: number) => api.delete(`/api/auth/admins/${adminId}`),

  getAuditLogs: (params?: { admin_id?: number; action?: string; page?: number; limit?: number }) =>
    api.get('/api/auth/audit-logs', { params }),
};

// 시스템
export const systemApi = {
  getStatus: () => api.get('/api/system/status'),

  getConfigs: (category?: string) =>
    api.get('/api/system/configs', { params: { category } }),

  updateConfig: (key: string, value: string, description?: string) =>
    api.put(`/api/system/configs/${key}`, { value, description }),

  initConfigs: () => api.post('/api/system/configs/init'),
};

export default api;
