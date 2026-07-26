import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Admin, TokenResponse, Permission } from '@/types';

interface AuthState {
  // 상태
  admin: Admin | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // 액션
  setAuth: (data: TokenResponse) => void;
  updateAdmin: (admin: Partial<Admin>) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
  
  // 권한 체크
  hasPermission: (permission: Permission) => boolean;
  isSuperAdmin: () => boolean;
  isPartnerAdmin: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // 초기 상태
      admin: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: true,

      // 로그인 성공 시 호출
      setAuth: (data: TokenResponse) => {
        set({
          admin: data.admin,
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          isAuthenticated: true,
          isLoading: false,
        });
      },

      // 관리자 정보 업데이트
      updateAdmin: (updates: Partial<Admin>) => {
        const current = get().admin;
        if (current) {
          set({ admin: { ...current, ...updates } });
        }
      },

      // 로그아웃
      logout: () => {
        set({
          admin: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          isLoading: false,
        });
      },

      // 로딩 상태
      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },

      // 권한 체크
      hasPermission: (permission: Permission) => {
        const admin = get().admin;
        if (!admin) return false;
        return admin.permissions.includes(permission);
      },

      isSuperAdmin: () => {
        return get().admin?.role === 'super_admin';
      },

      isPartnerAdmin: () => {
        return get().admin?.role === 'partner_admin';
      },
    }),
    {
      name: 'tron-gateway-auth',
      partialize: (state) => ({
        admin: state.admin,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// 권한별 메뉴 설정
export const getMenuItems = (admin: Admin | null) => {
  if (!admin) return [];

  const baseMenu = [
    {
      name: '대시보드',
      href: '/dashboard',
      icon: 'LayoutDashboard',
      permission: null, // 모든 권한 접근 가능
    },
  ];

  const walletMenu = admin.permissions.includes('view_wallets')
    ? [{ name: '지갑 관리', href: '/wallets', icon: 'Wallet', permission: 'view_wallets' }]
    : [];

  const depositMenu = admin.permissions.includes('view_deposits')
    ? [{ name: '입금 내역', href: '/deposits', icon: 'ArrowDownCircle', permission: 'view_deposits' }]
    : [];

  const withdrawalMenu = admin.permissions.includes('view_withdrawals')
    ? [{ name: '출금 내역', href: '/withdrawals', icon: 'ArrowUpCircle', permission: 'view_withdrawals' }]
    : [];

  const partnerMenu = admin.permissions.includes('manage_partners')
    ? [{ name: '파트너 관리', href: '/partners', icon: 'Building2', permission: 'manage_partners' }]
    : [];

  const adminMenu = admin.role !== 'partner_staff'
    ? [{ name: '관리자', href: '/admins', icon: 'Users', permission: null }]
    : [];

  const systemMenu = admin.permissions.includes('system_settings')
    ? [{ name: '시스템 설정', href: '/settings', icon: 'Settings', permission: 'system_settings' }]
    : [];

  return [
    ...baseMenu,
    ...walletMenu,
    ...depositMenu,
    ...withdrawalMenu,
    ...partnerMenu,
    ...adminMenu,
    ...systemMenu,
  ];
};
