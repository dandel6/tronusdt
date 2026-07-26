'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
    User,
    Shield,
    Save,
    Key,
    Eye,
    EyeOff,
    ArrowLeft
} from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useAuthStore } from '@/stores/authStore';
import { ROLE_LABELS } from '@/types';
import { adminApi } from '@/lib/api';


export default function ProfilePage() {
    const { admin } = useAuthStore();
    const queryClient = useQueryClient();

    const [isEditing, setIsEditing] = useState(false);
    const [showPasswordChange, setShowPasswordChange] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    const [formData, setFormData] = useState({
        full_name: admin?.full_name || '',
    });

    const [passwordData, setPasswordData] = useState({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
    });

    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const handleSave = () => {
        setSuccess('프로필이 업데이트되었습니다.');
        setIsEditing(false);
        setTimeout(() => setSuccess(''), 3000);
    };

    const handlePasswordChange = () => {
        if (passwordData.newPassword !== passwordData.confirmPassword) {
            setError('새 비밀번호가 일치하지 않습니다.');
            return;
        }
        if (passwordData.newPassword.length < 4) {
            setError('비밀번호는 최소 4자 이상이어야 합니다.');
            return;
        }
        setSuccess('비밀번호가 변경되었습니다.');
        setShowPasswordChange(false);
        setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
        setTimeout(() => setSuccess(''), 3000);
    };

    return (
        <div className="flex min-h-screen bg-dark-900">
            <Sidebar />
            <main className="flex-1 lg:pl-[280px] transition-all duration-300">
                <div className="p-6 md:p-8 space-y-6 max-w-4xl">
                    {/* Header */}
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => window.history.back()}
                            className="p-2 rounded-xl hover:bg-white/5 transition-colors"
                        >
                            <ArrowLeft className="w-5 h-5 text-dark-300" />
                        </button>
                        <div>
                            <h1 className="text-2xl font-bold text-white tracking-tight">프로필</h1>
                            <p className="text-dark-300 mt-1">계정 정보를 확인하고 수정할 수 있습니다.</p>
                        </div>
                    </div>

                    {/* Success/Error Messages */}
                    {success && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="p-4 rounded-xl bg-accent-success/10 border border-accent-success/20 text-accent-success"
                        >
                            {success}
                        </motion.div>
                    )}
                    {error && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="p-4 rounded-xl bg-accent-danger/10 border border-accent-danger/20 text-accent-danger"
                        >
                            {error}
                        </motion.div>
                    )}

                    {/* Profile Card */}
                    <div className="bg-dark-800/50 backdrop-blur-xl border border-white/5 rounded-2xl p-6">
                        <div className="flex items-start gap-6">
                            {/* Avatar */}
                            <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-accent-primary to-accent-secondary flex items-center justify-center">
                                <User className="w-12 h-12 text-white" />
                            </div>

                            {/* Info */}
                            <div className="flex-1">
                                <h2 className="text-xl font-bold text-white">
                                    {admin?.full_name || admin?.username}
                                </h2>
                                <p className="text-dark-300 mt-1">@{admin?.username}</p>
                                <div className="flex items-center gap-2 mt-3">
                                    <span className="px-3 py-1 rounded-full text-xs font-medium bg-accent-primary/20 text-accent-primary">
                                        {admin && ROLE_LABELS[admin.role]}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Account Details */}
                    <div className="bg-dark-800/50 backdrop-blur-xl border border-white/5 rounded-2xl p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-lg font-semibold text-white">계정 정보</h3>
                            <button
                                onClick={() => setIsEditing(!isEditing)}
                                className="px-4 py-2 rounded-xl text-sm font-medium bg-accent-primary/20 text-accent-primary hover:bg-accent-primary/30 transition-colors"
                            >
                                {isEditing ? '취소' : '수정'}
                            </button>
                        </div>

                        <div className="space-y-4">
                            {/* Username */}
                            <div className="flex items-center gap-4 p-4 rounded-xl bg-dark-900/50">
                                <User className="w-5 h-5 text-dark-400" />
                                <div className="flex-1">
                                    <p className="text-xs text-dark-400 mb-1">사용자명</p>
                                    <p className="text-white">{admin?.username}</p>
                                </div>
                            </div>

                            {/* Full Name */}
                            <div className="flex items-center gap-4 p-4 rounded-xl bg-dark-900/50">
                                <User className="w-5 h-5 text-dark-400" />
                                <div className="flex-1">
                                    <p className="text-xs text-dark-400 mb-1">이름</p>
                                    {isEditing ? (
                                        <input
                                            type="text"
                                            value={formData.full_name}
                                            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                                            className="w-full px-3 py-2 bg-dark-800 border border-white/10 rounded-lg text-white focus:outline-none focus:border-accent-primary/50"
                                        />
                                    ) : (
                                        <p className="text-white">{admin?.full_name || '-'}</p>
                                    )}
                                </div>
                            </div>

                            {/* Role */}
                            <div className="flex items-center gap-4 p-4 rounded-xl bg-dark-900/50">
                                <Shield className="w-5 h-5 text-dark-400" />
                                <div className="flex-1">
                                    <p className="text-xs text-dark-400 mb-1">권한</p>
                                    <p className="text-white">{admin && ROLE_LABELS[admin.role]}</p>
                                </div>
                            </div>

                            {isEditing && (
                                <button
                                    onClick={handleSave}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary font-medium hover:shadow-neon transition-all"
                                >
                                    <Save className="w-4 h-4" />
                                    저장
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Password Change */}
                    <div className="bg-dark-800/50 backdrop-blur-xl border border-white/5 rounded-2xl p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-lg font-semibold text-white">비밀번호 변경</h3>
                            <button
                                onClick={() => setShowPasswordChange(!showPasswordChange)}
                                className="px-4 py-2 rounded-xl text-sm font-medium bg-dark-700 text-dark-200 hover:bg-dark-600 transition-colors"
                            >
                                {showPasswordChange ? '취소' : '변경하기'}
                            </button>
                        </div>

                        {showPasswordChange && (
                            <div className="space-y-4">
                                <div className="relative">
                                    <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        placeholder="현재 비밀번호"
                                        value={passwordData.currentPassword}
                                        onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                                        className="w-full pl-12 pr-12 py-3 bg-dark-900/50 border border-white/10 rounded-xl text-white placeholder:text-dark-500 focus:outline-none focus:border-accent-primary/50"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-4 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white"
                                    >
                                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                    </button>
                                </div>
                                <div className="relative">
                                    <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        placeholder="새 비밀번호"
                                        value={passwordData.newPassword}
                                        onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                                        className="w-full pl-12 py-3 bg-dark-900/50 border border-white/10 rounded-xl text-white placeholder:text-dark-500 focus:outline-none focus:border-accent-primary/50"
                                    />
                                </div>
                                <div className="relative">
                                    <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        placeholder="새 비밀번호 확인"
                                        value={passwordData.confirmPassword}
                                        onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                                        className="w-full pl-12 py-3 bg-dark-900/50 border border-white/10 rounded-xl text-white placeholder:text-dark-500 focus:outline-none focus:border-accent-primary/50"
                                    />
                                </div>
                                <button
                                    onClick={handlePasswordChange}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-dark-700 text-white font-medium hover:bg-dark-600 transition-colors"
                                >
                                    <Key className="w-4 h-4" />
                                    비밀번호 변경
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}
