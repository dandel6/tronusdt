"""
대시보드 API 라우터
- 통계 및 실시간 데이터
- 권한별 데이터 필터링
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc

from app.db import get_session, UserWallet, Deposit, Withdrawal
from app.db.admin_models import Admin, Partner, AdminRole, Permission
from app.auth import get_current_admin, require_permission
from app.wallet import tron_client
from app.config import settings


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# ==========================================
# 대시보드 통계
# ==========================================

@router.get("/stats")
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    대시보드 통계
    
    - Super Admin: 전체 통계
    - Partner Admin/Staff: 파트너별 통계
    """
    admin_role = AdminRole(admin["role"])
    partner_id = admin.get("partner_id")
    
    # 기본 쿼리 필터
    wallet_filter = []
    deposit_filter = []
    withdrawal_filter = []
    
    if admin_role != AdminRole.SUPER_ADMIN and partner_id:
        # 파트너별 사용자 ID 목록 조회 (실제 구현에서는 파트너-사용자 연결 필요)
        # 여기서는 예시로 전체 데이터를 보여줌 (실제 구현 시 수정 필요)
        pass
    
    # 1. 총 사용자 수
    total_users = await session.execute(
        select(func.count(UserWallet.user_id))
    )
    total_users_count = total_users.scalar() or 0
    
    # 2. 총 입금 통계
    deposit_stats = await session.execute(
        select(
            func.count(Deposit.tx_id),
            func.coalesce(func.sum(Deposit.amount), 0)
        ).where(Deposit.status == "confirmed")
    )
    deposit_row = deposit_stats.first()
    total_deposits = {
        "count": deposit_row[0] or 0,
        "amount": float(deposit_row[1]) if deposit_row[1] else 0
    }
    
    # 3. 총 출금 통계
    withdrawal_stats = await session.execute(
        select(
            func.count(Withdrawal.withdrawal_id),
            func.coalesce(func.sum(Withdrawal.amount), 0)
        ).where(Withdrawal.status == "completed")
    )
    withdrawal_row = withdrawal_stats.first()
    total_withdrawals = {
        "count": withdrawal_row[0] or 0,
        "amount": float(withdrawal_row[1]) if withdrawal_row[1] else 0
    }
    
    # 4. 대기 중인 출금
    pending_stats = await session.execute(
        select(
            func.count(Withdrawal.withdrawal_id),
            func.coalesce(func.sum(Withdrawal.amount), 0)
        ).where(Withdrawal.status == "pending")
    )
    pending_row = pending_stats.first()
    pending_withdrawals = {
        "count": pending_row[0] or 0,
        "amount": float(pending_row[1]) if pending_row[1] else 0
    }
    
    # 5. 미스윕 입금
    unswept_stats = await session.execute(
        select(
            func.count(Deposit.tx_id),
            func.coalesce(func.sum(Deposit.amount), 0)
        ).where(and_(Deposit.status == "confirmed", Deposit.swept == False))
    )
    unswept_row = unswept_stats.first()
    unswept_deposits = {
        "count": unswept_row[0] or 0,
        "amount": float(unswept_row[1]) if unswept_row[1] else 0
    }
    
    # 6. 오늘 통계
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_deposits = await session.execute(
        select(
            func.count(Deposit.tx_id),
            func.coalesce(func.sum(Deposit.amount), 0)
        ).where(Deposit.created_at >= today_start)
    )
    today_deposits_row = today_deposits.first()
    
    today_withdrawals = await session.execute(
        select(
            func.count(Withdrawal.withdrawal_id),
            func.coalesce(func.sum(Withdrawal.amount), 0)
        ).where(Withdrawal.created_at >= today_start)
    )
    today_withdrawals_row = today_withdrawals.first()
    
    # 7. 메인 지갑 잔액 (Super Admin만)
    main_wallet_info = None
    if admin_role == AdminRole.SUPER_ADMIN:
        try:
            main_usdt = tron_client.get_usdt_balance(settings.main_wallet_address)
            main_trx = tron_client.get_trx_balance(settings.main_wallet_address)
            resources = tron_client.get_account_resources(settings.main_wallet_address)
            
            main_wallet_info = {
                "address": settings.main_wallet_address,
                "usdt_balance": float(main_usdt),
                "trx_balance": float(main_trx),
                "energy_available": resources.get("energy_available", 0),
                "bandwidth_available": resources.get("bandwidth_available", 0),
            }
        except Exception:
            main_wallet_info = {"error": "Failed to fetch wallet info"}
    
    # 수수료 계산 (시스템 설정에서 가져오기 - 기본 1%)
    # TODO: SystemConfig에서 fee_rate 가져오기
    fee_rate = 0.01  # 1%
    total_fee_amount = float(total_deposits["amount"]) * fee_rate
    today_fee_amount = float(today_deposits_row[1] or 0) * fee_rate
    
    total_fees = {
        "amount": total_fee_amount,
        "today_amount": today_fee_amount
    }
    
    return {
        "total_users": total_users_count,
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "pending_withdrawals": pending_withdrawals,
        "unswept_deposits": unswept_deposits,
        "today": {
            "deposits": {
                "count": today_deposits_row[0] or 0,
                "amount": float(today_deposits_row[1]) if today_deposits_row[1] else 0
            },
            "withdrawals": {
                "count": today_withdrawals_row[0] or 0,
                "amount": float(today_withdrawals_row[1]) if today_withdrawals_row[1] else 0
            }
        },
        "total_fees": total_fees,
        "main_wallet": main_wallet_info,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/chart/transactions")
async def get_transaction_chart(
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    트랜잭션 차트 데이터 (최근 N일)
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # 일별 입금 집계
    deposits_by_day = await session.execute(
        select(
            func.date(Deposit.created_at).label("date"),
            func.count(Deposit.tx_id),
            func.coalesce(func.sum(Deposit.amount), 0)
        ).where(Deposit.created_at >= start_date)
        .group_by(func.date(Deposit.created_at))
        .order_by(func.date(Deposit.created_at))
    )
    
    # 일별 출금 집계
    withdrawals_by_day = await session.execute(
        select(
            func.date(Withdrawal.created_at).label("date"),
            func.count(Withdrawal.withdrawal_id),
            func.coalesce(func.sum(Withdrawal.amount), 0)
        ).where(Withdrawal.created_at >= start_date)
        .group_by(func.date(Withdrawal.created_at))
        .order_by(func.date(Withdrawal.created_at))
    )
    
    # 결과 병합
    deposits_data = {str(row[0]): {"count": row[1], "amount": float(row[2])} 
                     for row in deposits_by_day.all()}
    withdrawals_data = {str(row[0]): {"count": row[1], "amount": float(row[2])} 
                        for row in withdrawals_by_day.all()}
    
    chart_data = []
    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        chart_data.append({
            "date": date_str,
            "deposits": deposits_data.get(date_str, {"count": 0, "amount": 0}),
            "withdrawals": withdrawals_data.get(date_str, {"count": 0, "amount": 0})
        })
        current += timedelta(days=1)
    
    return {"data": chart_data}


# ==========================================
# 실시간 트랜잭션 목록
# ==========================================

@router.get("/transactions/recent")
async def get_recent_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    tx_type: Optional[str] = Query(default=None, regex="^(deposit|withdrawal)$"),
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    최근 트랜잭션 목록
    
    실시간 모니터링용
    """
    transactions = []
    
    # 입금 조회
    if tx_type is None or tx_type == "deposit":
        deposits = await session.execute(
            select(Deposit)
            .order_by(desc(Deposit.created_at))
            .limit(limit)
        )
        for d in deposits.scalars().all():
            transactions.append({
                "type": "deposit",
                "id": d.tx_id,
                "user_id": d.user_id,
                "amount": float(d.amount),
                "from_address": d.from_address,
                "status": d.status,
                "swept": d.swept,
                "created_at": d.created_at.isoformat()
            })
    
    # 출금 조회
    if tx_type is None or tx_type == "withdrawal":
        withdrawals = await session.execute(
            select(Withdrawal)
            .order_by(desc(Withdrawal.created_at))
            .limit(limit)
        )
        for w in withdrawals.scalars().all():
            transactions.append({
                "type": "withdrawal",
                "id": str(w.withdrawal_id),
                "user_id": w.user_id,
                "amount": float(w.amount),
                "to_address": w.to_address,
                "tx_id": w.tx_id,
                "status": w.status,
                "created_at": w.created_at.isoformat()
            })
    
    # 시간순 정렬
    transactions.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {"transactions": transactions[:limit]}


@router.get("/deposits")
async def get_deposits(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    swept: Optional[bool] = None,
    page: int = 1,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission(Permission.VIEW_DEPOSITS))
):
    """입금 목록 조회"""
    query = select(Deposit).order_by(desc(Deposit.created_at))
    
    if user_id:
        query = query.where(Deposit.user_id == user_id)
    if status:
        query = query.where(Deposit.status == status)
    if swept is not None:
        query = query.where(Deposit.swept == swept)
    
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    deposits = result.scalars().all()
    
    return {
        "deposits": [
            {
                "tx_id": d.tx_id,
                "user_id": d.user_id,
                "amount": float(d.amount),
                "from_address": d.from_address,
                "status": d.status,
                "confirmations": d.confirmations,
                "swept": d.swept,
                "sweep_tx_id": d.sweep_tx_id,
                "created_at": d.created_at.isoformat()
            }
            for d in deposits
        ],
        "page": page,
        "limit": limit
    }


@router.get("/withdrawals")
async def get_withdrawals(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission(Permission.VIEW_WITHDRAWALS))
):
    """출금 목록 조회"""
    query = select(Withdrawal).order_by(desc(Withdrawal.created_at))
    
    if user_id:
        query = query.where(Withdrawal.user_id == user_id)
    if status:
        query = query.where(Withdrawal.status == status)
    
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    withdrawals = result.scalars().all()
    
    return {
        "withdrawals": [
            {
                "withdrawal_id": w.withdrawal_id,
                "user_id": w.user_id,
                "to_address": w.to_address,
                "amount": float(w.amount),
                "tx_id": w.tx_id,
                "status": w.status,
                "error_message": w.error_message,
                "created_at": w.created_at.isoformat(),
                "processed_at": w.processed_at.isoformat() if w.processed_at else None
            }
            for w in withdrawals
        ],
        "page": page,
        "limit": limit
    }


# ==========================================
# 지갑 관리
# ==========================================

@router.get("/wallets")
async def get_wallets(
    user_id: Optional[int] = None,
    page: int = 1,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission(Permission.VIEW_WALLETS))
):
    """지갑 목록 조회"""
    query = select(UserWallet).order_by(desc(UserWallet.created_at))
    
    if user_id:
        query = query.where(UserWallet.user_id == user_id)
    
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    wallets = result.scalars().all()
    
    wallet_list = []
    for w in wallets:
        # 온체인 잔액 조회 (대량 조회 시 성능 이슈 가능)
        try:
            balance = tron_client.get_usdt_balance(w.wallet_address)
        except Exception:
            balance = 0
        
        wallet_list.append({
            "user_id": w.user_id,
            "wallet_address": w.wallet_address,
            "derivation_path": w.derivation_path,
            "balance": float(balance),
            "created_at": w.created_at.isoformat()
        })
    
    return {
        "wallets": wallet_list,
        "page": page,
        "limit": limit
    }


@router.get("/wallets/{user_id}")
async def get_wallet_detail(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission(Permission.VIEW_WALLETS))
):
    """지갑 상세 조회"""
    result = await session.execute(
        select(UserWallet).where(UserWallet.user_id == user_id)
    )
    wallet = result.scalar_one_or_none()
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # 온체인 정보
    try:
        usdt_balance = tron_client.get_usdt_balance(wallet.wallet_address)
        trx_balance = tron_client.get_trx_balance(wallet.wallet_address)
    except Exception as e:
        usdt_balance = 0
        trx_balance = 0
    
    # 입금 내역
    deposits = await session.execute(
        select(Deposit)
        .where(Deposit.user_id == user_id)
        .order_by(desc(Deposit.created_at))
        .limit(20)
    )
    
    # 출금 내역
    withdrawals = await session.execute(
        select(Withdrawal)
        .where(Withdrawal.user_id == user_id)
        .order_by(desc(Withdrawal.created_at))
        .limit(20)
    )
    
    return {
        "user_id": wallet.user_id,
        "wallet_address": wallet.wallet_address,
        "derivation_path": wallet.derivation_path,
        "usdt_balance": float(usdt_balance),
        "trx_balance": float(trx_balance),
        "created_at": wallet.created_at.isoformat(),
        "deposits": [
            {
                "tx_id": d.tx_id,
                "amount": float(d.amount),
                "status": d.status,
                "created_at": d.created_at.isoformat()
            }
            for d in deposits.scalars().all()
        ],
        "withdrawals": [
            {
                "withdrawal_id": w.withdrawal_id,
                "amount": float(w.amount),
                "status": w.status,
                "created_at": w.created_at.isoformat()
            }
            for w in withdrawals.scalars().all()
        ]
    }
