// ==========================================
// 인증 관련 타입
// ==========================================

export type AdminRole = 'super_admin' | 'partner_admin' | 'partner_staff';

export type Permission =
  | 'system_settings'
  | 'manage_partners'
  | 'view_all_data'
  | 'create_wallet'
  | 'view_wallets'
  | 'view_deposits'
  | 'view_withdrawals'
  | 'request_withdrawal'
  | 'approve_withdrawal'
  | 'trigger_sweep';

export interface Admin {
  admin_id: number;
  email: string;
  username: string;
  full_name?: string;
  role: AdminRole;
  partner_id?: number;
  permissions: Permission[];
  is_2fa_enabled: boolean;
  last_login_at?: string;
  created_at: string;
}

export interface Partner {
  partner_id: number;
  name: string;
  code: string;
  description?: string;
  api_key: string;
  webhook_url?: string;
  fee_rate: number;
  daily_withdrawal_limit: number;
  is_active: boolean;
  admin_count?: number;
  created_at: string;
  updated_at?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  totp_code?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  admin: Admin;
}

// ==========================================
// 대시보드 관련 타입
// ==========================================

export interface DashboardStats {
  total_users: number;
  total_deposits: {
    count: number;
    amount: number;
  };
  total_withdrawals: {
    count: number;
    amount: number;
  };
  pending_withdrawals: {
    count: number;
    amount: number;
  };
  unswept_deposits: {
    count: number;
    amount: number;
  };
  today: {
    deposits: { count: number; amount: number };
    withdrawals: { count: number; amount: number };
  };
  total_fees?: {
    amount: number;
    today_amount: number;
  };
  main_wallet?: {
    address: string;
    usdt_balance: number;
    trx_balance: number;
    energy_available: number;
    bandwidth_available: number;
  };
  timestamp: string;
}

export interface Transaction {
  type: 'deposit' | 'withdrawal';
  id: string;
  user_id: number;
  amount: number;
  from_address?: string;
  to_address?: string;
  tx_id?: string;
  status: string;
  swept?: boolean;
  created_at: string;
}

export interface Deposit {
  tx_id: string;
  user_id: number;
  amount: number;
  from_address: string;
  status: string;
  confirmations: number;
  swept: boolean;
  sweep_tx_id?: string;
  created_at: string;
}

export interface Withdrawal {
  withdrawal_id: number;
  user_id: number;
  to_address: string;
  amount: number;
  tx_id?: string;
  status: string;
  error_message?: string;
  created_at: string;
  processed_at?: string;
}

export interface Wallet {
  user_id: number;
  wallet_address: string;
  derivation_path: string;
  balance: number;
  usdt_balance?: number;
  trx_balance?: number;
  created_at: string;
}

// ==========================================
// 차트 데이터 타입
// ==========================================

export interface ChartDataPoint {
  date: string;
  deposits: {
    count: number;
    amount: number;
  };
  withdrawals: {
    count: number;
    amount: number;
  };
}

// ==========================================
// 감사 로그 타입
// ==========================================

export interface AuditLog {
  log_id: number;
  admin_id: number;
  action: string;
  resource_type?: string;
  resource_id?: string;
  details?: string;
  ip_address?: string;
  created_at: string;
}

// ==========================================
// API 응답 타입
// ==========================================

export interface PaginatedResponse<T> {
  data: T[];
  page: number;
  limit: number;
  total?: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

// ==========================================
// 권한 체크 헬퍼
// ==========================================

export const ROLE_LABELS: Record<AdminRole, string> = {
  super_admin: '최상위 관리자',
  partner_admin: '업체 관리자',
  partner_staff: '업체 직원',
};

export const ROLE_COLORS: Record<AdminRole, string> = {
  super_admin: 'text-accent-primary',
  partner_admin: 'text-accent-secondary',
  partner_staff: 'text-accent-info',
};

export const hasPermission = (admin: Admin | null, permission: Permission): boolean => {
  if (!admin) return false;
  return admin.permissions.includes(permission);
};

export const isSuperAdmin = (admin: Admin | null): boolean => {
  return admin?.role === 'super_admin';
};

export const isPartnerAdmin = (admin: Admin | null): boolean => {
  return admin?.role === 'partner_admin';
};

export const canManageUsers = (admin: Admin | null): boolean => {
  return admin?.role === 'super_admin' || admin?.role === 'partner_admin';
};
