'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowDownCircle,
  ArrowUpCircle,
  ExternalLink,
  Copy,
  Check,
  RefreshCw,
} from 'lucide-react';
import { GlassCard, Badge, EmptyState } from '@/components/ui/Card';
import { cn, formatUsdt, shortenAddress, timeAgo, getTronscanUrl, copyToClipboard } from '@/lib/utils';
import { dashboardApi } from '@/lib/api';
import type { Transaction } from '@/types';

interface LiveTransactionTableProps {
  initialData?: Transaction[];
  autoRefresh?: boolean;
  refreshInterval?: number;
  maxItems?: number;
}

export function LiveTransactionTable({
  initialData = [],
  autoRefresh = true,
  refreshInterval = 30000,
  maxItems = 20,
}: LiveTransactionTableProps) {
  const [transactions, setTransactions] = useState<Transaction[]>(initialData);
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchTransactions = async () => {
    try {
      setIsLoading(true);
      const response = await dashboardApi.getRecentTransactions(maxItems);
      setTransactions(response.data.transactions);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to fetch transactions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (initialData.length === 0) {
      fetchTransactions();
    }

    if (autoRefresh) {
      const interval = setInterval(fetchTransactions, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval, maxItems]);

  const handleCopy = async (text: string, id: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
      confirmed: 'success',
      completed: 'success',
      swept: 'info',
      pending: 'warning',
      processing: 'warning',
      failed: 'danger',
    };
    return variants[status] || 'info';
  };

  return (
    <GlassCard className="overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold text-white">실시간 트랜잭션</h3>
          <div className="flex items-center gap-2">
            <span className="live-dot" />
            <span className="text-xs text-dark-300">Live</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-dark-400">
            마지막 업데이트: {timeAgo(lastUpdated.toISOString())}
          </span>
          <button
            onClick={fetchTransactions}
            disabled={isLoading}
            className="p-2 rounded-lg hover:bg-white/5 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('w-4 h-4 text-dark-300', isLoading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-dark-300">
              <th className="pb-3 font-medium">유형</th>
              <th className="pb-3 font-medium">사용자</th>
              <th className="pb-3 font-medium">금액</th>
              <th className="pb-3 font-medium">주소</th>
              <th className="pb-3 font-medium">상태</th>
              <th className="pb-3 font-medium">시간</th>
              <th className="pb-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence mode="popLayout">
              {transactions.map((tx, index) => (
                <motion.tr
                  key={tx.id}
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  transition={{ delay: index * 0.05 }}
                  className="border-t border-white/5 hover:bg-white/5"
                >
                  {/* Type */}
                  <td className="py-4">
                    <div className="flex items-center gap-2">
                      {tx.type === 'deposit' ? (
                        <ArrowDownCircle className="w-5 h-5 text-accent-success" />
                      ) : (
                        <ArrowUpCircle className="w-5 h-5 text-accent-danger" />
                      )}
                      <span className={tx.type === 'deposit' ? 'text-accent-success' : 'text-accent-danger'}>
                        {tx.type === 'deposit' ? '입금' : '출금'}
                      </span>
                    </div>
                  </td>

                  {/* User ID */}
                  <td className="py-4">
                    <span className="text-white font-mono">#{tx.user_id}</span>
                  </td>

                  {/* Amount */}
                  <td className="py-4">
                    <span className="text-white font-medium">
                      {formatUsdt(tx.amount)} USDT
                    </span>
                  </td>

                  {/* Address */}
                  <td className="py-4">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-dark-200">
                        {shortenAddress(tx.from_address || tx.to_address || '', 6)}
                      </span>
                      <button
                        onClick={() => handleCopy(tx.from_address || tx.to_address || '', tx.id)}
                        className="p-1 rounded hover:bg-white/10 transition-colors"
                      >
                        {copiedId === tx.id ? (
                          <Check className="w-3 h-3 text-accent-success" />
                        ) : (
                          <Copy className="w-3 h-3 text-dark-400" />
                        )}
                      </button>
                    </div>
                  </td>

                  {/* Status */}
                  <td className="py-4">
                    <Badge variant={getStatusBadge(tx.status)}>
                      {tx.status}
                    </Badge>
                  </td>

                  {/* Time */}
                  <td className="py-4">
                    <span className="text-dark-300 text-xs">
                      {timeAgo(tx.created_at)}
                    </span>
                  </td>

                  {/* Actions */}
                  <td className="py-4">
                    {tx.tx_id && (
                      <a
                        href={getTronscanUrl(tx.tx_id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1 rounded hover:bg-white/10 transition-colors inline-flex"
                      >
                        <ExternalLink className="w-4 h-4 text-dark-400 hover:text-accent-primary" />
                      </a>
                    )}
                  </td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>

        {transactions.length === 0 && !isLoading && (
          <EmptyState
            title="트랜잭션이 없습니다"
            description="아직 입출금 내역이 없습니다."
          />
        )}
      </div>
    </GlassCard>
  );
}
