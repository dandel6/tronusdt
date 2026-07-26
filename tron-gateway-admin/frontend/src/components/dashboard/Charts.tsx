'use client';

import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { GlassCard } from '@/components/ui/Card';
import { formatUsdt, formatCompactNumber } from '@/lib/utils';
import type { ChartDataPoint } from '@/types';

interface TransactionChartProps {
  data: ChartDataPoint[];
  className?: string;
}

// 커스텀 툴팁
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload) return null;

  return (
    <div className="glass-card p-3 text-sm">
      <p className="text-dark-200 mb-2">{label}</p>
      {payload.map((entry: any, index: number) => (
        <div key={index} className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-dark-300">{entry.name}:</span>
          <span className="text-white font-medium">
            {formatUsdt(entry.value)} USDT
          </span>
        </div>
      ))}
    </div>
  );
};

// 트랜잭션 차트 (영역 차트)
export function TransactionChart({ data, className }: TransactionChartProps) {
  const chartData = useMemo(
    () =>
      data.map((d) => ({
        date: new Date(d.date).toLocaleDateString('ko-KR', {
          month: 'short',
          day: 'numeric',
        }),
        입금: d.deposits.amount,
        출금: d.withdrawals.amount,
      })),
    [data]
  );

  return (
    <GlassCard className={className}>
      <h3 className="text-lg font-semibold text-white mb-6">입출금 추이</h3>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="depositGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="withdrawalGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#8a8a9a', fontSize: 12 }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#8a8a9a', fontSize: 12 }}
              tickFormatter={(value) => formatCompactNumber(value)}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="입금"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#depositGradient)"
            />
            <Area
              type="monotone"
              dataKey="출금"
              stroke="#ef4444"
              strokeWidth={2}
              fill="url(#withdrawalGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </GlassCard>
  );
}

// 볼륨 바 차트
export function VolumeChart({ data, className }: TransactionChartProps) {
  const chartData = useMemo(
    () =>
      data.map((d) => ({
        date: new Date(d.date).toLocaleDateString('ko-KR', {
          month: 'short',
          day: 'numeric',
        }),
        입금건수: d.deposits.count,
        출금건수: d.withdrawals.count,
      })),
    [data]
  );

  return (
    <GlassCard className={className}>
      <h3 className="text-lg font-semibold text-white mb-6">거래 건수</h3>
      <div className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#8a8a9a', fontSize: 12 }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#8a8a9a', fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                background: 'rgba(26, 26, 36, 0.95)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '12px',
              }}
            />
            <Bar dataKey="입금건수" fill="#10b981" radius={[4, 4, 0, 0]} />
            <Bar dataKey="출금건수" fill="#ef4444" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </GlassCard>
  );
}

// 도넛 차트 (상태별 분포)
interface StatusDistributionProps {
  data: { name: string; value: number; color: string }[];
  title: string;
  className?: string;
}

export function StatusDistribution({ data, title, className }: StatusDistributionProps) {
  const total = useMemo(() => data.reduce((sum, d) => sum + d.value, 0), [data]);

  return (
    <GlassCard className={className}>
      <h3 className="text-lg font-semibold text-white mb-6">{title}</h3>
      <div className="flex items-center gap-6">
        <div className="w-40 h-40">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={70}
                paddingAngle={2}
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 space-y-3">
          {data.map((item, index) => (
            <div key={index} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-dark-200 text-sm">{item.name}</span>
              </div>
              <div className="text-right">
                <span className="text-white font-medium">{item.value}</span>
                <span className="text-dark-400 text-xs ml-1">
                  ({total > 0 ? ((item.value / total) * 100).toFixed(1) : 0}%)
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </GlassCard>
  );
}

// 메인 월렛 정보 카드
interface WalletInfoCardProps {
  address: string;
  usdtBalance: number;
  trxBalance: number;
  energyAvailable: number;
  className?: string;
}

export function WalletInfoCard({
  address,
  usdtBalance,
  trxBalance,
  energyAvailable,
  className,
}: WalletInfoCardProps) {
  return (
    <GlassCard className={className}>
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-white">메인 월렛</h3>
        <span className="badge-success">Active</span>
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-dark-300 text-sm mb-1">주소</p>
          <p className="font-mono text-white text-sm break-all">{address}</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-dark-700/50 rounded-xl p-4">
            <p className="text-dark-300 text-sm">USDT</p>
            <p className="text-2xl font-bold text-white">
              {formatUsdt(usdtBalance)}
            </p>
          </div>
          <div className="bg-dark-700/50 rounded-xl p-4">
            <p className="text-dark-300 text-sm">TRX</p>
            <p className="text-2xl font-bold text-white">
              {formatUsdt(trxBalance, 0)}
            </p>
          </div>
        </div>

        <div className="bg-dark-700/50 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <p className="text-dark-300 text-sm">에너지</p>
            <p className="text-white font-medium">{formatCompactNumber(energyAvailable)}</p>
          </div>
          <div className="mt-2 h-2 bg-dark-600 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-accent-primary to-accent-secondary rounded-full"
              style={{ width: `${Math.min((energyAvailable / 100000) * 100, 100)}%` }}
            />
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
