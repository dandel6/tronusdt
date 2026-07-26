'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Building2,
  Plus,
  Search,
  MoreVertical,
  Edit,
  Trash2,
  Key,
  Users,
  X,
  Check,
  AlertCircle,
} from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { GlassCard, Badge, Skeleton, EmptyState } from '@/components/ui/Card';
import { partnerApi } from '@/lib/api';
import { cn, formatDate, formatUsdt } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';
import type { Partner } from '@/types';

export default function PartnersPage() {
  const { admin } = useAuthStore();
  const [partners, setPartners] = useState<Partner[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedPartner, setSelectedPartner] = useState<Partner | null>(null);
  const [apiSecret, setApiSecret] = useState<string | null>(null);

  // Super Admin 체크
  if (admin?.role !== 'super_admin') {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center">
        <GlassCard className="max-w-md text-center">
          <AlertCircle className="w-12 h-12 text-accent-danger mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">접근 권한 없음</h2>
          <p className="text-dark-300">이 페이지는 최상위 관리자만 접근할 수 있습니다.</p>
        </GlassCard>
      </div>
    );
  }

  useEffect(() => {
    fetchPartners();
  }, []);

  const fetchPartners = async () => {
    try {
      setIsLoading(true);
      const response = await partnerApi.list();
      setPartners(response.data.partners);
    } catch (error) {
      console.error('Failed to fetch partners:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegenerateSecret = async (partnerId: number) => {
    if (!confirm('API Secret을 재발급하시겠습니까? 기존 시크릿은 더 이상 사용할 수 없습니다.')) {
      return;
    }

    try {
      const response = await partnerApi.regenerateSecret(partnerId);
      setApiSecret(response.data.api_secret);
    } catch (error) {
      console.error('Failed to regenerate secret:', error);
      alert('API Secret 재발급에 실패했습니다.');
    }
  };

  const handleToggleActive = async (partner: Partner) => {
    try {
      await partnerApi.update(partner.partner_id, { is_active: !partner.is_active });
      fetchPartners();
    } catch (error) {
      console.error('Failed to update partner:', error);
    }
  };

  const filteredPartners = partners.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-dark-900">
      <Sidebar />

      <main className="lg:ml-[280px] min-h-screen">
        <Header title="파트너 관리" />

        <div className="p-6 space-y-6">
          {/* Header Actions */}
          <div className="flex flex-col sm:flex-row gap-4 justify-between">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
              <input
                type="text"
                placeholder="파트너 이름 또는 코드 검색..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="glass-input w-full pl-12"
              />
            </div>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary font-medium hover:shadow-neon transition-all"
            >
              <Plus className="w-4 h-4" />
              파트너 추가
            </button>
          </div>

          {/* Partners Grid */}
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-64" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredPartners.map((partner, index) => (
                <motion.div
                  key={partner.partner_id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  <GlassCard hover className="h-full">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent-primary/20 to-accent-secondary/20 flex items-center justify-center">
                          <Building2 className="w-6 h-6 text-accent-primary" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-white">{partner.name}</h3>
                          <p className="text-dark-400 text-sm font-mono">{partner.code}</p>
                        </div>
                      </div>
                      <Badge variant={partner.is_active ? 'success' : 'danger'}>
                        {partner.is_active ? '활성' : '비활성'}
                      </Badge>
                    </div>

                    <div className="space-y-3 mb-4">
                      <div className="flex justify-between text-sm">
                        <span className="text-dark-300">수수료율</span>
                        <span className="text-white">{(partner.fee_rate / 100).toFixed(2)}%</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-dark-300">일일 출금 한도</span>
                        <span className="text-white">
                          {formatUsdt(partner.daily_withdrawal_limit / 1_000_000)} USDT
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-dark-300">관리자 수</span>
                        <span className="text-white">{partner.admin_count || 0}명</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-dark-300">생성일</span>
                        <span className="text-dark-200">{formatDate(partner.created_at, 'short')}</span>
                      </div>
                    </div>

                    <div className="flex gap-2 pt-4 border-t border-white/5">
                      <button
                        onClick={() => setSelectedPartner(partner)}
                        className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg bg-dark-700/50 hover:bg-dark-600/50 text-dark-200 hover:text-white transition-colors"
                      >
                        <Edit className="w-4 h-4" />
                        수정
                      </button>
                      <button
                        onClick={() => handleRegenerateSecret(partner.partner_id)}
                        className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg bg-dark-700/50 hover:bg-dark-600/50 text-dark-200 hover:text-white transition-colors"
                      >
                        <Key className="w-4 h-4" />
                        키 재발급
                      </button>
                      <button
                        onClick={() => handleToggleActive(partner)}
                        className={cn(
                          'p-2 rounded-lg transition-colors',
                          partner.is_active
                            ? 'bg-accent-danger/20 text-accent-danger hover:bg-accent-danger/30'
                            : 'bg-accent-success/20 text-accent-success hover:bg-accent-success/30'
                        )}
                      >
                        {partner.is_active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                      </button>
                    </div>
                  </GlassCard>
                </motion.div>
              ))}
            </div>
          )}

          {!isLoading && filteredPartners.length === 0 && (
            <EmptyState
              icon={<Building2 className="w-12 h-12" />}
              title="파트너가 없습니다"
              description="새 파트너를 추가해주세요."
              action={
                <button
                  onClick={() => setIsCreateModalOpen(true)}
                  className="px-4 py-2 rounded-xl bg-accent-primary text-white"
                >
                  파트너 추가
                </button>
              }
            />
          )}
        </div>

        {/* API Secret Modal */}
        <AnimatePresence>
          {apiSecret && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
              onClick={() => setApiSecret(null)}
            >
              <motion.div
                initial={{ scale: 0.95 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0.95 }}
                className="glass-card max-w-md w-full"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 rounded-xl bg-accent-warning/20">
                    <Key className="w-6 h-6 text-accent-warning" />
                  </div>
                  <h3 className="text-lg font-semibold text-white">새 API Secret</h3>
                </div>
                <p className="text-dark-300 text-sm mb-4">
                  아래 API Secret을 안전하게 보관하세요. 이 창을 닫으면 다시 확인할 수 없습니다.
                </p>
                <div className="bg-dark-700/50 rounded-xl p-4 font-mono text-sm text-white break-all mb-4">
                  {apiSecret}
                </div>
                <button
                  onClick={() => setApiSecret(null)}
                  className="w-full py-2 rounded-xl bg-accent-primary text-white font-medium"
                >
                  확인
                </button>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Create Partner Modal */}
        <CreatePartnerModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onSuccess={() => {
            fetchPartners();
            setIsCreateModalOpen(false);
          }}
        />
      </main>
    </div>
  );
}

