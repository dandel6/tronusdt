"""
파트너(업체) 관리 API 라우터
Super Admin 전용
"""
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db import get_session
from app.db.admin_models import Partner, Admin, AdminRole, AuditLog
from app.auth import (
    get_current_admin,
    require_role,
    hash_password,
    get_client_ip,
)


router = APIRouter(prefix="/api/partners", tags=["Partners"])


# ==========================================
# 스키마
# ==========================================

class CreatePartnerRequest(BaseModel):
    """파트너 생성 요청"""
    name: str
    code: str
    description: Optional[str] = None
    webhook_url: Optional[str] = None
    fee_rate: int = 100  # 1%
    daily_withdrawal_limit: int = 10000_000000  # 10,000 USDT


class UpdatePartnerRequest(BaseModel):
    """파트너 수정 요청"""
    name: Optional[str] = None
    description: Optional[str] = None
    webhook_url: Optional[str] = None
    fee_rate: Optional[int] = None
    daily_withdrawal_limit: Optional[int] = None
    is_active: Optional[bool] = None


# ==========================================
# 파트너 CRUD
# ==========================================

@router.get("")
async def list_partners(
    is_active: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """
    파트너 목록 조회
    
    Super Admin 전용
    """
    query = select(Partner)
    
    if is_active is not None:
        query = query.where(Partner.is_active == is_active)
    
    query = query.order_by(Partner.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    partners = result.scalars().all()
    
    # 각 파트너별 관리자 수 조회
    partner_data = []
    for p in partners:
        admin_count = await session.execute(
            select(func.count(Admin.admin_id)).where(Admin.partner_id == p.partner_id)
        )
        partner_data.append({
            "partner_id": p.partner_id,
            "name": p.name,
            "code": p.code,
            "description": p.description,
            "fee_rate": p.fee_rate,
            "daily_withdrawal_limit": p.daily_withdrawal_limit,
            "is_active": p.is_active,
            "admin_count": admin_count.scalar(),
            "created_at": p.created_at.isoformat(),
        })
    
    return {
        "partners": partner_data,
        "page": page,
        "limit": limit
    }


@router.post("")
async def create_partner(
    request: CreatePartnerRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """
    파트너 생성
    
    Super Admin 전용
    """
    # 코드 중복 확인
    result = await session.execute(
        select(Partner).where(Partner.code == request.code)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Partner code already exists")
    
    # API 키 생성
    api_key = secrets.token_urlsafe(32)
    api_secret = secrets.token_urlsafe(48)
    api_secret_hash = hash_password(api_secret)
    
    # 파트너 생성
    partner = Partner(
        name=request.name,
        code=request.code.upper(),
        description=request.description,
        api_key=api_key,
        api_secret_hash=api_secret_hash,
        webhook_url=request.webhook_url,
        fee_rate=request.fee_rate,
        daily_withdrawal_limit=request.daily_withdrawal_limit,
    )
    session.add(partner)
    
    # 감사 로그
    ip = get_client_ip(req)
    audit_log = AuditLog(
        admin_id=int(admin["sub"]),
        action="create_partner",
        resource_type="partner",
        resource_id=request.code,
        ip_address=ip
    )
    session.add(audit_log)
    
    await session.commit()
    await session.refresh(partner)
    
    return {
        "partner_id": partner.partner_id,
        "name": partner.name,
        "code": partner.code,
        "api_key": api_key,
        "api_secret": api_secret,  # 생성 시에만 반환
        "message": "Partner created. Please save the API secret securely."
    }


@router.get("/{partner_id}")
async def get_partner(
    partner_id: int,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    파트너 상세 조회
    
    - Super Admin: 모든 파트너 조회 가능
    - Partner Admin/Staff: 자신의 파트너만 조회 가능
    """
    admin_role = AdminRole(admin["role"])
    
    # 권한 확인
    if admin_role != AdminRole.SUPER_ADMIN:
        if admin.get("partner_id") != partner_id:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    result = await session.execute(
        select(Partner).where(Partner.partner_id == partner_id)
    )
    partner = result.scalar_one_or_none()
    
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # 관리자 목록
    result = await session.execute(
        select(Admin).where(Admin.partner_id == partner_id)
    )
    admins = result.scalars().all()
    
    return {
        "partner_id": partner.partner_id,
        "name": partner.name,
        "code": partner.code,
        "description": partner.description,
        "api_key": partner.api_key,
        "webhook_url": partner.webhook_url,
        "fee_rate": partner.fee_rate,
        "daily_withdrawal_limit": partner.daily_withdrawal_limit,
        "is_active": partner.is_active,
        "created_at": partner.created_at.isoformat(),
        "updated_at": partner.updated_at.isoformat() if partner.updated_at else None,
        "admins": [
            {
                "admin_id": a.admin_id,
                "username": a.username,
                "email": a.email,
                "role": a.role.value,
                "is_active": a.is_active,
            }
            for a in admins
        ]
    }


@router.patch("/{partner_id}")
async def update_partner(
    partner_id: int,
    request: UpdatePartnerRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """
    파트너 수정
    
    Super Admin 전용
    """
    result = await session.execute(
        select(Partner).where(Partner.partner_id == partner_id)
    )
    partner = result.scalar_one_or_none()
    
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # 수정
    if request.name is not None:
        partner.name = request.name
    if request.description is not None:
        partner.description = request.description
    if request.webhook_url is not None:
        partner.webhook_url = request.webhook_url
    if request.fee_rate is not None:
        partner.fee_rate = request.fee_rate
    if request.daily_withdrawal_limit is not None:
        partner.daily_withdrawal_limit = request.daily_withdrawal_limit
    if request.is_active is not None:
        partner.is_active = request.is_active
    
    # 감사 로그
    ip = get_client_ip(req)
    audit_log = AuditLog(
        admin_id=int(admin["sub"]),
        action="update_partner",
        resource_type="partner",
        resource_id=str(partner_id),
        ip_address=ip
    )
    session.add(audit_log)
    
    await session.commit()
    
    return {"message": "Partner updated successfully"}


@router.post("/{partner_id}/regenerate-api-secret")
async def regenerate_api_secret(
    partner_id: int,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """
    API Secret 재발급
    
    Super Admin 전용
    """
    result = await session.execute(
        select(Partner).where(Partner.partner_id == partner_id)
    )
    partner = result.scalar_one_or_none()
    
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # 새 API Secret 생성
    api_secret = secrets.token_urlsafe(48)
    partner.api_secret_hash = hash_password(api_secret)
    
    # 감사 로그
    ip = get_client_ip(req)
    audit_log = AuditLog(
        admin_id=int(admin["sub"]),
        action="regenerate_api_secret",
        resource_type="partner",
        resource_id=str(partner_id),
        ip_address=ip
    )
    session.add(audit_log)
    
    await session.commit()
    
    return {
        "api_key": partner.api_key,
        "api_secret": api_secret,
        "message": "API secret regenerated. Please save it securely."
    }


@router.delete("/{partner_id}")
async def delete_partner(
    partner_id: int,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """
    파트너 삭제 (비활성화)
    
    Super Admin 전용
    """
    result = await session.execute(
        select(Partner).where(Partner.partner_id == partner_id)
    )
    partner = result.scalar_one_or_none()
    
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # 비활성화 (소프트 삭제)
    partner.is_active = False
    
    # 해당 파트너의 모든 관리자 비활성화
    result = await session.execute(
        select(Admin).where(Admin.partner_id == partner_id)
    )
    admins = result.scalars().all()
    for a in admins:
        a.is_active = False
    
    # 감사 로그
    ip = get_client_ip(req)
    audit_log = AuditLog(
        admin_id=int(admin["sub"]),
        action="delete_partner",
        resource_type="partner",
        resource_id=str(partner_id),
        ip_address=ip
    )
    session.add(audit_log)
    
    await session.commit()
    
    return {"message": "Partner deleted successfully"}
