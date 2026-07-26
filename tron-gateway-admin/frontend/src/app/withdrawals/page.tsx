'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
    Search,
    Download,
    ExternalLink,
    CheckCircle2,
    Clock,
    AlertTriangle
} from 'lucide-react';
import { dashboardApi } from '@/lib/api';
import { format } from 'date-fns';
import { Sidebar } from '@/components/layout/Sidebar';
import { DateRangePicker } from '@/components/ui/DatePicker';

export default function WithdrawalsPage() {
    const [page, setPage] = useState(1);
    const [statusFilter, setStatusFilter] = useState('');
    const [startDate, setStartDate] = useState<Date | null>(null);
    const [endDate, setEndDate] = useState<Date | null>(null);

    const formatDateForApi = (date: Date | null) => {
        if (!date) return undefined;
        return format(date, 'yyyy-MM-dd');
    };

    const { data, isLoading } = useQuery({
        queryKey: ['withdrawals', page, statusFilter, startDate?.toISOString(), endDate?.toISOString()],
        queryFn: () => dashboardApi.getWithdrawals({
            page,
            limit: 20,
            status: statusFilter || undefined,
            start_date: formatDateForApi(startDate),
            end_date: formatDateForApi(endDate)
        }),
    });

    return (
        <div className="flex min-h-screen bg-dark-900">
            <Sidebar />
            <main className="flex-1 lg:pl-[280px] transition-all duration-300">
                <div className="p-6 md:p-8 space-y-6">
                    {/* Header */}
                    <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold text-white tracking-tight">출금 내역</h1>
                            <p className="text-dark-300 mt-1">외부 지갑으로 출금된 내역을 조회합니다.</p>
                        </div>

                        <button className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 text-white border border-white/5 rounded-lg transition-colors">
                            <Download className="w-4 h-4" />
                            <span>엑셀 다운로드</span>
                        </button>
                    </div>

                    {/* Filters */}
                    <div className="relative z-50 flex flex-wrap gap-4 p-4 bg-dark-800/50 backdrop-blur-xl border border-white/5 rounded-2xl">
                        <div className="relative flex-1 min-w-[200px] max-w-xs">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                            <input
                                type="text"
                                placeholder="주소 또는 TXID 검색..."
                                className="w-full pl-10 h-10 bg-dark-900/50 border border-white/5 rounded-xl text-white placeholder:text-dark-500 focus:outline-none focus:border-accent-primary/50 transition-colors"
                            />
                        </div>
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                            className="h-10 px-4 bg-dark-900/50 border border-white/5 rounded-xl text-white focus:outline-none focus:border-accent-primary/50 transition-colors"
                        >
                            <option value="">모든 상태</option>
                            <option value="pending">대기중</option>
                            <option value="processing">처리중</option>
                            <option value="completed">완료됨</option>
                            <option value="failed">실패</option>
                        </select>
                        <DateRangePicker
                            startDate={startDate}
                            endDate={endDate}
                            onStartDateChange={setStartDate}
                            onEndDateChange={setEndDate}
                        />
                    </div>

                    {/* List */}
                    <div className="bg-dark-800/50 backdrop-blur-xl border border-white/5 rounded-2xl overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-white/5 bg-white/5">
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">시간</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">출금액</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">받는 주소</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">TXID</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">상태</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {isLoading ? (
                                        <tr>
                                            <td colSpan={5} className="px-6 py-8 text-center text-dark-400">
                                                로딩 중...
                                            </td>
                                        </tr>
                                    ) : !data?.data?.withdrawals || data.data.withdrawals.length === 0 ? (
                                        <tr>
                                            <td colSpan={5} className="px-6 py-8 text-center text-dark-400">
                                                출금 내역이 없습니다.
                                            </td>
                                        </tr>
                                    ) : (
                                        data.data.withdrawals.map((withdrawal: any) => (
                                            <tr key={withdrawal.withdrawal_id} className="group hover:bg-white/5 transition-colors">
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <div className="flex items-center gap-1.5 text-sm text-dark-300">
                                                        <Clock className="w-3.5 h-3.5" />
                                                        {format(new Date(withdrawal.created_at), 'yyyy-MM-dd HH:mm:ss')}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className="text-sm font-bold text-accent-danger">
                                                        -{withdrawal.amount.toLocaleString()} USDT
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className="text-sm text-dark-300 font-mono">
                                                        {withdrawal.to_address.substring(0, 6)}...{withdrawal.to_address.substring(withdrawal.to_address.length - 6)}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    {withdrawal.tx_id ? (
                                                        <div className="flex items-center gap-2 text-sm text-accent-primary font-mono group-hover:underline cursor-pointer"
                                                            onClick={() => window.open(`https://tronscan.org/#/transaction/${withdrawal.tx_id}`, '_blank')}>
                                                            {withdrawal.tx_id.substring(0, 8)}...
                                                            <ExternalLink className="w-3 h-3 opacity-50" />
                                                        </div>
                                                    ) : (
                                                        <span className="text-xs text-dark-500">-</span>
                                                    )}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${withdrawal.status === 'completed' ? 'bg-accent-success/10 text-accent-success' :
                                                        withdrawal.status === 'pending' ? 'bg-accent-warning/10 text-accent-warning' :
                                                            withdrawal.status === 'failed' ? 'bg-accent-danger/10 text-accent-danger' :
                                                                'bg-dark-600 text-dark-300'
                                                        }`}>
                                                        {withdrawal.status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                                                        {withdrawal.status === 'pending' && <Clock className="w-3 h-3" />}
                                                        {withdrawal.status === 'failed' && <AlertTriangle className="w-3 h-3" />}
                                                        {withdrawal.status}
                                                    </span>
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
        </div>
    );
}
