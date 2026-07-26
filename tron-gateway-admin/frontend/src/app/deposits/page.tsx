'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
    Search,
    Download,
    ExternalLink,
    CheckCircle2,
    Clock
} from 'lucide-react';
import { dashboardApi } from '@/lib/api';
import { format } from 'date-fns';
import { Sidebar } from '@/components/layout/Sidebar';
import { DateRangePicker } from '@/components/ui/DatePicker';

export default function DepositsPage() {
    const [page, setPage] = useState(1);
    const [statusFilter, setStatusFilter] = useState('');
    const [startDate, setStartDate] = useState<Date | null>(null);
    const [endDate, setEndDate] = useState<Date | null>(null);

    const formatDateForApi = (date: Date | null) => {
        if (!date) return undefined;
        return format(date, 'yyyy-MM-dd');
    };

    const { data, isLoading } = useQuery({
        queryKey: ['deposits', page, statusFilter, startDate?.toISOString(), endDate?.toISOString()],
        queryFn: () => dashboardApi.getDeposits({
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
                            <h1 className="text-2xl font-bold text-white tracking-tight">입금 내역</h1>
                            <p className="text-dark-300 mt-1">사용자 지갑으로 입금된 모든 내역을 조회합니다.</p>
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
                            <option value="confirmed">승인됨</option>
                            <option value="pending">대기중</option>
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
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">TXID / 시간</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">입금액</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">보낸 주소</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">상태</th>
                                        <th className="px-6 py-4 text-left text-xs font-medium text-dark-300 uppercase tracking-wider">스위핑</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {isLoading ? (
                                        <tr>
                                            <td colSpan={5} className="px-6 py-8 text-center text-dark-400">
                                                로딩 중...
                                            </td>
                                        </tr>
                                    ) : !data?.data?.deposits || data.data.deposits.length === 0 ? (
                                        <tr>
                                            <td colSpan={5} className="px-6 py-8 text-center text-dark-400">
                                                입금 내역이 없습니다.
                                            </td>
                                        </tr>
                                    ) : (
                                        data.data.deposits.map((deposit: any) => (
                                            <tr key={deposit.tx_id} className="group hover:bg-white/5 transition-colors">
                                                <td className="px-6 py-4">
                                                    <div className="flex flex-col gap-1">
                                                        <div className="flex items-center gap-2 text-sm text-accent-primary font-mono group-hover:underline cursor-pointer"
                                                            onClick={() => window.open(`https://tronscan.org/#/transaction/${deposit.tx_id}`, '_blank')}>
                                                            {deposit.tx_id.substring(0, 8)}...{deposit.tx_id.substring(deposit.tx_id.length - 8)}
                                                            <ExternalLink className="w-3 h-3 opacity-50" />
                                                        </div>
                                                        <div className="text-xs text-dark-400">
                                                            {format(new Date(deposit.created_at), 'yyyy-MM-dd HH:mm:ss')}
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className="text-sm font-bold text-accent-success">
                                                        +{deposit.amount.toLocaleString()} USDT
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className="text-sm text-dark-300 font-mono">
                                                        {deposit.from_address.substring(0, 6)}...{deposit.from_address.substring(deposit.from_address.length - 6)}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${deposit.status === 'confirmed' ? 'bg-accent-success/10 text-accent-success' :
                                                        'bg-accent-warning/10 text-accent-warning'
                                                        }`}>
                                                        {deposit.status === 'confirmed' ? <CheckCircle2 className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                                                        {deposit.status}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className={`text-xs ${deposit.swept ? 'text-accent-primary' : 'text-dark-500'
                                                        }`}>
                                                        {deposit.swept ? '완료' : '대기'}
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
