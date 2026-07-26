"""
FastAPI 서버
REST API 엔드포인트
"""
from decimal import Decimal
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.db import get_session, UserWallet, Deposit, Withdrawal
from app.wallet import hd_wallet, tron_client
from app.sweeper import auto_sweeper
from app.withdrawal import withdrawal_processor

from contextlib import asynccontextmanager
from app.utils.notifier import notifier

from app.auth.auth_router import router as auth_router, limiter as auth_limiter
from app.api.dashboard_router import router as dashboard_router
from app.api.partner_router import router as partner_router
from app.api.system_router import router as system_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await notifier.alert_startup()
    yield
    # Shutdown
    await notifier.alert_shutdown()


app = FastAPI(
    title="TRON USDT Gateway",
    description="USDT TRC-20 입출금 자동화 API",
    version="1.0.0",
    lifespan=lifespan
)

# Rate Limiter 등록
app.state.limiter = auth_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 라우터 등록
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(partner_router)
app.include_router(system_router)


# ==========================================
# 보안 유틸리티
# ==========================================

def mask_address(address: str) -> str:
    """주소 마스킹 (앞 6자리...뒤 4자리)"""
    if not address or len(address) < 10:
        return "***"
    return f"{address[:6]}...{address[-4:]}"


def mask_balance(balance: float, show_range: bool = True) -> str:
    """잔액 마스킹 (범위로 표시)"""
    if not show_range:
        return "***"
    if balance < 100:
        return "< 100"
    elif balance < 1000:
        return "100 - 1K"
    elif balance < 10000:
        return "1K - 10K"
    elif balance < 100000:
        return "10K - 100K"
    else:
        return "> 100K"

# CORS 설정 (환경변수에서 허용 도메인 로드)
def get_cors_origins():
    """CORS 허용 도메인 목록 반환"""
    if settings.cors_origins:
        # 쉼표로 구분된 도메인 파싱
        origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
        if origins:
            return origins
    # 기본값: 로컬 개발환경만 허용 (프로덕션에서는 반드시 CORS_ORIGINS 설정 필요)
    print("경고: CORS_ORIGINS가 설정되지 않았습니다. 로컬 개발환경만 허용됩니다.")
    return ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)


# ==========================================
# 인증
# ==========================================

async def verify_api_key(x_api_key: str = Header(...)):
    """API 키 검증"""
    if x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# ==========================================
# 요청 스키마
# ==========================================

class CreateWalletRequest(BaseModel):
    user_id: int

class WithdrawRequest(BaseModel):
    user_id: int
    to_address: str  # 회원 외부 TRON 지갑
    amount: float


# ==========================================
# 지갑 API
# ==========================================

@app.post("/api/wallet/create")
async def create_wallet(
    request: CreateWalletRequest,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key)
):
    """
    사용자 입금 지갑 생성
    
    - HD Wallet에서 고유 주소 파생
    - BIP44 경로: m/44'/195'/0'/0/{user_id}
    """
    try:
        result = await hd_wallet.create_user_wallet(session, request.user_id)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/wallet/{user_id}")
async def get_wallet(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key)
):
    """사용자 지갑 정보 조회"""
    wallet = await hd_wallet.get_user_wallet(session, user_id)
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # 온체인 잔액 조회
    onchain_balance = tron_client.get_usdt_balance(wallet.wallet_address)
    
    return {
        "user_id": wallet.user_id,
        "address": wallet.wallet_address,
        "onchain_balance": float(onchain_balance),
        "created_at": wallet.created_at.isoformat()
    }


# ==========================================
# 입금 API
# ==========================================

@app.get("/api/deposits/{user_id}")
async def get_deposits(
    user_id: int,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key)
):
    """사용자 입금 내역 조회"""
    result = await session.execute(
        select(Deposit)
        .where(Deposit.user_id == user_id)
        .order_by(Deposit.created_at.desc())
        .limit(limit)
    )
    deposits = result.scalars().all()
    
    return {
        "deposits": [
            {
                "tx_id": d.tx_id,
                "amount": float(d.amount),
                "from_address": d.from_address,
                "status": d.status,
                "swept": d.swept,
                "created_at": d.created_at.isoformat()
            }
            for d in deposits
        ]
    }


# ==========================================
# 출금 API
# ==========================================

