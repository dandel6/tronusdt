"""
JWT 인증 모듈
- 로그인/로그아웃
- 액세스 토큰 & 리프레시 토큰
- 비밀번호 해싱
- 2FA 지원
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

import jwt
import bcrypt
import pyotp
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db.admin_models import Admin, AdminSession, AuditLog, AdminRole, Permission
from app.config import settings


# ==========================================
# 설정
# ==========================================

class AuthConfig:
    """인증 설정 - 환경변수에서 로드"""

    @property
    def SECRET_KEY(self) -> str:
        if not settings.jwt_secret_key:
            raise ValueError("JWT_SECRET_KEY environment variable is required")
        return settings.jwt_secret_key

    @property
    def ALGORITHM(self) -> str:
        return settings.jwt_algorithm

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return settings.access_token_expire_minutes

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        return settings.refresh_token_expire_days

    @property
    def MAX_FAILED_ATTEMPTS(self) -> int:
        return settings.max_failed_attempts

    @property
    def LOCKOUT_DURATION_MINUTES(self) -> int:
        return settings.lockout_duration_minutes

    @property
    def MIN_PASSWORD_LENGTH(self) -> int:
        return settings.min_password_length


auth_config = AuthConfig()


# ==========================================
# Pydantic 스키마
# ==========================================

class LoginRequest(BaseModel):
    """로그인 요청"""
    email: str
    password: str
    totp_code: Optional[str] = None


class TokenResponse(BaseModel):
    """토큰 응답"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    admin: Dict[str, Any]


class RefreshTokenRequest(BaseModel):
    """토큰 갱신 요청"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """비밀번호 변경 요청"""
    current_password: str
    new_password: str


class CreateAdminRequest(BaseModel):
    """관리자 생성 요청"""
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    role: AdminRole = AdminRole.PARTNER_STAFF
    partner_id: Optional[int] = None


# ==========================================
# 유틸리티 함수
# ==========================================

def hash_password(password: str) -> str:
    """비밀번호 해싱"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """비밀번호 검증"""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def hash_token(token: str) -> str:
    """토큰 해싱 (리프레시 토큰 저장용)"""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_access_token(admin: Admin) -> Tuple[str, int]:
    """액세스 토큰 생성"""
    expires_delta = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.utcnow() + expires_delta
    
    payload = {
        "sub": str(admin.admin_id),
        "email": admin.email,
        "username": admin.username,
        "role": admin.role.value,
        "partner_id": admin.partner_id,
        "permissions": [p.value for p in admin.get_permissions()],
        "type": "access",
        "exp": expires_at,
        "iat": datetime.utcnow(),
    }
    
    token = jwt.encode(payload, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)
    return token, int(expires_delta.total_seconds())


def generate_refresh_token() -> Tuple[str, datetime]:
    """리프레시 토큰 생성"""
    token = secrets.token_urlsafe(64)
    expires_at = datetime.utcnow() + timedelta(days=auth_config.REFRESH_TOKEN_EXPIRE_DAYS)
    return token, expires_at


def decode_token(token: str) -> Dict[str, Any]:
    """토큰 디코딩"""
    try:
        payload = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def generate_totp_secret() -> str:
    """TOTP 시크릿 생성"""
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    """TOTP 코드 검증"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)


def get_totp_uri(secret: str, email: str, issuer: str = "TRON Gateway") -> str:
    """TOTP URI 생성 (QR 코드용)"""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


# ==========================================
# 인증 서비스
# ==========================================

