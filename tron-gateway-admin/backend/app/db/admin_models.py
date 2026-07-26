"""
Admin Database Models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.db.base import Base


class AdminRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    PARTNER_ADMIN = "partner_admin"
    PARTNER_STAFF = "partner_staff"


class Partner(Base):
    """Partner (Business) Model"""
    __tablename__ = "partners"
    
    partner_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    api_key = Column(String(64), unique=True, nullable=False, index=True)
    api_secret_hash = Column(String(128), nullable=False)
    
    webhook_url = Column(String(500), nullable=True)
    callback_url = Column(String(500), nullable=True)
    
    fee_rate = Column(Integer, default=100)  # basis points (100 = 1%)
    daily_withdrawal_limit = Column(Integer, default=1000000000000)  # 1M USDT in 6 decimals
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    admins = relationship("Admin", back_populates="partner")


class Admin(Base):
    """Admin User Model"""
    __tablename__ = "admins"
    
    admin_id = Column(Integer, primary_key=True, autoincrement=True)
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    
    full_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    
    role = Column(Enum(AdminRole), nullable=False, default=AdminRole.PARTNER_STAFF)
    partner_id = Column(Integer, ForeignKey("partners.partner_id"), nullable=True)
    
    is_active = Column(Boolean, default=True)
    is_2fa_enabled = Column(Boolean, default=False)
    totp_secret = Column(String(32), nullable=True)
    
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    partner = relationship("Partner", back_populates="admins")
    
    @property
    def permissions(self):
        """Get permissions based on role"""
        if self.role == AdminRole.SUPER_ADMIN:
            return [
                "system_settings",
                "manage_partners",
                "view_all_data",
                "create_wallet",
                "view_wallets",
                "view_deposits",
                "view_withdrawals",
                "request_withdrawal",
                "approve_withdrawal",
                "trigger_sweep",
            ]
        elif self.role == AdminRole.PARTNER_ADMIN:
            return [
                "create_wallet",
                "view_wallets",
                "view_deposits",
                "view_withdrawals",
                "request_withdrawal",
                "approve_withdrawal",
            ]
        else:  # PARTNER_STAFF
            return [
                "view_wallets",
                "view_deposits",
                "view_withdrawals",
            ]


class AdminSession(Base):
    """Admin Session Model for JWT Refresh Tokens"""
    __tablename__ = "admin_sessions"
    
    session_id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey("admins.admin_id"), nullable=False)
    
    refresh_token_hash = Column(String(128), nullable=False, index=True)
    
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    """Audit Log Model"""
    __tablename__ = "audit_logs"
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey("admins.admin_id"), nullable=False)
    
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemConfig(Base):
    """System Configuration Model"""
    __tablename__ = "system_configs"
    
    config_id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("admins.admin_id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("admins.admin_id"), nullable=True)
