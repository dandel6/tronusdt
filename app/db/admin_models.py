"""
관리자 모델 - 3단계 RBAC 시스템
Tier 1: Super Admin (최상위 관리자)
Tier 2: Partner Admin (업체 대표)
Tier 3: Partner Staff (업체 직원, ReadOnly)
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, DateTime, 
    Boolean, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from app.db.models import Base


class AdminRole(str, Enum):
    """관리자 역할"""
    SUPER_ADMIN = "super_admin"      # Tier 1: 최상위 관리자
    PARTNER_ADMIN = "partner_admin"  # Tier 2: 업체 대표
    PARTNER_STAFF = "partner_staff"  # Tier 3: 업체 직원 (ReadOnly)


class Permission(str, Enum):
    """권한 목록"""
    # 시스템 관리
    SYSTEM_SETTINGS = "system_settings"       # 시스템 설정 변경
    MANAGE_PARTNERS = "manage_partners"       # 업체 관리
    VIEW_ALL_DATA = "view_all_data"           # 모든 데이터 조회
    
    # 지갑 관리
    CREATE_WALLET = "create_wallet"           # 지갑 생성
    VIEW_WALLETS = "view_wallets"             # 지갑 조회
    
    # 입출금
    VIEW_DEPOSITS = "view_deposits"           # 입금 조회
    VIEW_WITHDRAWALS = "view_withdrawals"     # 출금 조회
    REQUEST_WITHDRAWAL = "request_withdrawal" # 출금 요청
    APPROVE_WITHDRAWAL = "approve_withdrawal" # 출금 승인
    
    # 스위핑
    TRIGGER_SWEEP = "trigger_sweep"           # 스위핑 실행


# 역할별 기본 권한 매핑
ROLE_PERMISSIONS = {
    AdminRole.SUPER_ADMIN: [
        Permission.SYSTEM_SETTINGS,
        Permission.MANAGE_PARTNERS,
        Permission.VIEW_ALL_DATA,
        Permission.CREATE_WALLET,
        Permission.VIEW_WALLETS,
        Permission.VIEW_DEPOSITS,
        Permission.VIEW_WITHDRAWALS,
        Permission.REQUEST_WITHDRAWAL,
        Permission.APPROVE_WITHDRAWAL,
        Permission.TRIGGER_SWEEP,
    ],
    AdminRole.PARTNER_ADMIN: [
        Permission.CREATE_WALLET,
        Permission.VIEW_WALLETS,
        Permission.VIEW_DEPOSITS,
        Permission.VIEW_WITHDRAWALS,
        Permission.REQUEST_WITHDRAWAL,
        Permission.APPROVE_WITHDRAWAL,
    ],
    AdminRole.PARTNER_STAFF: [
        Permission.VIEW_WALLETS,
        Permission.VIEW_DEPOSITS,
        Permission.VIEW_WITHDRAWALS,
    ],
}


class Partner(Base):
    """
    파트너(업체) 테이블
    각 파트너는 독립적인 사용자 풀을 가짐
    """
    __tablename__ = "partners"
    
    partner_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False, index=True)  # 업체 코드
    description = Column(Text, nullable=True)
    
    # API 설정
    api_key = Column(String(64), unique=True, nullable=False, index=True)
    api_secret_hash = Column(String(128), nullable=False)
    webhook_url = Column(String(500), nullable=True)
    
    # 설정
    fee_rate = Column(Integer, default=100)  # 수수료율 (기본 1%, 10000 = 100%)
    daily_withdrawal_limit = Column(BigInteger, default=10000_000000)  # USDT 6 decimals
    is_active = Column(Boolean, default=True)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    admins = relationship("Admin", back_populates="partner")
    
    __table_args__ = (
        Index('idx_partner_code', 'code'),
        Index('idx_partner_api_key', 'api_key'),
    )


class Admin(Base):
    """
    관리자 테이블
    3단계 RBAC 시스템
    """
    __tablename__ = "admins"
    
    admin_id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    
    # 역할 및 소속
    role = Column(SQLEnum(AdminRole), nullable=False, default=AdminRole.PARTNER_STAFF)
    partner_id = Column(BigInteger, ForeignKey("partners.partner_id"), nullable=True)
    
    # 프로필
    full_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # 보안
    is_active = Column(Boolean, default=True)
    is_2fa_enabled = Column(Boolean, default=False)
    totp_secret = Column(String(32), nullable=True)
    totp_backup_codes = Column(Text, nullable=True)  # JSON 배열: 해시된 백업 코드
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 생성자 추적
    created_by = Column(BigInteger, ForeignKey("admins.admin_id"), nullable=True)
    
    # 관계
    partner = relationship("Partner", back_populates="admins")
    sessions = relationship("AdminSession", back_populates="admin")
    audit_logs = relationship("AuditLog", back_populates="admin", foreign_keys="AuditLog.admin_id")
    
    __table_args__ = (
        Index('idx_admin_email', 'email'),
        Index('idx_admin_username', 'username'),
        Index('idx_admin_partner', 'partner_id'),
    )
    
    def has_permission(self, permission: Permission) -> bool:
        """권한 확인"""
        if not self.is_active:
            return False
        return permission in ROLE_PERMISSIONS.get(self.role, [])
    
    def get_permissions(self) -> List[Permission]:
        """모든 권한 조회"""
        return ROLE_PERMISSIONS.get(self.role, [])
    
    @property
    def is_super_admin(self) -> bool:
        return self.role == AdminRole.SUPER_ADMIN
    
    @property
    def is_partner_admin(self) -> bool:
        return self.role == AdminRole.PARTNER_ADMIN
    
    @property
    def can_manage_users(self) -> bool:
        """사용자 관리 권한 (Tier 1, 2만)"""
        return self.role in [AdminRole.SUPER_ADMIN, AdminRole.PARTNER_ADMIN]


class AdminSession(Base):
    """
    관리자 세션 테이블
    JWT 리프레시 토큰 관리
    """
    __tablename__ = "admin_sessions"
    
    session_id = Column(String(36), primary_key=True)  # UUID
    admin_id = Column(BigInteger, ForeignKey("admins.admin_id"), nullable=False)
    
    refresh_token_hash = Column(String(128), nullable=False)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)
    
    # 관계
    admin = relationship("Admin", back_populates="sessions")
    
    __table_args__ = (
        Index('idx_session_admin', 'admin_id'),
        Index('idx_session_expires', 'expires_at'),
    )


class AuditLog(Base):
    """
    감사 로그 테이블
    모든 중요 작업 기록
    """
    __tablename__ = "audit_logs"
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(BigInteger, ForeignKey("admins.admin_id"), nullable=False)
    
    action = Column(String(100), nullable=False)  # login, logout, create_wallet, approve_withdrawal 등
    resource_type = Column(String(50), nullable=True)  # wallet, withdrawal, partner 등
    resource_id = Column(String(100), nullable=True)
    
    details = Column(Text, nullable=True)  # JSON 상세 정보
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 관계
    admin = relationship("Admin", back_populates="audit_logs", foreign_keys=[admin_id])
    
    __table_args__ = (
        Index('idx_audit_admin', 'admin_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_created', 'created_at'),
    )


class SystemConfig(Base):
    """
    시스템 설정 테이블
    Super Admin만 수정 가능
    """
    __tablename__ = "system_configs"
    
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    
    # 설정 카테고리
    category = Column(String(50), default="general")  # general, fee, sweep, security
    
    # 접근 제어
    is_sensitive = Column(Boolean, default=False)  # 민감 정보 여부
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(BigInteger, ForeignKey("admins.admin_id"), nullable=True)
    
    __table_args__ = (
        Index('idx_config_category', 'category'),
    )
