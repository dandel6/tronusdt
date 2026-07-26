"""데이터베이스 모델"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Float,
    DateTime, Boolean, ForeignKey, Index, Numeric, Enum as SQLEnum
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from app.config import settings

Base = declarative_base()


class WithdrawalStatus(str, Enum):
    """출금 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class UserWallet(Base):
    """사용자 입금 지갑"""
    __tablename__ = "user_wallets"
    
    user_id = Column(BigInteger, primary_key=True)
    wallet_address = Column(String(34), unique=True, nullable=False, index=True)
    private_key_encrypted = Column(Text, nullable=False)
    derivation_path = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    deposits = relationship("Deposit", back_populates="user")
    withdrawals = relationship("Withdrawal", back_populates="user")
    
    # 인덱스
    __table_args__ = (
        Index('idx_wallet_address', 'wallet_address'),
    )


class Deposit(Base):
    """입금 트랜잭션"""
    __tablename__ = "deposits"
    
    tx_id = Column(String(64), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("user_wallets.user_id"), nullable=False)
    from_address = Column(String(34))
    amount = Column(Numeric(20, 6), nullable=False)  # USDT 6 decimals
    block_timestamp = Column(BigInteger, nullable=False)
    confirmations = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending, confirmed, swept
    swept = Column(Boolean, default=False)
    sweep_tx_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    user = relationship("UserWallet", back_populates="deposits")
    
    # 인덱스
    __table_args__ = (
        Index('idx_deposit_user', 'user_id'),
        Index('idx_deposit_status', 'status'),
        Index('idx_deposit_swept', 'swept'),
    )


class Withdrawal(Base):
    """출금 요청"""
    __tablename__ = "withdrawals"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    withdrawal_id = Column(BigInteger, unique=True, nullable=True)  # 외부 참조용
    user_id = Column(BigInteger, ForeignKey("user_wallets.user_id"), nullable=False)
    to_address = Column(String(34), nullable=False)  # 회원 외부 지갑
    amount = Column(Numeric(20, 6), nullable=False)
    tx_id = Column(String(64), nullable=True)
    status = Column(SQLEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    error_message = Column(Text, nullable=True)

    # 승인/거부 정보 (CLI 전용 기능)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(50), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejected_by = Column(String(50), nullable=True)
    reject_reason = Column(Text, nullable=True)

    # 처리 정보
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processed_by = Column(String(50), nullable=True)

    # 관계
    user = relationship("UserWallet", back_populates="withdrawals")

    # 인덱스
    __table_args__ = (
        Index('idx_withdrawal_user', 'user_id'),
        Index('idx_withdrawal_status', 'status'),
        Index('idx_withdrawal_created', 'created_at'),
    )


class SweepLog(Base):
    """스위핑 로그"""
    __tablename__ = "sweep_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    from_address = Column(String(34), nullable=False)
    to_address = Column(String(34), nullable=False)  # 메인 핫월렛
    amount = Column(Numeric(20, 6), nullable=False)
    tx_id = Column(String(64), nullable=True)
    energy_used = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class EnergyLog(Base):
    """에너지 사용 로그"""
    __tablename__ = "energy_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False)  # stake, unstake, delegate, rental
    amount = Column(Integer, nullable=False)
    cost_trx = Column(Float, default=0.0)
    tx_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemSetting(Base):
    """시스템 설정"""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(50), nullable=True)
    update_reason = Column(Text, nullable=True)


class ColdWalletTransfer(Base):
    """콜드월렛 이체 기록"""
    __tablename__ = "cold_wallet_transfers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    direction = Column(String(20), nullable=False)  # hot_to_cold, cold_to_hot
    amount = Column(Numeric(20, 6), nullable=False)
    tx_id = Column(String(64), nullable=True)
    from_address = Column(String(34), nullable=False)
    to_address = Column(String(34), nullable=False)
    status = Column(String(20), default="pending")  # pending, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(50), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_cold_transfer_direction', 'direction'),
        Index('idx_cold_transfer_created', 'created_at'),
    )


# 데이터베이스 엔진 및 세션
engine = create_async_engine(settings.database_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """데이터베이스 테이블 생성"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database initialized")


async def get_session() -> AsyncSession:
    """세션 생성"""
    async with async_session() as session:
        yield session