// 파트너 생성 모달
function CreatePartnerModal({
  isOpen,
  onClose,
  onSuccess,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    description: '',
    fee_rate: 100,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<{ api_key: string; api_secret: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const response = await partnerApi.create(formData);
      setResult({
        api_key: response.data.api_key,
        api_secret: response.data.api_secret,
      });
    } catch (error: any) {
      alert(error.response?.data?.detail || '파트너 생성에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    if (result) {
      onSuccess();
    }
    setFormData({ name: '', code: '', description: '', fee_rate: 100 });
    setResult(null);
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={handleClose}
        >
          <motion.div
            initial={{ scale: 0.95 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0.95 }}
            className="glass-card max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-white">
                {result ? '파트너 생성 완료' : '새 파트너 추가'}
              </h3>
              <button onClick={handleClose} className="text-dark-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            {result ? (
              <div className="space-y-4">
                <p className="text-dark-300 text-sm">
                  파트너가 생성되었습니다. 아래 API 키와 시크릿을 안전하게 보관하세요.
                </p>
                <div>
                  <label className="text-dark-300 text-sm">API Key</label>
                  <div className="bg-dark-700/50 rounded-xl p-3 font-mono text-sm text-white break-all">
                    {result.api_key}
                  </div>
                </div>
                <div>
                  <label className="text-dark-300 text-sm">API Secret</label>
                  <div className="bg-dark-700/50 rounded-xl p-3 font-mono text-sm text-white break-all">
                    {result.api_secret}
                  </div>
                </div>
                <button
                  onClick={handleClose}
                  className="w-full py-2 rounded-xl bg-accent-primary text-white font-medium"
                >
                  확인
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-dark-200 text-sm mb-2">파트너명</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="glass-input w-full"
                    required
                  />
                </div>
                <div>
                  <label className="block text-dark-200 text-sm mb-2">코드 (영문)</label>
                  <input
                    type="text"
                    value={formData.code}
                    onChange={(e) =>
                      setFormData({ ...formData, code: e.target.value.toUpperCase() })
                    }
                    className="glass-input w-full font-mono"
                    pattern="[A-Z0-9]+"
                    maxLength={20}
                    required
                  />
                </div>
                <div>
                  <label className="block text-dark-200 text-sm mb-2">설명</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="glass-input w-full resize-none"
                    rows={3}
                  />
                </div>
                <div>
                  <label className="block text-dark-200 text-sm mb-2">
                    수수료율 ({(formData.fee_rate / 100).toFixed(2)}%)
                  </label>
                  <input
                    type="range"
                    value={formData.fee_rate}
                    onChange={(e) =>
                      setFormData({ ...formData, fee_rate: parseInt(e.target.value) })
                    }
                    min={0}
                    max={2000}
                    step={10}
                    className="w-full"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-2 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium disabled:opacity-50"
                >
                  {isLoading ? '생성 중...' : '파트너 생성'}
                </button>
              </form>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
