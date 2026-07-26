"""
System Configuration API Router
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from app.db import get_session
from app.auth.dependencies import get_current_admin, require_super_admin
from app.db.admin_models import Admin, AdminRole, SystemConfig

router = APIRouter(prefix="/api/system", tags=["System"])


class ConfigUpdate(BaseModel):
    value: str
    description: Optional[str] = None


class ConfigResponse(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
    category: Optional[str] = None
    updated_at: Optional[str] = None


# Default system configurations
DEFAULT_CONFIGS = {
    "fee": [
        {"key": "FEE_RATE", "value": "100", "description": "Default fee rate (basis points, 100 = 1%)", "category": "fee"},
        {"key": "MIN_WITHDRAWAL", "value": "10000000", "description": "Minimum withdrawal amount (USDT, 6 decimals)", "category": "fee"},
        {"key": "MAX_WITHDRAWAL", "value": "100000000000", "description": "Maximum withdrawal amount (USDT, 6 decimals)", "category": "fee"},
        {"key": "DAILY_WITHDRAWAL_LIMIT", "value": "1000000000000", "description": "Daily withdrawal limit (USDT, 6 decimals)", "category": "fee"},
    ],
    "security": [
        {"key": "MAX_LOGIN_ATTEMPTS", "value": "5", "description": "Maximum login attempts", "category": "security"},
        {"key": "LOCKOUT_DURATION", "value": "1800", "description": "Account lockout duration (seconds)", "category": "security"},
        {"key": "SESSION_TIMEOUT", "value": "3600", "description": "Session timeout (seconds)", "category": "security"},
        {"key": "REQUIRE_2FA", "value": "false", "description": "Require 2FA for all admins", "category": "security"},
    ],
    "sweep": [
        {"key": "SWEEP_THRESHOLD", "value": "1000000", "description": "Sweep threshold (USDT, 6 decimals)", "category": "sweep"},
        {"key": "SWEEP_INTERVAL", "value": "300", "description": "Sweep interval (seconds)", "category": "sweep"},
        {"key": "MIN_CONFIRMATIONS", "value": "20", "description": "Minimum block confirmations", "category": "sweep"},
        {"key": "AUTO_SWEEP_ENABLED", "value": "true", "description": "Enable automatic sweeping", "category": "sweep"},
    ],
    "notification": [
        {"key": "WEBHOOK_ENABLED", "value": "true", "description": "Enable webhook notifications", "category": "notification"},
        {"key": "EMAIL_NOTIFICATIONS", "value": "true", "description": "Enable email notifications", "category": "notification"},
        {"key": "LARGE_DEPOSIT_THRESHOLD", "value": "10000000000", "description": "Large deposit alert threshold", "category": "notification"},
        {"key": "ALERT_EMAIL", "value": "", "description": "Alert recipient email", "category": "notification"},
    ],
}


@router.get("/status")
async def get_system_status(
    current_admin: Admin = Depends(get_current_admin)
):
    """Get system status"""
    return {
        "status": "operational",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "healthy",
            "tron_node": "healthy",
            "sweep_service": "running",
            "webhook_service": "running"
        }
    }


@router.get("/configs")
async def get_configs(
    category: Optional[str] = Query(None),
    current_admin: Admin = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session)
):
    """Get system configurations (Super Admin only)"""
    try:
        # Try to fetch from database
        result = await session.execute(select(SystemConfig))
        db_configs = {c.key: c for c in result.scalars()}
        
        # Merge with defaults
        configs = {}
        for cat, items in DEFAULT_CONFIGS.items():
            if category and cat != category:
                continue
            configs[cat] = []
            for item in items:
                if item["key"] in db_configs:
                    db_config = db_configs[item["key"]]
                    configs[cat].append({
                        "key": db_config.key,
                        "value": db_config.value,
                        "description": db_config.description or item["description"],
                        "category": cat,
                        "updated_at": db_config.updated_at.isoformat() if db_config.updated_at else None
                    })
                else:
                    configs[cat].append(item)
        
        return {"configs": configs}
    except Exception as e:
        # If database table doesn't exist, return defaults
        if category:
            return {"configs": {category: DEFAULT_CONFIGS.get(category, [])}}
        return {"configs": DEFAULT_CONFIGS}


@router.put("/configs/{key}")
async def update_config(
    key: str,
    config: ConfigUpdate,
    current_admin: Admin = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session)
):
    """Update system configuration (Super Admin only)"""
    # Find the config in defaults to get category
    category = None
    for cat, items in DEFAULT_CONFIGS.items():
        for item in items:
            if item["key"] == key:
                category = cat
                break
        if category:
            break
    
    if not category:
        raise HTTPException(status_code=404, detail=f"Configuration key '{key}' not found")
    
    try:
        # Check if exists in database
        result = await session.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.value = config.value
            if config.description:
                existing.description = config.description
            existing.updated_at = datetime.utcnow()
            existing.updated_by = current_admin.admin_id
        else:
            new_config = SystemConfig(
                key=key,
                value=config.value,
                description=config.description,
                category=category,
                created_by=current_admin.admin_id,
                updated_by=current_admin.admin_id
            )
            session.add(new_config)
        
        await session.commit()
        
        return {
            "key": key,
            "value": config.value,
            "description": config.description,
            "category": category,
            "updated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


@router.post("/configs/init")
async def init_configs(
    current_admin: Admin = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session)
):
    """Initialize default configurations in database (Super Admin only)"""
    try:
        created = 0
        for category, items in DEFAULT_CONFIGS.items():
            for item in items:
                # Check if exists
                result = await session.execute(
                    select(SystemConfig).where(SystemConfig.key == item["key"])
                )
                if not result.scalar_one_or_none():
                    new_config = SystemConfig(
                        key=item["key"],
                        value=item["value"],
                        description=item["description"],
                        category=category,
                        created_by=current_admin.admin_id,
                        updated_by=current_admin.admin_id
                    )
                    session.add(new_config)
                    created += 1
        
        await session.commit()
        
        return {
            "message": f"Initialized {created} configurations",
            "created": created
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to initialize configurations: {str(e)}")
