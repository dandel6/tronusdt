"""
시스템 설정 API 라우터
Super Admin 전용

보안 계층:
- CLI 전용: 긴급 제어, 지갑 설정 등 민감한 설정
- Frontend Super Admin: 수수료, 한도, 알림 등 운영 설정
"""
import json
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_session
from app.db.admin_models import SystemConfig, AdminRole, AuditLog
from app.auth import get_current_admin, require_role, get_client_ip
from app.config import settings


router = APIRouter(prefix="/api/system", tags=["System"])


# CLI 전용 설정 키 (Frontend에서 수정 불가)
CLI_ONLY_KEYS = {
    # 긴급 제어
    "withdrawal_enabled",
    "deposit_monitor_enabled",
    "sweep_enabled",
    "emergency_mode",
    # 지갑 관련
    "cold_wallet_address",
    "main_wallet_address",
    # 대량 출금 임계값
    "large_withdrawal_threshold",
    # IP 차단
    "blocked_ip_",  # prefix
}


def is_cli_only_key(key: str) -> bool:
    """CLI 전용 키인지 확인"""
    if key in CLI_ONLY_KEYS:
        return True
    # prefix 체크 (blocked_ip_ 등)
    for cli_key in CLI_ONLY_KEYS:
        if cli_key.endswith("_") and key.startswith(cli_key):
            return True
    return False


class SystemConfigUpdate(BaseModel):
    value: str
    description: Optional[str] = None


@router.get("/configs")
async def get_all_configs(
    category: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """시스템 설정 목록 조회 (Super Admin 전용)"""
    query = select(SystemConfig)
    if category:
        query = query.where(SystemConfig.category == category)

    result = await session.execute(query)
    configs = result.scalars().all()

    grouped = {}
    for config in configs:
        if config.category not in grouped:
            grouped[config.category] = []

        cli_only = is_cli_only_key(config.key)

        grouped[config.category].append({
            "key": config.key,
            "value": config.value if not config.is_sensitive else "***",
            "description": config.description,
            "is_sensitive": config.is_sensitive,
            "cli_only": cli_only,  # CLI 전용 여부
            "updated_at": config.updated_at.isoformat() if config.updated_at else None
        })

    return {"configs": grouped}


@router.put("/configs/{key}")
async def update_config(
    key: str,
    request: SystemConfigUpdate,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """설정 값 업데이트 (Super Admin 전용)"""
    # CLI 전용 키 체크
    if is_cli_only_key(key):
        raise HTTPException(
            status_code=403,
            detail=f"이 설정은 CLI에서만 변경 가능합니다. 서버에서 'python scripts/admin_cli.py'를 실행하세요."
        )

    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    old_value = config.value
    config.value = request.value
    if request.description:
        config.description = request.description
    config.updated_by = int(admin["sub"])
    
    ip = get_client_ip(req)
    audit_log = AuditLog(
        admin_id=int(admin["sub"]),
        action="update_config",
        resource_type="config",
        resource_id=key,
        details=json.dumps({"old": old_value if not config.is_sensitive else "***", "new": request.value if not config.is_sensitive else "***"}),
        ip_address=ip
    )
    session.add(audit_log)
    await session.commit()
    
    return {"message": "Config updated", "key": key}


@router.post("/configs/init")
async def init_default_configs(
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """기본 설정 초기화 (Super Admin 전용)"""
    defaults = [
        ("sweep_threshold_usdt", "10", "스위핑 임계값 (USDT)", "sweep"),
        ("sweep_enabled", "true", "자동 스위핑 활성화", "sweep"),
        ("default_fee_rate", "100", "기본 수수료율 (100=1%)", "fee"),
        ("min_withdrawal", "10000000", "최소 출금액", "fee"),
        ("max_daily_withdrawal", "10000000000", "일일 최대 출금액", "fee"),
        ("max_login_attempts", "5", "최대 로그인 시도", "security"),
        ("lockout_minutes", "30", "계정 잠금 시간(분)", "security"),
        ("telegram_enabled", "true", "텔레그램 알림", "notification"),
        ("alert_low_balance", "1000", "잔액 부족 알림 임계값", "notification"),
    ]
    
    created = 0
    for key, value, desc, cat in defaults:
        result = await session.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        if not result.scalar_one_or_none():
            session.add(SystemConfig(key=key, value=value, description=desc, category=cat))
            created += 1
    
    await session.commit()
    return {"message": f"Initialized {created} configs"}


@router.get("/status")
async def get_system_status(
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """시스템 상태 조회"""
    from app.wallet import tron_client
    
    status = {
        "server": "running",
        "database": "connected",
        "tron_api": "unknown"
    }
    
    try:
        tron_client.get_usdt_balance(settings.main_wallet_address)
        status["tron_api"] = "connected"
    except Exception:
        status["tron_api"] = "error"
    
    admin_role = AdminRole(admin["role"])
    if admin_role == AdminRole.SUPER_ADMIN:
        try:
            main_usdt = tron_client.get_usdt_balance(settings.main_wallet_address)
            main_trx = tron_client.get_trx_balance(settings.main_wallet_address)
            status["main_wallet"] = {
                "address": settings.main_wallet_address,
                "usdt": float(main_usdt),
                "trx": float(main_trx)
            }
        except Exception:
            status["main_wallet"] = {"error": "Failed to fetch"}
    
    return status
