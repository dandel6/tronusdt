import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// 클래스 이름 병합
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// USDT 금액 포맷 (6 decimals)
export function formatUsdt(amount: number, decimals: number = 2): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(amount);
}

// 큰 숫자 포맷 (K, M, B)
export function formatCompactNumber(num: number): string {
  if (num >= 1_000_000_000) {
    return `${(num / 1_000_000_000).toFixed(1)}B`;
  }
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`;
  }
  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`;
  }
  return num.toString();
}

// 주소 축약
export function shortenAddress(address: string, chars: number = 6): string {
  if (!address) return '';
  return `${address.slice(0, chars)}...${address.slice(-chars)}`;
}

// 날짜 포맷
export function formatDate(dateStr: string, format: 'full' | 'short' | 'time' = 'full'): string {
  const date = new Date(dateStr);
  
  if (format === 'time') {
    return date.toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }
  
  if (format === 'short') {
    return date.toLocaleDateString('ko-KR', {
      month: 'short',
      day: 'numeric',
    });
  }
  
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// 상대 시간
export function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (seconds < 60) return '방금 전';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분 전`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}시간 전`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}일 전`;
  
  return formatDate(dateStr, 'short');
}

// 상태 색상
export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    // 입금 상태
    pending: 'badge-warning',
    confirmed: 'badge-success',
    swept: 'badge-info',
    
    // 출금 상태
    processing: 'badge-warning',
    completed: 'badge-success',
    failed: 'badge-danger',
    
    // 기타
    active: 'badge-success',
    inactive: 'badge-danger',
  };
  
  return colors[status.toLowerCase()] || 'badge-info';
}

// 상태 레이블
export function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '대기중',
    confirmed: '확인됨',
    swept: '스위핑 완료',
    processing: '처리중',
    completed: '완료',
    failed: '실패',
    active: '활성',
    inactive: '비활성',
  };
  
  return labels[status.toLowerCase()] || status;
}

// 트랜잭션 타입 아이콘
export function getTxTypeInfo(type: 'deposit' | 'withdrawal'): {
  label: string;
  color: string;
  icon: string;
} {
  if (type === 'deposit') {
    return {
      label: '입금',
      color: 'text-accent-success',
      icon: 'ArrowDownCircle',
    };
  }
  return {
    label: '출금',
    color: 'text-accent-danger',
    icon: 'ArrowUpCircle',
  };
}

// TronScan 링크 생성
export function getTronscanUrl(txId: string): string {
  return `https://tronscan.org/#/transaction/${txId}`;
}

export function getTronscanAddressUrl(address: string): string {
  return `https://tronscan.org/#/address/${address}`;
}

// 클립보드 복사
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// 퍼센트 계산
export function calculatePercentChange(current: number, previous: number): number {
  if (previous === 0) return current > 0 ? 100 : 0;
  return ((current - previous) / previous) * 100;
}

// 디바운스
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;
  
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}
