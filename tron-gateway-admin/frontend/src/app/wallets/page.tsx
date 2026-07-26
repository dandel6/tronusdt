'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Wallet,
  Search,
  ExternalLink,
  Copy,
  Check,
  RefreshCw,
  Plus,
  Eye,
  X,
} from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { GlassCard, DataTable, Badge, Skeleton, EmptyState } from '@/components/ui/Card';
import { dashboardApi, walletApi } from '@/lib/api';
import {
  cn,
  formatUsdt,
  shortenAddress,
  formatDate,
  copyToClipboard,
  getTronscanAddressUrl,
} from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';
import type { Wallet as WalletType } from '@/types';

export default function WalletsPage() {
  const { admin } = useAuthStore();
  const [wallets, setWallets] = useState<WalletType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [isCreating, setIsCreating] = useState(false);

  const canCreateWallet = admin?.permissions?.includes('create_wallet') || admin?.role === 'super_admin';

  useEffect(() => {
    fetchWallets();
  }, [page]);

  const fetchWallets = async () => {
    try {
      setIsLoading(true);
      const response = await dashboardApi.getWallets({ page, limit: 20 });
      setWallets(response.data.wallets || []);
    } catch (error) {
      console.error('Failed to fetch wallets:', error);
      setWallets([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateWallet = async () => {
    try {
      setIsCreating(true);
      // Auto-generate next user_id based on current wallet count
      const nextUserId = wallets.length > 0
        ? Math.max(...wallets.map(w => w.user_id)) + 1
        : 1001;
      await walletApi.create(nextUserId);
      fetchWallets();
    } catch (error: any) {
      alert(error.response?.data?.detail || '지갑 생성에 실패했습니다.');
    } finally {
      setIsCreating(false);
    }
  };


  const handleCopy = async (text: string, id: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const filteredWallets = wallets.filter(
    (w) =>
      w.user_id.toString().includes(searchQuery) ||
      w.wallet_address.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-dark-900">
      <Sidebar />

      <main className="lg:ml-[280px] min-h-screen">
        <Header title="지갑 관리" />

        <div className="p-6 space-y-6">
          {/* Header Actions */}
          <div className="flex flex-col sm:flex-row gap-4 justify-between">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
              <input
                type="text"
                placeholder="사용자 ID 또는 주소 검색..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="glass-input w-full pl-12"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={fetchWallets}
                className="glass-button flex items-center gap-2"
              >
                <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
                새로고침
              </button>
              {canCreateWallet && (
                <button
                  onClick={handleCreateWallet}
                  disabled={isCreating}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-accent-primary to-accent-secondary font-medium hover:shadow-neon transition-all disabled:opacity-50"
                >
                  <Plus className={cn('w-4 h-4', isCreating && 'animate-spin')} />
                  {isCreating ? '생성 중...' : '지갑 생성'}
                </button>
              )}
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <GlassCard className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-accent-primary/20">
                  <Wallet className="w-5 h-5 text-accent-primary" />
                </div>
                <div>
                  <p className="text-dark-300 text-sm">총 지갑 수</p>
                  <p className="text-xl font-bold text-white">{wallets.length}</p>
                </div>
              </div>
            </GlassCard>
            <GlassCard className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-accent-success/20">
                  <Wallet className="w-5 h-5 text-accent-success" />
                </div>
                <div>
                  <p className="text-dark-300 text-sm">총 잔액</p>
                  <p className="text-xl font-bold text-white">
                    {formatUsdt(wallets.reduce((sum, w) => sum + (w.balance || 0), 0))} USDT
                  </p>
                </div>
              </div>
            </GlassCard>
            <GlassCard className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-accent-warning/20">
                  <Wallet className="w-5 h-5 text-accent-warning" />
                </div>
                <div>
                  <p className="text-dark-300 text-sm">잔액 있는 지갑</p>
                  <p className="text-xl font-bold text-white">
                    {wallets.filter((w) => (w.balance || 0) > 0).length}
                  </p>
                </div>
              </div>
            </GlassCard>
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <th>사용자 ID</th>
                  <th>지갑 주소</th>
                  <th>잔액</th>
                  <th>생성일</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredWallets.map((wallet, index) => (
                  <motion.tr
                    key={wallet.user_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <td>
                      <span className="font-mono text-white">#{wallet.user_id}</span>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-dark-200">
                          {shortenAddress(wallet.wallet_address, 8)}
                        </span>
                        <button
                          onClick={() =>
                            handleCopy(wallet.wallet_address, wallet.user_id.toString())
                          }
                          className="p-1 rounded hover:bg-white/10"
                        >
                          {copiedId === wallet.user_id.toString() ? (
                            <Check className="w-4 h-4 text-accent-success" />
                          ) : (
                            <Copy className="w-4 h-4 text-dark-400" />
                          )}
                        </button>
                        <a
                          href={getTronscanAddressUrl(wallet.wallet_address)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 rounded hover:bg-white/10"
                        >
                          <ExternalLink className="w-4 h-4 text-dark-400 hover:text-accent-primary" />
                        </a>
                      </div>
                    </td>
                    <td>
                      <span
                        className={cn(
                          'font-medium',
                          (wallet.balance || 0) > 0 ? 'text-accent-success' : 'text-dark-300'
                        )}
                      >
                        {formatUsdt(wallet.balance || 0)} USDT
                      </span>
                    </td>
                    <td>
                      <span className="text-dark-300 text-sm">
                        {formatDate(wallet.created_at, 'short')}
                      </span>
                    </td>
                    <td>
                      <a
                        href={`/wallets/${wallet.user_id}`}
                        className="p-2 rounded-lg hover:bg-white/10 inline-flex"
                      >
                        <Eye className="w-4 h-4 text-dark-400 hover:text-white" />
                      </a>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </DataTable>
          )}

          {!isLoading && filteredWallets.length === 0 && (
            <EmptyState
              icon={<Wallet className="w-12 h-12" />}
              title="지갑이 없습니다"
              description="검색 조건에 맞는 지갑이 없습니다."
            />
          )}

          {/* Pagination */}
          <div className="flex justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="glass-button disabled:opacity-50"
            >
              이전
            </button>
            <span className="glass-button">{page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={wallets.length < 20}
              className="glass-button disabled:opacity-50"
            >
              다음
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
