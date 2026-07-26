"""
Dashboard API Router
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

from app.db import get_session
from app.db.models import Wallet, Deposit, Withdrawal
from app.auth.dependencies import get_current_admin, require_permission
from app.db.admin_models import Admin, AdminRole

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# Response Models
class StatsResponse(BaseModel):
    total_users: int
    total_deposits: dict
    total_withdrawals: dict
    pending_withdrawals: dict
    unswept_deposits: dict
    today: dict
    total_fees: dict  # Added fee stats
    main_wallet: Optional[dict] = None
    timestamp: str


class DepositResponse(BaseModel):
    tx_id: str
    user_id: int
    amount: float
    from_address: str
    status: str
    confirmations: int = 0
    swept: bool
    sweep_tx_id: Optional[str] = None
    created_at: str


class WithdrawalResponse(BaseModel):
    withdrawal_id: int
    user_id: int
    to_address: str
    amount: float
    tx_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: str
    processed_at: Optional[str] = None


class WalletResponse(BaseModel):
    user_id: int
    wallet_address: str
    derivation_path: Optional[str] = None
    balance: float = 0
    usdt_balance: float = 0
    trx_balance: float = 0
    created_at: str


class TransactionResponse(BaseModel):
    type: str
    id: str
    user_id: int
    amount: float
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    tx_id: Optional[str] = None
    status: str
    swept: Optional[bool] = None
    created_at: str


class ChartDataPoint(BaseModel):
    date: str
    deposits: dict
    withdrawals: dict


@router.get("/stats", response_model=StatsResponse)
async def get_dashboard_stats(
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Get dashboard statistics"""
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    
    # Partner filter for non-super admins
    partner_filter = True
    if current_admin.role != AdminRole.SUPER_ADMIN and current_admin.partner_id:
        partner_filter = Wallet.partner_id == current_admin.partner_id
    
    # Total users (wallets)
    total_users_result = await session.execute(
        select(func.count(Wallet.user_id)).where(partner_filter)
    )
    total_users = total_users_result.scalar() or 0
    
    # Total deposits
    total_deposits_result = await session.execute(
        select(
            func.count(Deposit.tx_id),
            func.coalesce(func.sum(Deposit.amount), 0)
        ).select_from(Deposit).join(Wallet, Deposit.user_id == Wallet.user_id).where(partner_filter)
    )
    total_deposits_row = total_deposits_result.first()
    total_deposits = {
        "count": total_deposits_row[0] or 0,
        "amount": float(total_deposits_row[1] or 0)
    }
    
    # Total withdrawals
    total_withdrawals_result = await session.execute(
        select(
            func.count(Withdrawal.withdrawal_id),
            func.coalesce(func.sum(Withdrawal.amount), 0)
        ).select_from(Withdrawal).join(Wallet, Withdrawal.user_id == Wallet.user_id).where(partner_filter)
    )
    total_withdrawals_row = total_withdrawals_result.first()
    total_withdrawals = {
        "count": total_withdrawals_row[0] or 0,
        "amount": float(total_withdrawals_row[1] or 0)
    }
    
    # Pending withdrawals
    pending_withdrawals_result = await session.execute(
        select(
            func.count(Withdrawal.withdrawal_id),
            func.coalesce(func.sum(Withdrawal.amount), 0)
        ).select_from(Withdrawal).join(Wallet, Withdrawal.user_id == Wallet.user_id).where(
            and_(partner_filter, Withdrawal.status == 'pending')
        )
    )
    pending_row = pending_withdrawals_result.first()
    pending_withdrawals = {
        "count": pending_row[0] or 0,
        "amount": float(pending_row[1] or 0)
    }
    
    # Unswept deposits
    unswept_result = await session.execute(
        select(
            func.count(Deposit.tx_id),
            func.coalesce(func.sum(Deposit.amount), 0)
        ).select_from(Deposit).join(Wallet, Deposit.user_id == Wallet.user_id).where(
            and_(partner_filter, Deposit.swept == False)
        )
    )
    unswept_row = unswept_result.first()
    unswept_deposits = {
        "count": unswept_row[0] or 0,
        "amount": float(unswept_row[1] or 0)
    }
    
    # Today's stats
    today_deposits_result = await session.execute(
        select(
            func.count(Deposit.tx_id),
            func.coalesce(func.sum(Deposit.amount), 0)
        ).select_from(Deposit).join(Wallet, Deposit.user_id == Wallet.user_id).where(
            and_(partner_filter, Deposit.created_at >= today_start)
        )
    )
    today_deposits_row = today_deposits_result.first()
    
    today_withdrawals_result = await session.execute(
        select(
            func.count(Withdrawal.withdrawal_id),
            func.coalesce(func.sum(Withdrawal.amount), 0)
        ).select_from(Withdrawal).join(Wallet, Withdrawal.user_id == Wallet.user_id).where(
            and_(partner_filter, Withdrawal.created_at >= today_start)
        )
    )
    today_withdrawals_row = today_withdrawals_result.first()
    
    today = {
        "deposits": {
            "count": today_deposits_row[0] or 0,
            "amount": float(today_deposits_row[1] or 0)
        },
        "withdrawals": {
            "count": today_withdrawals_row[0] or 0,
            "amount": float(today_withdrawals_row[1] or 0)
        }
    }
    
    # Fee calculation (1% default rate)
    # In production, this should come from a fees table
    fee_rate = 0.01  # 1%
    total_fee_amount = total_deposits["amount"] * fee_rate
    today_fee_amount = today["deposits"]["amount"] * fee_rate
    
    total_fees = {
        "amount": total_fee_amount,
        "today_amount": today_fee_amount
    }
    
    # Main wallet info (Super Admin only)
    main_wallet = None
    if current_admin.role == AdminRole.SUPER_ADMIN:
        # In production, fetch from actual main wallet
        main_wallet = {
            "address": "TMainWalletAddressHere",
            "usdt_balance": 0,
            "trx_balance": 0,
            "energy_available": 0,
            "bandwidth_available": 0
        }
    
    return StatsResponse(
        total_users=total_users,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        pending_withdrawals=pending_withdrawals,
        unswept_deposits=unswept_deposits,
        today=today,
        total_fees=total_fees,
        main_wallet=main_wallet,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/chart/transactions")
async def get_chart_data(
    days: int = Query(7, ge=1, le=90),
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Get transaction chart data for last N days"""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)
    
    data = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        date_start = datetime.combine(date, datetime.min.time())
        date_end = datetime.combine(date + timedelta(days=1), datetime.min.time())
        
        # Deposits for this day
        deposits_result = await session.execute(
            select(
                func.count(Deposit.tx_id),
                func.coalesce(func.sum(Deposit.amount), 0)
            ).where(
                and_(Deposit.created_at >= date_start, Deposit.created_at < date_end)
            )
        )
        deposits_row = deposits_result.first()
        
        # Withdrawals for this day
        withdrawals_result = await session.execute(
            select(
                func.count(Withdrawal.withdrawal_id),
                func.coalesce(func.sum(Withdrawal.amount), 0)
            ).where(
                and_(Withdrawal.created_at >= date_start, Withdrawal.created_at < date_end)
            )
        )
        withdrawals_row = withdrawals_result.first()
        
        data.append({
            "date": date.isoformat(),
            "deposits": {
                "count": deposits_row[0] or 0,
                "amount": float(deposits_row[1] or 0)
            },
            "withdrawals": {
                "count": withdrawals_row[0] or 0,
                "amount": float(withdrawals_row[1] or 0)
            }
        })
    
    return {"data": data}


@router.get("/transactions/recent")
async def get_recent_transactions(
    limit: int = Query(50, ge=1, le=100),
    tx_type: Optional[str] = Query(None, regex="^(deposit|withdrawal)$"),
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Get recent transactions"""
    transactions = []
    
    # Get deposits
    if tx_type is None or tx_type == "deposit":
        deposits_result = await session.execute(
            select(Deposit).order_by(Deposit.created_at.desc()).limit(limit)
        )
        for deposit in deposits_result.scalars():
            transactions.append({
                "type": "deposit",
                "id": deposit.tx_id,
                "user_id": deposit.user_id,
                "amount": float(deposit.amount),
                "from_address": deposit.from_address,
                "to_address": None,
                "tx_id": deposit.tx_id,
                "status": deposit.status,
                "swept": deposit.swept,
                "created_at": deposit.created_at.isoformat()
            })
    
    # Get withdrawals
    if tx_type is None or tx_type == "withdrawal":
        withdrawals_result = await session.execute(
            select(Withdrawal).order_by(Withdrawal.created_at.desc()).limit(limit)
        )
        for withdrawal in withdrawals_result.scalars():
            transactions.append({
                "type": "withdrawal",
                "id": str(withdrawal.withdrawal_id),
                "user_id": withdrawal.user_id,
                "amount": float(withdrawal.amount),
                "from_address": None,
                "to_address": withdrawal.to_address,
                "tx_id": withdrawal.tx_id,
                "status": withdrawal.status,
                "swept": None,
                "created_at": withdrawal.created_at.isoformat()
            })
    
    # Sort by created_at
    transactions.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {"transactions": transactions[:limit]}


@router.get("/deposits")
async def get_deposits(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    swept: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Get deposits list"""
    query = select(Deposit)
    
    if user_id:
        query = query.where(Deposit.user_id == user_id)
    if status:
        query = query.where(Deposit.status == status)
    if swept is not None:
        query = query.where(Deposit.swept == swept)
    
    query = query.order_by(Deposit.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    deposits = []
    for deposit in result.scalars():
        deposits.append({
            "tx_id": deposit.tx_id,
            "user_id": deposit.user_id,
            "amount": float(deposit.amount),
            "from_address": deposit.from_address,
            "status": deposit.status,
            "confirmations": getattr(deposit, 'confirmations', 0),
            "swept": deposit.swept,
            "sweep_tx_id": getattr(deposit, 'sweep_tx_id', None),
            "created_at": deposit.created_at.isoformat()
        })
    
    return {"deposits": deposits, "page": page, "limit": limit}


@router.get("/withdrawals")
async def get_withdrawals(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Get withdrawals list"""
    query = select(Withdrawal)
    
    if user_id:
        query = query.where(Withdrawal.user_id == user_id)
    if status:
        query = query.where(Withdrawal.status == status)
    
    query = query.order_by(Withdrawal.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    withdrawals = []
    for withdrawal in result.scalars():
        withdrawals.append({
            "withdrawal_id": withdrawal.withdrawal_id,
            "user_id": withdrawal.user_id,
            "to_address": withdrawal.to_address,
            "amount": float(withdrawal.amount),
            "tx_id": withdrawal.tx_id,
            "status": withdrawal.status,
            "error_message": getattr(withdrawal, 'error_message', None),
            "created_at": withdrawal.created_at.isoformat(),
            "processed_at": withdrawal.processed_at.isoformat() if withdrawal.processed_at else None
        })
    
    return {"withdrawals": withdrawals, "page": page, "limit": limit}


@router.get("/wallets")
async def get_wallets(
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Get wallets list"""
    query = select(Wallet)
    
    if user_id:
        query = query.where(Wallet.user_id == user_id)
    
    # Partner filter
    if current_admin.role != AdminRole.SUPER_ADMIN and current_admin.partner_id:
        query = query.where(Wallet.partner_id == current_admin.partner_id)
    
    query = query.order_by(Wallet.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    wallets = []
    for wallet in result.scalars():
        wallets.append({
            "user_id": wallet.user_id,
            "wallet_address": wallet.wallet_address,
            "derivation_path": getattr(wallet, 'derivation_path', None),
            "balance": float(getattr(wallet, 'balance', 0) or 0),
            "usdt_balance": float(getattr(wallet, 'usdt_balance', 0) or 0),
            "trx_balance": float(getattr(wallet, 'trx_balance', 0) or 0),
            "created_at": wallet.created_at.isoformat()
        })
    
    return {"wallets": wallets, "page": page, "limit": limit}


@router.get("/wallets/{user_id}")
async def get_wallet_detail(
    user_id: int,
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Get wallet detail"""
    result = await session.execute(
        select(Wallet).where(Wallet.user_id == user_id)
    )
    wallet = result.scalar_one_or_none()
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Get deposit history
    deposits_result = await session.execute(
        select(Deposit).where(Deposit.user_id == user_id).order_by(Deposit.created_at.desc()).limit(50)
    )
    deposits = [
        {
            "tx_id": d.tx_id,
            "amount": float(d.amount),
            "from_address": d.from_address,
            "status": d.status,
            "swept": d.swept,
            "created_at": d.created_at.isoformat()
        }
        for d in deposits_result.scalars()
    ]
    
    # Get withdrawal history
    withdrawals_result = await session.execute(
        select(Withdrawal).where(Withdrawal.user_id == user_id).order_by(Withdrawal.created_at.desc()).limit(50)
    )
    withdrawals = [
        {
            "withdrawal_id": w.withdrawal_id,
            "amount": float(w.amount),
            "to_address": w.to_address,
            "status": w.status,
            "tx_id": w.tx_id,
            "created_at": w.created_at.isoformat()
        }
        for w in withdrawals_result.scalars()
    ]
    
    return {
        "wallet": {
            "user_id": wallet.user_id,
            "wallet_address": wallet.wallet_address,
            "balance": float(getattr(wallet, 'balance', 0) or 0),
            "created_at": wallet.created_at.isoformat()
        },
        "deposits": deposits,
        "withdrawals": withdrawals
    }
