'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    Save,
    RefreshCw,
    DollarSign,
    Shield,
    Bell,
    Settings,
    Database,
    AlertCircle,
    Lock,
    Terminal,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { systemApi } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import { Sidebar } from '@/components/layout/Sidebar';

export default function SettingsPage() {
    const queryClient = useQueryClient();
    const { isSuperAdmin } = useAuthStore();
    const [editingKey, setEditingKey] = useState<string | null>(null);
    const [editValue, setEditValue] = useState('');

    const { data: configData, isLoading, refetch } = useQuery({
        queryKey: ['system-configs'],
        queryFn: () => systemApi.getConfigs(),
        enabled: isSuperAdmin(),
    });

    const updateMutation = useMutation({
        mutationFn: (vars: { key: string, value: string }) =>
            systemApi.updateConfig(vars.key, vars.value),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['system-configs'] });
            setEditingKey(null);
        },
    });

    const initMutation = useMutation({
        mutationFn: () => systemApi.initConfigs(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['system-configs'] });
            refetch();
        },
    });

    const handleEdit = (key: string, currentValue: string) => {
        setEditingKey(key);
        setEditValue(currentValue);
    };

    const handleSave = (key: string) => {
        updateMutation.mutate({ key, value: editValue });
    };

    const sections = [
        { id: 'fee', title: '수수료 및 한도', icon: DollarSign, description: '입금/출금 수수료율과 한도를 설정합니다.' },
        { id: 'security', title: '보안 설정', icon: Shield, description: '로그인 시도 제한 및 계정 잠금 설정입니다.' },
        { id: 'notification', title: '알림 설정', icon: Bell, description: '텔레그램 알림 및 잔액 경고 설정입니다.' },
        { id: 'sweep', title: '스위핑 설정', icon: RefreshCw, description: '자동 스위핑 임계값 및 활성화 설정입니다.' },
    ];

    // Check if there are any configs
    const hasConfigs = configData?.data?.configs &&
        Object.values(configData.data.configs).some((arr: any) => arr && arr.length > 0);

    return (
        <div className="flex min-h-screen bg-dark-900">
            <Sidebar />
            <main className="flex-1 lg:pl-[280px] transition-all duration-300">
                <div className="p-6 md:p-8 space-y-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold text-white tracking-tight">시스템 설정</h1>
                            <p className="text-dark-300 mt-1">전역 시스템 환경변수를 설정합니다.</p>
                        </div>
                        {isSuperAdmin() && (
                            <button
                                onClick={() => refetch()}
                                className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 text-white border border-white/5 rounded-lg transition-colors"
                            >
                                <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                                새로고침
                            </button>
                        )}
                    </div>

                    {!isSuperAdmin() ? (
                        <div className="flex flex-col items-center justify-center min-h-[40vh] text-center bg-dark-800/50 rounded-2xl border border-white/5">
                            <Shield className="w-16 h-16 text-dark-500 mb-4" />
                            <h2 className="text-xl font-bold text-white mb-2">접근 권한이 없습니다</h2>
                            <p className="text-dark-300">시스템 설정은 최상위 관리자(Super Admin)만 접근 가능합니다.</p>
                        </div>
                    ) : isLoading ? (
                        <div className="text-center py-12 text-dark-400">설정 불러오는 중...</div>
                    ) : !hasConfigs ? (
                        <div className="flex flex-col items-center justify-center min-h-[40vh] text-center bg-dark-800/50 rounded-2xl border border-white/5 p-8">
                            <Database className="w-16 h-16 text-dark-500 mb-4" />
                            <h2 className="text-xl font-bold text-white mb-2">설정이 초기화되지 않았습니다</h2>
                            <p className="text-dark-300 mb-6">기본 시스템 설정을 초기화해주세요.</p>
                            <button
                                onClick={() => initMutation.mutate()}
                                disabled={initMutation.isPending}
                                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium rounded-xl hover:shadow-neon transition-all disabled:opacity-50"
                            >
                                <Settings className="w-5 h-5" />
                                {initMutation.isPending ? '초기화 중...' : '기본 설정 초기화'}
                            </button>
                            {initMutation.isSuccess && (
                                <p className="mt-4 text-accent-success">✓ 설정이 초기화되었습니다.</p>
                            )}
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 gap-6">
                            {sections.map((section) => {
                                const configs = configData?.data?.configs?.[section.id] || [];
                                if (configs.length === 0) return null;

                                return (
                                    <motion.div
                                        key={section.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="bg-dark-800/50 backdrop-blur-xl border border-white/5 rounded-2xl p-6"
                                    >
                                        <div className="flex items-center gap-3 mb-2">
                                            <div className="w-10 h-10 rounded-xl bg-dark-700 flex items-center justify-center border border-white/5">
                                                <section.icon className="w-5 h-5 text-accent-primary" />
                                            </div>
                                            <div>
                                                <h2 className="text-lg font-bold text-white">{section.title}</h2>
                                                <p className="text-sm text-dark-400">{section.description}</p>
                                            </div>
                                        </div>

                                        <div className="space-y-4 mt-4">
                                            {configs.map((config: any) => (
                                                <div
                                                    key={config.key}
                                                    className={`group p-4 rounded-xl border transition-colors ${
                                                        config.cli_only
                                                            ? 'bg-dark-900/20 border-amber-500/20'
                                                            : 'bg-dark-900/30 border-white/5 hover:border-white/10'
                                                    }`}
                                                >
                                                    <div className="flex items-center justify-between mb-2">
                                                        <div className="flex items-center gap-2">
                                                            {config.cli_only && (
                                                                <Lock className="w-3.5 h-3.5 text-amber-500" />
                                                            )}
                                                            <label className={`text-sm font-medium ${config.cli_only ? 'text-amber-400' : 'text-dark-200'}`}>
                                                                {config.description || config.key}
                                                            </label>
                                                            {config.cli_only && (
                                                                <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded">
                                                                    CLI 전용
                                                                </span>
                                                            )}
                                                        </div>
                                                        <span className="text-xs text-dark-500 font-mono">{config.key}</span>
                                                    </div>

                                                    <div className="flex gap-3">
                                                        {editingKey === config.key && !config.cli_only ? (
                                                            <>
                                                                <input
                                                                    type="text"
                                                                    value={editValue}
                                                                    onChange={(e) => setEditValue(e.target.value)}
                                                                    className="flex-1 bg-dark-800 border border-accent-primary/50 text-white text-sm rounded-lg px-3 py-2 outline-none"
                                                                    autoFocus
                                                                />
                                                                <button
                                                                    onClick={() => handleSave(config.key)}
                                                                    disabled={updateMutation.isPending}
                                                                    className="px-3 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/90 transition-colors"
                                                                >
                                                                    <Save className="w-4 h-4" />
                                                                </button>
                                                                <button
                                                                    onClick={() => setEditingKey(null)}
                                                                    className="px-3 py-2 bg-dark-700 text-dark-300 rounded-lg hover:bg-dark-600 transition-colors"
                                                                >
                                                                    취소
                                                                </button>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <div className={`flex-1 text-sm font-mono px-3 py-2 rounded-lg border border-transparent transition-colors truncate ${
                                                                    config.cli_only
                                                                        ? 'bg-dark-950/20 text-dark-400'
                                                                        : 'bg-dark-950/30 text-white group-hover:border-white/5'
                                                                }`}>
                                                                    {config.value}
                                                                </div>
                                                                {config.cli_only ? (
                                                                    <div className="px-3 py-2 text-dark-500 flex items-center gap-1.5 text-sm">
                                                                        <Terminal className="w-3.5 h-3.5" />
                                                                        서버 CLI
                                                                    </div>
                                                                ) : (
                                                                    <button
                                                                        onClick={() => handleEdit(config.key, config.value)}
                                                                        className="px-3 py-2 text-dark-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                                                                    >
                                                                        수정
                                                                    </button>
                                                                )}
                                                            </>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </motion.div>
                                );
                            })}

                            {/* CLI Info */}
                            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-start gap-3">
                                <Terminal className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-amber-400 font-medium">CLI 전용 설정 안내</p>
                                    <p className="text-dark-300 text-sm mt-1">
                                        <Lock className="w-3 h-3 inline mr-1" />표시된 설정은 보안상 서버 CLI에서만 변경 가능합니다.
                                    </p>
                                    <code className="block mt-2 text-xs bg-dark-900 text-dark-300 px-3 py-2 rounded-lg font-mono">
                                        python scripts/admin_cli.py
                                    </code>
                                </div>
                            </div>

                            {/* Fee Info */}
                            <div className="p-4 rounded-xl bg-accent-info/10 border border-accent-info/20 flex items-start gap-3">
                                <AlertCircle className="w-5 h-5 text-accent-info flex-shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-accent-info font-medium">수수료율 설정 안내</p>
                                    <p className="text-dark-300 text-sm mt-1">
                                        수수료율은 <code className="bg-dark-800 px-1 rounded">default_fee_rate</code>에서 설정할 수 있습니다.
                                        값 100 = 1%, 50 = 0.5%, 200 = 2% 입니다.
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
