'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
    Search,
    Plus,
    MoreVertical,
    Calendar,
    LogIn,
    X,
    Eye,
    EyeOff,
    Users,
    Edit,
} from 'lucide-react';
import { format } from 'date-fns';
import { adminApi } from '@/lib/api';
import { AdminRole, ROLE_LABELS } from '@/types';
import { useAuthStore } from '@/stores/authStore';
import { Sidebar } from '@/components/layout/Sidebar';
import axios from 'axios';

export default function AdminsPage() {
    const [page, setPage] = useState(1);
    const [roleFilter, setRoleFilter] = useState<string>('');
    const queryClient = useQueryClient();
    const { admin: currentAdmin } = useAuthStore();

    // Modal states
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [formData, setFormData] = useState({
        username: '',
        password: '',
        full_name: '',
        role: 'partner_staff' as string,
        partner_id: '' as string,
    });
    const [createError, setCreateError] = useState('');
    const [activeMenuId, setActiveMenuId] = useState<number | null>(null);
    const [editingAdmin, setEditingAdmin] = useState<any>(null);

    // Fetch partners for dropdown
    const { data: partnersData } = useQuery({
        queryKey: ['partners'],
        queryFn: async () => {
            const token = localStorage.getItem('access_token');
            const response = await axios.get('/api/auth/partners', {
                headers: { Authorization: `Bearer ${token}` }
            });
            return response.data;
        },
        enabled: currentAdmin?.role === 'super_admin',
    });

    const { data, isLoading } = useQuery({
        queryKey: ['admins', page, roleFilter],
        queryFn: () => adminApi.list({
            page,
            limit: 20,
            role: roleFilter || undefined
        }),
    });

    const createMutation = useMutation({
        mutationFn: (data: { username: string; password: string; full_name?: string; role: string; partner_id?: number }) =>
            adminApi.create(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['admins'] });
            setShowCreateModal(false);
            setFormData({ username: '', password: '', full_name: '', role: 'partner_staff', partner_id: '' });
            setCreateError('');
        },
        onError: (error: any) => {
            setCreateError(error.response?.data?.detail || '관리자 생성에 실패했습니다.');
        }
    });

    const handleSubmit = () => {
        setCreateError('');

        if (!formData.username || !formData.password) {
            setCreateError('아이디와 비밀번호는 필수입니다.');
            return;
        }

        // Partner Admin/Staff 생성 시 파트너 필수 (Super Admin일 때만 선택)
        if (currentAdmin?.role === 'super_admin' &&
            (formData.role === 'partner_admin' || formData.role === 'partner_staff') &&
            !formData.partner_id) {
            setCreateError('파트너(그룹)를 선택해주세요.');
            return;
        }

        createMutation.mutate({
            username: formData.username,
            password: formData.password,
            full_name: formData.full_name || undefined,
            role: formData.role,
            partner_id: formData.partner_id ? parseInt(formData.partner_id) : undefined,
        });
    };

    const canCreateAdmin = currentAdmin?.role === 'super_admin' || currentAdmin?.role === 'partner_admin';

    return (
        <div className="flex min-h-screen bg-dark-900">
            <Sidebar />
            <main className="flex-1 lg:pl-[280px] transition-all duration-300">
                <div className="p-6 md:p-8 space-y-6">
                    {/* Header */}
                    <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold text-white tracking-tight">
                                {currentAdmin?.role === 'partner_admin' ? '내 스태프 관리' : '관리자 관리'}
                            </h1>
                            <p className="text-dark-300 mt-1">
                                {currentAdmin?.role === 'partner_admin'
                                    ? '내 파트너에 소속된 스태프를 관리합니다.'
                                    : '시스템 관리자 계정을 관리합니다.'}
                            </p>
                        </div>

                        {canCreateAdmin && (
                            <button
                                className="flex items-center gap-2 px-4 py-2 bg-accent-primary hover:bg-accent-primary/90 text-white rounded-lg transition-colors shadow-lg shadow-accent-primary/20"
                                onClick={() => setShowCreateModal(true)}
                            >
                                <Plus className="w-4 h-4" />
                                <span>관리자 추가</span>
                            </button>
                        )}
                    </div>

                    {/* Filters */}
                    <div className="flex gap-4 p-4 bg-dark-800/50 backdrop-blur-xl border border-white/5 rounded-2xl">
                        <div className="relative flex-1 max-w-xs">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                            <input
                                type="text"
                                placeholder="이름 또는 이메일 검색..."
                                className="w-full pl-10 h-10 bg-dark-900/50 border border-white/5 rounded-xl text-white placeholder:text-dark-500 focus:outline-none focus:border-accent-primary/50 transition-colors"
                            />
                        </div>
                        <select
                            value={roleFilter}
                            onChange={(e) => setRoleFilter(e.target.value)}
                            className="h-10 px-4 bg-dark-900/50 border border-white/5 rounded-xl text-white focus:outline-none focus:border-accent-primary/50 transition-colors"
                        >
                            <option value="">모든 권한</option>
                            {Object.entries(ROLE_LABELS).map(([key, label]) => (
                                <option key={key} value={key}>{label}</option>
                            ))}
                        </select>
                    </div>

                    {/* List */}
                    <div className="bg-dark-800/50 backdrop-blur-xl border border-white/5 rounded-2xl overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-white/5 bg-white/5">
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">관리자</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">권한</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">상태</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">마지막 로그인</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">등록일</th>
                                        <th className="px-6 py-4 text-right text-xs font-medium text-dark-300 uppercase tracking-wider">관리</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {isLoading ? (
                                        <tr>
                                            <td colSpan={6} className="px-6 py-8 text-center text-dark-400">
                                                로딩 중...
                                            </td>
                                        </tr>
                                    ) : !data?.data?.admins || data.data.admins.length === 0 ? (
                                        <tr>
                                            <td colSpan={6} className="px-6 py-8 text-center text-dark-400">
                                                등록된 관리자가 없습니다.
                                            </td>
                                        </tr>
                                    ) : (
                                        data.data.admins.map((admin: any) => (
                                            <tr
                                                key={admin.admin_id}
                                                className="group hover:bg-white/5 transition-colors"
                                            >
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-10 h-10 rounded-full bg-dark-700 flex items-center justify-center text-dark-300 font-medium border border-white/5">
                                                            {admin.full_name?.[0] || admin.username[0].toUpperCase()}
                                                        </div>
                                                        <div>
                                                            <div className="text-sm font-medium text-white">
                                                                {admin.full_name || admin.username}
                                                            </div>
                                                            <div className="text-xs text-dark-400">
                                                                {admin.email || admin.username}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${admin.role === 'super_admin' ? 'bg-accent-primary/10 text-accent-primary' :
                                                        admin.role === 'partner_admin' ? 'bg-accent-secondary/10 text-accent-secondary' :
                                                            'bg-dark-600 text-dark-300'
                                                        }`}>
                                                        {ROLE_LABELS[admin.role as AdminRole] || admin.role}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <div className="flex items-center gap-1.5">
                                                        <div className={`w-1.5 h-1.5 rounded-full ${admin.is_active ? 'bg-accent-success' : 'bg-accent-danger'}`} />
                                                        <span className={`text-sm ${admin.is_active ? 'text-accent-success' : 'text-accent-danger'}`}>
                                                            {admin.is_active ? '활성' : '비활성'}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <div className="flex items-center gap-1.5 text-sm text-dark-300">
                                                        {admin.last_login_at ? (
                                                            <>
                                                                <LogIn className="w-3.5 h-3.5" />
                                                                {format(new Date(admin.last_login_at), 'yyyy-MM-dd HH:mm')}
                                                            </>
                                                        ) : (
                                                            <span className="text-dark-500">-</span>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <div className="flex items-center gap-1.5 text-sm text-dark-300">
                                                        <Calendar className="w-3.5 h-3.5" />
                                                        {format(new Date(admin.created_at), 'yyyy-MM-dd')}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-right relative">
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            setActiveMenuId(activeMenuId === admin.admin_id ? null : admin.admin_id);
                                                        }}
                                                        className="p-2 text-dark-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                                                    >
                                                        <MoreVertical className="w-4 h-4" />
                                                    </button>
                                                    {activeMenuId === admin.admin_id && (
                                                        <div className="absolute right-8 top-1/2 -translate-y-1/2 w-32 bg-dark-800 border border-white/10 rounded-lg shadow-xl z-10 py-1">
                                                            <button
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    setEditingAdmin(admin);
                                                                    setActiveMenuId(null);
                                                                }}
                                                                className="w-full text-left px-4 py-2 text-sm text-dark-200 hover:bg-dark-700 hover:text-white flex items-center gap-2"
                                                            >
                                                                <Edit className="w-4 h-4" />
                                                                관리
                                                            </button>
                                                        </div>
                                                    )}
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>

            {/* Create Admin Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center">
                    <div
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                        onClick={() => setShowCreateModal(false)}
                    />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="relative w-full max-w-lg mx-4 p-6 rounded-2xl bg-dark-800 border border-white/10 shadow-2xl"
                    >
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-white">새 관리자 추가</h2>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                            >
                                <X className="w-5 h-5 text-dark-400" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-dark-300 mb-2">
                                    아이디 <span className="text-accent-danger">*</span>
                                </label>
                                <input
                                    type="text"
                                    value={formData.username}
                                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                    placeholder="아이디 입력"
                                    className="w-full px-4 py-3 bg-dark-900/50 border border-white/10 rounded-xl text-white placeholder:text-dark-500 focus:outline-none focus:border-accent-primary/50"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-dark-300 mb-2">
                                    비밀번호 <span className="text-accent-danger">*</span>
                                </label>
                                <div className="relative">
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        value={formData.password}
                                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                        placeholder="비밀번호 입력"
                                        className="w-full px-4 py-3 pr-12 bg-dark-900/50 border border-white/10 rounded-xl text-white placeholder:text-dark-500 focus:outline-none focus:border-accent-primary/50"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-dark-400 hover:text-white"
                                    >
                                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-dark-300 mb-2">
                                    이름 (선택)
                                </label>
                                <input
                                    type="text"
                                    value={formData.full_name}
                                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                                    placeholder="예: 홍길동"
                                    className="w-full px-4 py-3 bg-dark-900/50 border border-white/10 rounded-xl text-white placeholder:text-dark-500 focus:outline-none focus:border-accent-primary/50"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-dark-300 mb-2">
                                    권한
                                </label>
                                <select
                                    value={formData.role}
                                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                                    className="w-full px-4 py-3 bg-dark-900/50 border border-white/10 rounded-xl text-white focus:outline-none focus:border-accent-primary/50"
                                >
                                    {currentAdmin?.role === 'super_admin' && (
                                        <>
                                            <option value="super_admin">최상위 관리자 (Super Admin)</option>
                                            <option value="partner_admin">업체 관리자 (Partner Admin)</option>
                                        </>
                                    )}
                                    <option value="partner_staff">업체 직원 (Partner Staff)</option>
                                </select>
                            </div>

                            {/* Partner 선택 - Super Admin이 Partner Admin/Staff 생성 시 */}
                            {currentAdmin?.role === 'super_admin' &&
                                (formData.role === 'partner_admin' || formData.role === 'partner_staff') && (
                                    <div>
                                        <label className="block text-sm font-medium text-dark-300 mb-2">
                                            파트너 (그룹) <span className="text-accent-danger">*</span>
                                        </label>
                                        <select
                                            value={formData.partner_id}
                                            onChange={(e) => setFormData({ ...formData, partner_id: e.target.value })}
                                            className="w-full px-4 py-3 bg-dark-900/50 border border-white/10 rounded-xl text-white focus:outline-none focus:border-accent-primary/50"
                                        >
                                            <option value="">파트너 선택...</option>
                                            {partnersData?.partners?.map((partner: any) => (
                                                <option key={partner.partner_id} value={partner.partner_id}>
                                                    {partner.name} ({partner.code})
                                                </option>
                                            ))}
                                        </select>
                                        <p className="text-xs text-dark-400 mt-1">
                                            관리자가 속할 파트너(그룹)를 선택하세요.
                                        </p>
                                    </div>
                                )}

                            {createError && (
                                <div className="p-3 rounded-lg bg-accent-danger/10 border border-accent-danger/20 text-accent-danger text-sm">
                                    {createError}
                                </div>
                            )}

                            <div className="flex gap-3 pt-2">
                                <button
                                    onClick={() => setShowCreateModal(false)}
                                    className="flex-1 px-4 py-3 rounded-xl bg-dark-700 text-dark-300 font-medium hover:bg-dark-600 transition-colors"
                                >
                                    취소
                                </button>
                                <button
                                    onClick={handleSubmit}
                                    disabled={createMutation.isPending}
                                    className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary font-medium hover:shadow-neon transition-all disabled:opacity-50"
                                >
                                    {createMutation.isPending ? '생성 중...' : '관리자 생성'}
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </div>
            )}

            {/* Edit Admin Modal */}
            {editingAdmin && (
                <EditAdminModal
                    isOpen={!!editingAdmin}
                    onClose={() => setEditingAdmin(null)}
                    admin={editingAdmin}
                    partners={partnersData?.partners || []}
                    onSuccess={() => {
                        queryClient.invalidateQueries({ queryKey: ['admins'] });
                        setEditingAdmin(null);
                    }}
                />
            )}
        </div>
    );
}

function EditAdminModal({
    isOpen,
    onClose,
    admin,
    partners,
    onSuccess
}: {
    isOpen: boolean;
    onClose: () => void;
    admin: any;
    partners: any[];
    onSuccess: () => void;
}) {
    const { admin: currentAdmin } = useAuthStore();
    const [formData, setFormData] = useState({
        full_name: admin.full_name || '',
        partner_id: admin.partner_id || '',
    });
    const [error, setError] = useState('');

    const updateMutation = useMutation({
        mutationFn: (data: any) => adminApi.update(admin.admin_id, data),
        onSuccess: () => {
            onSuccess();
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || '수정에 실패했습니다.');
        }
    });

    const handleSubmit = () => {
        const updateData: any = {
            full_name: formData.full_name
        };

        if (currentAdmin?.role === 'super_admin' && formData.partner_id) {
            updateData.partner_id = parseInt(String(formData.partner_id));
        }

        updateMutation.mutate(updateData);
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-dark-800 border border-white/10 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden"
            >
                <div className="p-6 border-b border-white/5 flex items-center justify-between">
                    <h3 className="text-lg font-bold text-white">관리자 정보 수정</h3>
                    <button onClick={onClose} className="text-dark-400 hover:text-white">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-6 space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-dark-300 mb-2">
                            아이디
                        </label>
                        <input
                            type="text"
                            value={admin.username}
                            disabled
                            className="w-full px-4 py-3 bg-dark-900/30 border border-white/5 rounded-xl text-dark-400 cursor-not-allowed"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-dark-300 mb-2">
                            별명 (이름)
                        </label>
                        <input
                            type="text"
                            value={formData.full_name}
                            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                            className="w-full px-4 py-3 bg-dark-900/50 border border-white/10 rounded-xl text-white focus:outline-none focus:border-accent-primary/50"
                            placeholder="별명 입력"
                        />
                    </div>

                    {currentAdmin?.role === 'super_admin' &&
                        (admin.role === 'partner_admin' || admin.role === 'partner_staff') && (
                            <div>
                                <label className="block text-sm font-medium text-dark-300 mb-2">
                                    파트너 (그룹)
                                </label>
                                <select
                                    value={formData.partner_id}
                                    onChange={(e) => setFormData({ ...formData, partner_id: e.target.value })}
                                    className="w-full px-4 py-3 bg-dark-900/50 border border-white/10 rounded-xl text-white focus:outline-none focus:border-accent-primary/50"
                                >
                                    <option value="">파트너 선택...</option>
                                    {partners.map((partner: any) => (
                                        <option key={partner.partner_id} value={partner.partner_id}>
                                            {partner.name} ({partner.code})
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                    {error && (
                        <div className="p-3 rounded-lg bg-accent-danger/10 border border-accent-danger/20 text-accent-danger text-sm">
                            {error}
                        </div>
                    )}

                    <button
                        onClick={handleSubmit}
                        disabled={updateMutation.isPending}
                        className="w-full py-3 rounded-xl bg-accent-primary text-white font-medium hover:bg-accent-primary/90 transition-colors disabled:opacity-50"
                    >
                        {updateMutation.isPending ? '저장 중...' : '저장하기'}
                    </button>
                </div>
            </motion.div>
        </div>
    );
}

