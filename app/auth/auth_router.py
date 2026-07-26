"""
인증 API 라우터
- 로그인/로그아웃
- 토큰 갱신
- 비밀번호 변경
- 관리자 관리
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db import get_session
from app.db.admin_models import Admin, Partner, AdminRole, AuditLog
from app.auth.auth_service import (
    AuthService,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
    CreateAdminRequest,
    get_current_admin,
    require_permission,
    require_role,
    get_client_ip,
    Permission,
    hash_password,
    generate_totp_secret,
    get_totp_uri,
    verify_totp,
    generate_backup_codes
)


router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Rate Limiter 설정
limiter = Limiter(key_func=get_remote_address)


# ==========================================
# 인증 엔드포인트
# ==========================================

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")  # 분당 5회 제한 (브루트포스 방지)
async def login(
    request: Request,
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    로그인

    - 이메일 또는 사용자명으로 로그인
    - 2FA 활성화 시 totp_code 필요
    - Rate Limit: 분당 5회
    """
    ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    return await AuthService.login(
        session=session,
        request=login_data,
        ip_address=ip,
        user_agent=user_agent
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")  # 분당 10회 제한 (토큰 탈취 악용 방지)
async def refresh_token(
    request: RefreshTokenRequest,
    req: Request,
    session: AsyncSession = Depends(get_session)
):
    """토큰 갱신 - Rate Limit: 분당 10회"""
    ip = get_client_ip(req)
    
    return await AuthService.refresh_token(
        session=session,
        refresh_token=request.refresh_token,
        ip_address=ip
    )


@router.post("/logout")
async def logout(
    req: Request,
    refresh_token: Optional[str] = None,
    logout_all: bool = False,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    로그아웃
    
    - refresh_token: 특정 세션만 로그아웃
    - logout_all: 모든 세션 로그아웃
    """
    ip = get_client_ip(req)
    
    return await AuthService.logout(
        session=session,
        admin_id=int(admin["sub"]),
        refresh_token=refresh_token,
        ip_address=ip,
        logout_all=logout_all
    )


@router.post("/change-password")
@limiter.limit("3/minute")  # 분당 3회 제한 (브루트포스 방지)
async def change_password(
    request: ChangePasswordRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """비밀번호 변경 - Rate Limit: 분당 3회"""
    ip = get_client_ip(req)
    
    return await AuthService.change_password(
        session=session,
        admin_id=int(admin["sub"]),
        current_password=request.current_password,
        new_password=request.new_password,
        ip_address=ip
    )


@router.get("/me")
async def get_me(
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """현재 로그인한 관리자 정보"""
    result = await session.execute(
        select(Admin).where(Admin.admin_id == int(admin["sub"]))
    )
    db_admin = result.scalar_one_or_none()

    if not db_admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    partner_info = None
    if db_admin.partner_id:
        result = await session.execute(
            select(Partner).where(Partner.partner_id == db_admin.partner_id)
        )
        partner = result.scalar_one_or_none()
        if partner:
            partner_info = {
                "partner_id": partner.partner_id,
                "name": partner.name,
                "code": partner.code
            }

    return {
        "admin_id": db_admin.admin_id,
        "email": db_admin.email,
        "username": db_admin.username,
        "full_name": db_admin.full_name,
        "role": db_admin.role.value,
        "partner": partner_info,
        "permissions": [p.value for p in db_admin.get_permissions()],
        "is_2fa_enabled": db_admin.is_2fa_enabled,
        "last_login_at": db_admin.last_login_at.isoformat() if db_admin.last_login_at else None,
        "created_at": db_admin.created_at.isoformat()
    }


# ==========================================
# 2FA 관리 엔드포인트
# ==========================================

@router.post("/2fa/setup")
async def setup_2fa(
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    2FA 설정 시작

    - TOTP 시크릿 및 QR 코드 URI 반환
    - 아직 활성화되지 않음 (verify 필요)
    """
    import json

    result = await session.execute(
        select(Admin).where(Admin.admin_id == int(admin["sub"]))
    )
    db_admin = result.scalar_one_or_none()

    if not db_admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    if db_admin.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")

    # 새 TOTP 시크릿 생성
    totp_secret = generate_totp_secret()
    db_admin.totp_secret = totp_secret

    # 백업 코드 생성
    plain_codes, hashed_codes = generate_backup_codes(10)
    db_admin.totp_backup_codes = json.dumps(hashed_codes)

    await session.commit()

    # QR 코드 URI 생성
    identifier = db_admin.email or db_admin.username
    totp_uri = get_totp_uri(totp_secret, identifier)

    return {
        "totp_secret": totp_secret,
        "totp_uri": totp_uri,
        "backup_codes": plain_codes,
        "message": "2FA 설정을 완료하려면 /2fa/verify 엔드포인트에서 TOTP 코드를 확인하세요."
    }


@router.post("/2fa/verify")
@limiter.limit("5/minute")  # 분당 5회 제한 (2FA 우회 시도 방지)
async def verify_2fa(
    totp_code: str,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    2FA 활성화 완료 - Rate Limit: 분당 5회

    - 설정된 TOTP 시크릿으로 코드 검증
    - 성공 시 2FA 활성화
    """
    result = await session.execute(
        select(Admin).where(Admin.admin_id == int(admin["sub"]))
    )
    db_admin = result.scalar_one_or_none()

    if not db_admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    if db_admin.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")

    if not db_admin.totp_secret:
        raise HTTPException(status_code=400, detail="2FA setup not started. Call /2fa/setup first.")

    # TOTP 코드 검증
    if not verify_totp(db_admin.totp_secret, totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # 2FA 활성화
    db_admin.is_2fa_enabled = True

    # 감사 로그
    ip = get_client_ip(req)
    audit_log = AuditLog(
        admin_id=db_admin.admin_id,
        action="2fa_enabled",
        ip_address=ip
    )
    session.add(audit_log)

    await session.commit()

    return {"message": "2FA has been enabled successfully"}


@router.post("/2fa/disable")
@limiter.limit("3/minute")  # 분당 3회 제한 (2FA 비활성화 공격 방지)
async def disable_2fa(
    password: str,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    2FA 비활성화 - Rate Limit: 분당 3회

    - 비밀번호 확인 필요
    """
    from app.auth.auth_service import verify_password

    result = await session.execute(
        select(Admin).where(Admin.admin_id == int(admin["sub"]))
    )
    db_admin = result.scalar_one_or_none()

    if not db_admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    if not db_admin.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled")

    # 비밀번호 확인
    if not verify_password(password, db_admin.password_hash):
        raise HTTPException(status_code=400, detail="Invalid password")

    # 2FA 비활성화
    db_admin.is_2fa_enabled = False
    db_admin.totp_secret = None
    db_admin.totp_backup_codes = None

    # 감사 로그
    ip = get_client_ip(req)
    audit_log = AuditLog(
        admin_id=db_admin.admin_id,
        action="2fa_disabled",
        ip_address=ip
    )
    session.add(audit_log)

    await session.commit()

    return {"message": "2FA has been disabled"}


@router.post("/2fa/regenerate-backup-codes")
async def regenerate_backup_codes(
    totp_code: str,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    백업 코드 재생성

    - TOTP 코드 확인 필요
    - 기존 백업 코드 모두 무효화
    """
    import json

    result = await session.execute(
        select(Admin).where(Admin.admin_id == int(admin["sub"]))
    )
    db_admin = result.scalar_one_or_none()

    if not db_admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    if not db_admin.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled")

    # TOTP 코드 검증
    if not verify_totp(db_admin.totp_secret, totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # 새 백업 코드 생성
    plain_codes, hashed_codes = generate_backup_codes(10)
    db_admin.totp_backup_codes = json.dumps(hashed_codes)

    # 감사 로그
    ip = get_client_ip(req)
    audit_log = AuditLog(
        admin_id=db_admin.admin_id,
        action="backup_codes_regenerated",
        ip_address=ip
    )
    session.add(audit_log)

    await session.commit()

    return {
        "backup_codes": plain_codes,
        "message": "New backup codes generated. Previous codes are now invalid."
    }


# ==========================================
# 파트너(그룹) 관리 엔드포인트
# ==========================================

@router.get("/partners")
async def list_partners(
    page: int = 1,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    파트너(그룹) 목록 조회
    
    - Super Admin: 모든 파트너 조회
    - Partner Admin: 자신의 파트너만 조회
    - Staff: 자신의 파트너만 조회
    """
    admin_role = AdminRole(admin["role"])
    
    query = select(Partner).where(Partner.is_active == True)
    
    # Super Admin이 아니면 자신의 파트너만 조회
    if admin_role != AdminRole.SUPER_ADMIN:
        if admin.get("partner_id"):
            query = query.where(Partner.partner_id == admin["partner_id"])
        else:
            # 파트너가 없는 경우 빈 결과 반환
            return {"partners": [], "page": page, "limit": limit}
    
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    partners = result.scalars().all()
    
    return {
        "partners": [
            {
                "partner_id": p.partner_id,
                "name": p.name,
                "code": p.code,
                "description": p.description,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat()
            }
            for p in partners
        ],
        "page": page,
        "limit": limit
    }


@router.post("/partners")
async def create_partner(
    name: str,
    code: str,
    description: str = None,
    req: Request = None,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """파트너(그룹) 생성 - Super Admin 전용"""
    import secrets
    
    # 중복 코드 확인
    result = await session.execute(
        select(Partner).where(Partner.code == code)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Partner code already exists")
    
    # API 키 생성
    api_key = secrets.token_urlsafe(32)
    api_secret = secrets.token_urlsafe(48)
    
    from app.auth.auth_service import hash_password
    
    new_partner = Partner(
        name=name,
        code=code,
        description=description,
        api_key=api_key,
        api_secret_hash=hash_password(api_secret)
    )
    session.add(new_partner)
    
    # 감사 로그
    ip = get_client_ip(req) if req else None
    audit_log = AuditLog(
        admin_id=int(admin["sub"]),
        action="create_partner",
        resource_type="partner",
        resource_id=code,
        ip_address=ip
    )
    session.add(audit_log)
    
    await session.commit()
    await session.refresh(new_partner)
    
    return {
        "partner_id": new_partner.partner_id,
        "name": new_partner.name,
        "code": new_partner.code,
        "api_key": api_key,
        "api_secret": api_secret  # 생성 시에만 반환
    }


# ==========================================
# 관리자 관리 엔드포인트
# ==========================================

@router.post("/admins")
@limiter.limit("10/minute")  # 분당 10회 제한 (계정 대량 생성 방지)
async def create_admin(
    request: CreateAdminRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission(Permission.MANAGE_PARTNERS))
):
    """
    관리자 생성 - Rate Limit: 분당 10회

    - Super Admin: 모든 역할 생성 가능
    - Partner Admin: 자신의 파트너 내 Staff만 생성 가능
    """
    ip = get_client_ip(req)
    
    return await AuthService.create_admin(
        session=session,
        creator_id=int(admin["sub"]),
        request=request,
        ip_address=ip
    )


@router.get("/admins")
async def list_admins(
    partner_id: Optional[int] = None,
    role: Optional[AdminRole] = None,
    page: int = 1,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """
    관리자 목록 조회
    
    - Super Admin: 모든 관리자 조회 가능
    - Partner Admin: 자신의 파트너 내 관리자만 조회
    - Staff: 조회 불가
    """
    admin_role = AdminRole(admin["role"])
    
    if admin_role == AdminRole.PARTNER_STAFF:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    query = select(Admin)
    
    # Partner Admin은 자신의 파트너만 조회 + Super Admin은 볼 수 없음
    if admin_role == AdminRole.PARTNER_ADMIN:
        query = query.where(
            and_(
                Admin.partner_id == admin["partner_id"],
                Admin.role != AdminRole.SUPER_ADMIN
            )
        )
    elif partner_id:
        query = query.where(Admin.partner_id == partner_id)
    
    if role:
        query = query.where(Admin.role == role)
    
    # 페이지네이션
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    admins = result.scalars().all()
    
    return {
        "admins": [
            {
                "admin_id": a.admin_id,
                "email": a.email,
                "username": a.username,
                "full_name": a.full_name,
                "role": a.role.value,
                "partner_id": a.partner_id,
                "is_active": a.is_active,
                "last_login_at": a.last_login_at.isoformat() if a.last_login_at else None,
                "created_at": a.created_at.isoformat()
            }
            for a in admins
        ],
        "page": page,
        "limit": limit
    }


@router.get("/admins/{admin_id}")
async def get_admin(
    admin_id: int,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """관리자 상세 조회"""
    result = await session.execute(
        select(Admin).where(Admin.admin_id == admin_id)
    )
    target_admin = result.scalar_one_or_none()
    
    if not target_admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # 권한 확인
    admin_role = AdminRole(admin["role"])
    if admin_role == AdminRole.PARTNER_STAFF:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if admin_role == AdminRole.PARTNER_ADMIN:
        if target_admin.partner_id != admin["partner_id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    return {
        "admin_id": target_admin.admin_id,
        "email": target_admin.email,
        "username": target_admin.username,
        "full_name": target_admin.full_name,
        "phone": target_admin.phone,
        "role": target_admin.role.value,
        "partner_id": target_admin.partner_id,
        "is_active": target_admin.is_active,
        "is_2fa_enabled": target_admin.is_2fa_enabled,
        "last_login_at": target_admin.last_login_at.isoformat() if target_admin.last_login_at else None,
        "last_login_ip": target_admin.last_login_ip,
        "created_at": target_admin.created_at.isoformat(),
        "created_by": target_admin.created_by
    }


@router.patch("/admins/{admin_id}")
async def update_admin(
    admin_id: int,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
    is_active: Optional[bool] = None,
    role: Optional[AdminRole] = None,
    partner_id: Optional[int] = None,
    password: Optional[str] = None,
    req: Request = None,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(get_current_admin)
):
    """관리자 수정"""
    result = await session.execute(
        select(Admin).where(Admin.admin_id == admin_id)
    )
    target_admin = result.scalar_one_or_none()
    
    if not target_admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # 권한 확인
    admin_role = AdminRole(admin["role"])
    
    if admin_role == AdminRole.PARTNER_STAFF:
        # Staff는 자신의 프로필만 수정 가능
        if admin_id != int(admin["sub"]):
            raise HTTPException(status_code=403, detail="Not authorized")
        # 역할, 활성화 상태 변경 불가
        if role is not None or is_active is not None or partner_id is not None:
            raise HTTPException(status_code=403, detail="Cannot modify role or status")
    
    elif admin_role == AdminRole.PARTNER_ADMIN:
        # Partner Admin은 자신의 파트너 내에서만 수정 가능
        if target_admin.partner_id != admin["partner_id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        # Super Admin이나 Partner Admin의 역할 변경 불가
        if role and role in [AdminRole.SUPER_ADMIN, AdminRole.PARTNER_ADMIN]:
            raise HTTPException(status_code=403, detail="Cannot assign this role")
        # 파트너 변경 불가
        if partner_id is not None:
             raise HTTPException(status_code=403, detail="Cannot change partner")
    
    # 수정
    if full_name is not None:
        target_admin.full_name = full_name
    if phone is not None:
        target_admin.phone = phone
    if is_active is not None and admin_role != AdminRole.PARTNER_STAFF:
        target_admin.is_active = is_active
    if role is not None and admin_role == AdminRole.SUPER_ADMIN:
        target_admin.role = role
    if partner_id is not None and admin_role == AdminRole.SUPER_ADMIN:
        target_admin.partner_id = partner_id
    if password is not None:
        target_admin.password_hash = hash_password(password)
    
    # 감사 로그
    ip = get_client_ip(req) if req else None
    audit_log = AuditLog(
        admin_id=int(admin["sub"]),
        action="update_admin",
        resource_type="admin",
        resource_id=str(admin_id),
        ip_address=ip
    )
    session.add(audit_log)
    
    await session.commit()
    
    return {"message": "Admin updated successfully"}


@router.delete("/admins/{admin_id}")
async def delete_admin(
    admin_id: int,
    req: Request,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN))
):
    """관리자 삭제 (Super Admin 전용)"""
    if admin_id == int(admin["sub"]):
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    result = await session.execute(
        select(Admin).where(Admin.admin_id == admin_id)
    )
    target_admin = result.scalar_one_or_none()
    
    if not target_admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # 비활성화 처리 (소프트 삭제)
    target_admin.is_active = False
    
    # 감사 로그
    ip = get_client_ip(req)
    audit_log = AuditLog(
        admin_id=int(admin["sub"]),
        action="delete_admin",
        resource_type="admin",
        resource_id=str(admin_id),
        ip_address=ip
    )
    session.add(audit_log)
    
    await session.commit()
    
    return {"message": "Admin deleted successfully"}


# ==========================================
# 감사 로그 엔드포인트
# ==========================================

@router.get("/audit-logs")
async def get_audit_logs(
    admin_id: Optional[int] = None,
    action: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role(AdminRole.SUPER_ADMIN, AdminRole.PARTNER_ADMIN))
):
    """감사 로그 조회"""
    admin_role = AdminRole(admin["role"])
    
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    
    # Partner Admin은 자신의 파트너 내 로그만 조회
    if admin_role == AdminRole.PARTNER_ADMIN:
        partner_admin_ids = await session.execute(
            select(Admin.admin_id).where(Admin.partner_id == admin["partner_id"])
        )
        admin_ids = [row[0] for row in partner_admin_ids.all()]
        query = query.where(AuditLog.admin_id.in_(admin_ids))
    
    if admin_id:
        query = query.where(AuditLog.admin_id == admin_id)
    if action:
        query = query.where(AuditLog.action == action)
    
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await session.execute(query)
    logs = result.scalars().all()
    
    return {
        "logs": [
            {
                "log_id": log.log_id,
                "admin_id": log.admin_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ],
        "page": page,
        "limit": limit
    }