class AuthService:
    """인증 서비스"""
    
    @staticmethod
    async def login(
        session: AsyncSession,
        request: LoginRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TokenResponse:
        """로그인"""
        # 관리자 조회
        result = await session.execute(
            select(Admin).where(
                or_(Admin.email == request.email, Admin.username == request.email)
            )
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # 계정 잠금 확인
        if admin.locked_until and admin.locked_until > datetime.utcnow():
            remaining = (admin.locked_until - datetime.utcnow()).seconds // 60
            raise HTTPException(
                status_code=423,
                detail=f"Account locked. Try again in {remaining} minutes."
            )
        
        # 비밀번호 검증
        if not verify_password(request.password, admin.password_hash):
            admin.failed_login_attempts += 1

            # 최대 시도 횟수 초과 시 계정 잠금
            if admin.failed_login_attempts >= auth_config.MAX_FAILED_ATTEMPTS:
                admin.locked_until = datetime.utcnow() + timedelta(
                    minutes=auth_config.LOCKOUT_DURATION_MINUTES
                )

            # 실패한 로그인 시도 감사 로그
            failed_audit_log = AuditLog(
                admin_id=admin.admin_id,
                action="login_failed",
                details=f"Failed attempt #{admin.failed_login_attempts}",
                ip_address=ip_address,
                user_agent=user_agent
            )
            session.add(failed_audit_log)

            await session.commit()
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # 계정 활성화 확인
        if not admin.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
        
        # 2FA 확인
        if admin.is_2fa_enabled:
            if not request.totp_code:
                raise HTTPException(
                    status_code=401,
                    detail="2FA code required",
                    headers={"X-2FA-Required": "true"}
                )
            
            if not verify_totp(admin.totp_secret, request.totp_code):
                raise HTTPException(status_code=401, detail="Invalid 2FA code")
        
        # 로그인 성공 - 실패 카운터 초기화
        admin.failed_login_attempts = 0
        admin.locked_until = None
        admin.last_login_at = datetime.utcnow()
        admin.last_login_ip = ip_address
        
        # 토큰 생성
        access_token, expires_in = generate_access_token(admin)
        refresh_token, refresh_expires = generate_refresh_token()
        
        # 세션 저장
        session_id = str(uuid.uuid4())
        admin_session = AdminSession(
            session_id=session_id,
            admin_id=admin.admin_id,
            refresh_token_hash=hash_token(refresh_token),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=refresh_expires
        )
        session.add(admin_session)
        
        # 감사 로그
        audit_log = AuditLog(
            admin_id=admin.admin_id,
            action="login",
            ip_address=ip_address,
            user_agent=user_agent
        )
        session.add(audit_log)
        
        await session.commit()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            admin={
                "admin_id": admin.admin_id,
                "email": admin.email,
                "username": admin.username,
                "full_name": admin.full_name,
                "role": admin.role.value,
                "partner_id": admin.partner_id,
                "permissions": [p.value for p in admin.get_permissions()],
                "is_2fa_enabled": admin.is_2fa_enabled,
            }
        )
    
    @staticmethod
    async def refresh_token(
        session: AsyncSession,
        refresh_token: str,
        ip_address: Optional[str] = None
    ) -> TokenResponse:
        """토큰 갱신"""
        token_hash = hash_token(refresh_token)
        
        # 세션 조회
        result = await session.execute(
            select(AdminSession).where(
                and_(
                    AdminSession.refresh_token_hash == token_hash,
                    AdminSession.is_revoked == False,
                    AdminSession.expires_at > datetime.utcnow()
                )
            )
        )
        admin_session = result.scalar_one_or_none()
        
        if not admin_session:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # 관리자 조회
        result = await session.execute(
            select(Admin).where(Admin.admin_id == admin_session.admin_id)
        )
        admin = result.scalar_one_or_none()
        
        if not admin or not admin.is_active:
            raise HTTPException(status_code=401, detail="Account not found or disabled")
        
        # 기존 세션 무효화
        admin_session.is_revoked = True
        admin_session.revoked_at = datetime.utcnow()
        
        # 새 토큰 생성
        access_token, expires_in = generate_access_token(admin)
        new_refresh_token, refresh_expires = generate_refresh_token()
        
        # 새 세션 생성
        new_session = AdminSession(
            session_id=str(uuid.uuid4()),
            admin_id=admin.admin_id,
            refresh_token_hash=hash_token(new_refresh_token),
            user_agent=admin_session.user_agent,
            ip_address=ip_address,
            expires_at=refresh_expires
        )
        session.add(new_session)
        
        await session.commit()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=expires_in,
            admin={
                "admin_id": admin.admin_id,
                "email": admin.email,
                "username": admin.username,
                "full_name": admin.full_name,
                "role": admin.role.value,
                "partner_id": admin.partner_id,
                "permissions": [p.value for p in admin.get_permissions()],
            }
        )
    
    @staticmethod
    async def logout(
        session: AsyncSession,
        admin_id: int,
        refresh_token: Optional[str] = None,
        ip_address: Optional[str] = None,
        logout_all: bool = False
    ):
        """로그아웃"""
        if logout_all:
            # 모든 세션 무효화
            result = await session.execute(
                select(AdminSession).where(
                    and_(
                        AdminSession.admin_id == admin_id,
                        AdminSession.is_revoked == False
                    )
                )
            )
            sessions = result.scalars().all()
            for s in sessions:
                s.is_revoked = True
                s.revoked_at = datetime.utcnow()
        elif refresh_token:
            # 특정 세션만 무효화
            token_hash = hash_token(refresh_token)
            result = await session.execute(
                select(AdminSession).where(
                    AdminSession.refresh_token_hash == token_hash
                )
            )
            admin_session = result.scalar_one_or_none()
            if admin_session:
                admin_session.is_revoked = True
                admin_session.revoked_at = datetime.utcnow()
        
        # 감사 로그
        audit_log = AuditLog(
            admin_id=admin_id,
            action="logout" if not logout_all else "logout_all",
            ip_address=ip_address
        )
        session.add(audit_log)
        
        await session.commit()
        return {"message": "Logged out successfully"}
    
    @staticmethod
    async def change_password(
        session: AsyncSession,
        admin_id: int,
        current_password: str,
        new_password: str,
        ip_address: Optional[str] = None
    ):
        """비밀번호 변경"""
        # 관리자 조회
        result = await session.execute(
            select(Admin).where(Admin.admin_id == admin_id)
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        # 현재 비밀번호 확인
        if not verify_password(current_password, admin.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # 비밀번호 정책 확인
        if len(new_password) < auth_config.MIN_PASSWORD_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Password must be at least {auth_config.MIN_PASSWORD_LENGTH} characters"
            )
        
        # 비밀번호 변경
        admin.password_hash = hash_password(new_password)
        
        # 모든 세션 무효화 (선택적)
        result = await session.execute(
            select(AdminSession).where(
                and_(
                    AdminSession.admin_id == admin_id,
                    AdminSession.is_revoked == False
                )
            )
        )
        sessions = result.scalars().all()
        for s in sessions:
            s.is_revoked = True
            s.revoked_at = datetime.utcnow()
        
        # 감사 로그
        audit_log = AuditLog(
            admin_id=admin_id,
            action="change_password",
            ip_address=ip_address
        )
        session.add(audit_log)
        
        await session.commit()
        return {"message": "Password changed successfully"}
    
    @staticmethod
    async def create_admin(
        session: AsyncSession,
        creator_id: int,
        request: CreateAdminRequest,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """관리자 생성"""
        # 생성자 조회
        result = await session.execute(
            select(Admin).where(Admin.admin_id == creator_id)
        )
        creator = result.scalar_one_or_none()
        
        if not creator:
            raise HTTPException(status_code=403, detail="Creator not found")
        
        # 권한 확인
        if creator.role == AdminRole.PARTNER_STAFF:
            raise HTTPException(status_code=403, detail="Not authorized to create admins")
        
        # Super Admin만 Super Admin/Partner Admin 생성 가능
        if request.role in [AdminRole.SUPER_ADMIN, AdminRole.PARTNER_ADMIN]:
            if creator.role != AdminRole.SUPER_ADMIN:
                raise HTTPException(status_code=403, detail="Only Super Admin can create this role")
        
        # Partner Admin은 자신의 파트너 내에서만 Staff 생성 가능
        if creator.role == AdminRole.PARTNER_ADMIN:
            if request.partner_id and request.partner_id != creator.partner_id:
                raise HTTPException(status_code=403, detail="Can only create staff for your partner")
            request.partner_id = creator.partner_id
        
        # 중복 확인
        result = await session.execute(
            select(Admin).where(
                or_(Admin.email == request.email, Admin.username == request.username)
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email or username already exists")
        
        # 관리자 생성
        new_admin = Admin(
            email=request.email,
            username=request.username,
            password_hash=hash_password(request.password),
            full_name=request.full_name,
            role=request.role,
            partner_id=request.partner_id,
            created_by=creator_id
        )
        session.add(new_admin)
        
        # 감사 로그
        audit_log = AuditLog(
            admin_id=creator_id,
            action="create_admin",
            resource_type="admin",
            resource_id=request.email,
            ip_address=ip_address
        )
        session.add(audit_log)
        
        await session.commit()
        await session.refresh(new_admin)
        
        return {
            "admin_id": new_admin.admin_id,
            "email": new_admin.email,
            "username": new_admin.username,
            "role": new_admin.role.value,
            "partner_id": new_admin.partner_id
        }


# ==========================================
# FastAPI 의존성
# ==========================================

security = HTTPBearer()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """현재 로그인한 관리자 조회"""
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    
    return payload


def require_permission(*permissions: Permission):
    """권한 요구 데코레이터"""
    async def dependency(admin: Dict[str, Any] = Depends(get_current_admin)):
        admin_permissions = admin.get("permissions", [])
        
        for perm in permissions:
            if perm.value not in admin_permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {perm.value}"
                )
        
        return admin
    
    return dependency


def require_role(*roles: AdminRole):
    """역할 요구 데코레이터"""
    async def dependency(admin: Dict[str, Any] = Depends(get_current_admin)):
        admin_role = admin.get("role")
        
        if admin_role not in [r.value for r in roles]:
            raise HTTPException(
                status_code=403,
                detail=f"Role not authorized"
            )
        
        return admin
    
    return dependency


def get_client_ip(request: Request) -> str:
    """클라이언트 IP 주소 조회"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