@app.post("/api/withdraw")
async def create_withdrawal(
    request: WithdrawRequest,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key)
):
    """
    출금 요청
    
    - 메인 핫월렛에서 회원 외부 지갑으로 전송
    - to_address: 회원이 입력한 본인 TRON 지갑 주소
    """
    try:
        result = await withdrawal_processor.create_withdrawal(
            session,
            user_id=request.user_id,
            to_address=request.to_address,
            amount=Decimal(str(request.amount))
        )
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/withdrawal/{withdrawal_id}")
async def get_withdrawal(
    withdrawal_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key)
):
    """출금 상태 조회"""
    withdrawal = await withdrawal_processor.get_withdrawal(session, withdrawal_id)
    
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    
    return {
        "withdrawal_id": withdrawal.withdrawal_id,
        "user_id": withdrawal.user_id,
        "to_address": withdrawal.to_address,
        "amount": float(withdrawal.amount),
        "tx_id": withdrawal.tx_id,
        "status": withdrawal.status,
        "created_at": withdrawal.created_at.isoformat(),
        "processed_at": withdrawal.processed_at.isoformat() if withdrawal.processed_at else None
    }


@app.get("/api/withdrawals/{user_id}")
async def get_user_withdrawals(
    user_id: int,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key)
):
    """사용자 출금 내역"""
    withdrawals = await withdrawal_processor.get_user_withdrawals(session, user_id, limit)
    
    return {
        "withdrawals": [
            {
                "withdrawal_id": w.withdrawal_id,
                "to_address": w.to_address,
                "amount": float(w.amount),
                "tx_id": w.tx_id,
                "status": w.status,
                "created_at": w.created_at.isoformat()
            }
            for w in withdrawals
        ]
    }


@app.post("/api/withdraw/process")
async def process_withdrawals(_: str = Depends(verify_api_key)):
    """출금 배치 처리 (관리자)"""
    result = await withdrawal_processor.process_pending()
    return result


# ==========================================
# 스위핑 API (관리자)
# ==========================================

@app.post("/api/sweep/all")
async def sweep_all(_: str = Depends(verify_api_key)):
    """전체 스위핑 실행"""
    result = await auto_sweeper.sweep_all()
    return result


@app.post("/api/sweep/{address}")
async def sweep_address(
    address: str,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key)
):
    """특정 주소 강제 스위핑"""
    try:
        result = await auto_sweeper.force_sweep(session, address)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# 시스템 API
# ==========================================

@app.get("/api/system/status")
async def get_system_status(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
    show_sensitive: bool = False  # 민감 정보 표시 여부 (Super Admin만)
):
    """
    시스템 상태 (민감 정보 마스킹)

    - 기본: 주소/잔액 마스킹
    - show_sensitive=true: 실제 값 표시 (Super Admin 전용)
    """
    # 메인 지갑 잔액
    main_usdt = tron_client.get_usdt_balance(settings.main_wallet_address)
    main_trx = tron_client.get_trx_balance(settings.main_wallet_address)
    main_resources = tron_client.get_account_resources(settings.main_wallet_address)

    # 통계
    user_count = await session.execute(select(func.count(UserWallet.user_id)))

    pending_withdrawals = await session.execute(
        select(func.count(Withdrawal.withdrawal_id), func.sum(Withdrawal.amount))
        .where(Withdrawal.status == "pending")
    )
    pending_row = pending_withdrawals.first()

    unswept_deposits = await session.execute(
        select(func.count(Deposit.tx_id), func.sum(Deposit.amount))
        .where(Deposit.swept == False)
    )
    unswept_row = unswept_deposits.first()

    # 민감 정보 마스킹 적용
    if show_sensitive:
        # 실제 값 (Super Admin용)
        wallet_info = {
            "address": settings.main_wallet_address,
            "usdt_balance": float(main_usdt),
            "trx_balance": float(main_trx),
            "energy_available": main_resources.get("energy_available", 0)
        }
    else:
        # 마스킹된 값 (일반 조회)
        wallet_info = {
            "address": mask_address(settings.main_wallet_address),
            "usdt_balance_range": mask_balance(float(main_usdt)),
            "trx_balance_range": mask_balance(float(main_trx)),
            "energy_available": main_resources.get("energy_available", 0)
        }

    return {
        "main_wallet": wallet_info,
        "stats": {
            "total_users": user_count.scalar(),
            "pending_withdrawals": {
                "count": pending_row[0] or 0,
                "amount": float(pending_row[1] or 0) if show_sensitive else "***"
            },
            "unswept_deposits": {
                "count": unswept_row[0] or 0,
                "amount": float(unswept_row[1] or 0) if show_sensitive else "***"
            }
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "ok"}
