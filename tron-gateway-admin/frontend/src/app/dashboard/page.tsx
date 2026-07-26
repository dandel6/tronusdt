'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  ArrowDownCircle,
  ArrowUpCircle,
  Wallet,
  TrendingUp,
  Activity,
  Clock,
  AlertTriangle,
  DollarSign,
} from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { StatCard, GlassCard, Skeleton } from '@/components/ui/Card';
import { TransactionChart, VolumeChart, WalletInfoCard } from '@/components/dashboard/Charts';
import { LiveTransactionTable } from '@/components/dashboard/LiveTransactionTable';
import { dashboardApi } from '@/lib/api';
import { formatUsdt, formatCompactNumber } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';
import type { DashboardStats, ChartDataPoint } from '@/types';

export default function DashboardPage() {
  const { admin } = useAuthStore();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, chartRes] = await Promise.all([
          dashboardApi.getStats(),
          dashboardApi.getChartData(7),
        ]);
        setStats(statsRes.data);
        setChartData(chartRes.data.data);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 60000); // 1분마다 갱신
    return () => clearInterval(interval);
  }, []);

  const isSuperAdmin = admin?.role === 'super_admin';

  return (
    <div className="min-h-screen bg-dark-900">
      <Sidebar />

      <main className="lg:ml-[280px] min-h-screen">
        <Header title="대시보드" />

        <div className="p-6 space-y-6">
          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
            {isLoading ? (
              <>
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-32" />
                ))}
              </>
            ) : (
              <>
                <StatCard
                  title="총 사용자"
                  value={formatCompactNumber(stats?.total_users || 0)}
                  icon={<Users className="w-5 h-5" />}
                  variant="primary"
                />
                <StatCard
                  title="오늘 입금"
                  value={`${formatUsdt(stats?.today?.deposits?.amount || 0)}`}
                  subtitle={`${stats?.today?.deposits?.count || 0}건`}
                  icon={<ArrowDownCircle className="w-5 h-5" />}
                  variant="success"
                />
                <StatCard
                  title="오늘 출금"
                  value={`${formatUsdt(stats?.today?.withdrawals?.amount || 0)}`}
                  subtitle={`${stats?.today?.withdrawals?.count || 0}건`}
                  icon={<ArrowUpCircle className="w-5 h-5" />}
                  variant="danger"
                />
                <StatCard
                  title="대기 출금"
                  value={`${formatUsdt(stats?.pending_withdrawals?.amount || 0)}`}
                  subtitle={`${stats?.pending_withdrawals?.count || 0}건 대기 중`}
                  icon={<Clock className="w-5 h-5" />}
                  variant="warning"
                />
                <StatCard
                  title="총 수수료"
                  value={`${formatUsdt(stats?.total_fees?.amount || 0)}`}
                  subtitle={`오늘: ${formatUsdt(stats?.total_fees?.today_amount || 0)}`}
                  icon={<DollarSign className="w-5 h-5" />}
                  variant="primary"
                />
              </>
            )}
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              {isLoading ? (
                <Skeleton className="h-96" />
              ) : (
                <TransactionChart data={chartData} />
              )}
            </div>
            <div>
              {isLoading ? (
                <Skeleton className="h-96" />
              ) : isSuperAdmin && stats?.main_wallet ? (
                <WalletInfoCard
                  address={stats.main_wallet.address}
                  usdtBalance={stats.main_wallet.usdt_balance}
                  trxBalance={stats.main_wallet.trx_balance}
                  energyAvailable={stats.main_wallet.energy_available}
                />
              ) : (
                <GlassCard className="h-full">
                  <h3 className="text-lg font-semibold text-white mb-6">총 통계</h3>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center p-4 bg-dark-700/50 rounded-xl">
                      <span className="text-dark-300">총 입금</span>
                      <span className="text-white font-bold">
                        {formatUsdt(stats?.total_deposits.amount || 0)} USDT
                      </span>
                    </div>
                    <div className="flex justify-between items-center p-4 bg-dark-700/50 rounded-xl">
                      <span className="text-dark-300">총 출금</span>
                      <span className="text-white font-bold">
                        {formatUsdt(stats?.total_withdrawals.amount || 0)} USDT
                      </span>
                    </div>
                    <div className="flex justify-between items-center p-4 bg-dark-700/50 rounded-xl">
                      <span className="text-dark-300">미스윕 입금</span>
                      <span className="text-accent-warning font-bold">
                        {formatUsdt(stats?.unswept_deposits.amount || 0)} USDT
                      </span>
                    </div>
                  </div>
                </GlassCard>
              )}
            </div>
          </div>

          {/* Alert Banner (Super Admin Only) */}
          {isSuperAdmin && stats?.pending_withdrawals.count && stats.pending_withdrawals.count > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-4 p-4 rounded-xl bg-accent-warning/10 border border-accent-warning/20"
            >
              <AlertTriangle className="w-6 h-6 text-accent-warning flex-shrink-0" />
              <div>
                <p className="text-white font-medium">대기 중인 출금 요청이 있습니다</p>
                <p className="text-dark-300 text-sm">
                  {stats.pending_withdrawals.count}건의 출금 요청이 승인 대기 중입니다.
                  총 {formatUsdt(stats.pending_withdrawals.amount)} USDT
                </p>
              </div>
              <a
                href="/withdrawals?status=pending"
                className="ml-auto px-4 py-2 rounded-lg bg-accent-warning text-dark-900 font-medium hover:bg-accent-warning/90 transition-colors"
              >
                확인하기
              </a>
            </motion.div>
          )}

          {/* Live Transactions */}
          <LiveTransactionTable autoRefresh={true} refreshInterval={30000} maxItems={20} />

          {/* Volume Chart */}
          {isLoading ? (
            <Skeleton className="h-72" />
          ) : (
            <VolumeChart data={chartData} />
          )}
        </div>
      </main>
    </div>
  );
}
