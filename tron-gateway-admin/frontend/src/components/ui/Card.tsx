'use client';

import { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  animate?: boolean;
  onClick?: () => void;
}

export function GlassCard({
  children,
  className,
  hover = false,
  animate = false,
  onClick,
}: GlassCardProps) {
  const baseClasses = cn(
    'glass-card',
    hover && 'cursor-pointer transition-all duration-300 hover:bg-white/10 hover:shadow-neon',
    className
  );

  if (animate) {
    return (
      <motion.div
        className={baseClasses}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        onClick={onClick}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <div className={baseClasses} onClick={onClick}>
      {children}
    </div>
  );
}

// 통계 카드
interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  variant?: 'primary' | 'success' | 'warning' | 'danger';
  className?: string;
}

export function StatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  variant = 'primary',
  className,
}: StatCardProps) {
  const variantColors = {
    primary: 'from-accent-primary/20 to-accent-primary/5',
    success: 'from-accent-success/20 to-accent-success/5',
    warning: 'from-accent-warning/20 to-accent-warning/5',
    danger: 'from-accent-danger/20 to-accent-danger/5',
  };

  return (
    <motion.div
      className={cn('stat-card', variant, className)}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className={`absolute inset-0 bg-gradient-to-br ${variantColors[variant]} rounded-2xl`} />
      
      <div className="relative">
        <div className="flex items-center justify-between mb-4">
          <span className="text-dark-200 text-sm font-medium">{title}</span>
          {icon && <div className="text-dark-300">{icon}</div>}
        </div>
        
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-white number-counter">{value}</span>
          {trend && (
            <span
              className={cn(
                'text-sm font-medium',
                trend.isPositive ? 'text-accent-success' : 'text-accent-danger'
              )}
            >
              {trend.isPositive ? '+' : ''}{trend.value.toFixed(1)}%
            </span>
          )}
        </div>
        
        {subtitle && (
          <p className="text-dark-300 text-sm mt-1">{subtitle}</p>
        )}
      </div>
    </motion.div>
  );
}

// 데이터 테이블 래퍼
interface DataTableProps {
  children: ReactNode;
  className?: string;
}

export function DataTable({ children, className }: DataTableProps) {
  return (
    <GlassCard className={cn('overflow-hidden p-0', className)}>
      <div className="overflow-x-auto custom-scrollbar">
        <table className="data-table">
          {children}
        </table>
      </div>
    </GlassCard>
  );
}

// 빈 상태
interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && <div className="text-dark-400 mb-4">{icon}</div>}
      <h3 className="text-lg font-medium text-white mb-2">{title}</h3>
      {description && <p className="text-dark-300 mb-4">{description}</p>}
      {action}
    </div>
  );
}

// 로딩 스켈레톤
export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn('animate-shimmer rounded-lg bg-dark-700', className)} />
  );
}

// 배지
interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  className?: string;
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  const variants = {
    default: 'bg-dark-500/50 text-dark-100',
    success: 'badge-success',
    warning: 'badge-warning',
    danger: 'badge-danger',
    info: 'badge-info',
  };

  return (
    <span className={cn('badge', variants[variant], className)}>
      {children}
    </span>
  );
}
