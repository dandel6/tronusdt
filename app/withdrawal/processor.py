"""
출금 처리
메인 핫월렛 → 회원 외부 지갑
"""
import asyncio
import hashlib
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session, Withdrawal
from app.wallet import tron_client

logger = logging.getLogger(__name__)


class WithdrawalProcessor:
    """
    출금 처리기
    - 메인 핫월렛에서 회원 외부 지갑으로 전송
    - 일일/단건 한도 검증
    - 배치 처리 지원
    - 이중 출금 방지 (DB 잠금 + Idempotency Key)
    """

    # 최소 출금액 (수수료 고려)
    MIN_WITHDRAWAL = Decimal("1.0")

    def __init__(self):
        self._processing_lock = asyncio.Lock()  # 메모리 락 (단일 인스턴스용)
        self.main_wallet_key = settings.main_wallet_private_key
        self.max_daily = Decimal(str(settings.max_daily_withdrawal))
        self.max_single = Decimal(str(settings.max_single_withdrawal))
    
    @staticmethod
    def _generate_idempotency_key(user_id: int, to_address: str, amount: Decimal, timestamp_minute: int) -> str:
        """
        Idempotency Key 생성 (1분 내 동일 요청 방지)
        """
        data = f"{user_id}:{to_address}:{amount}:{timestamp_minute}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    async def create_withdrawal(
        self,
        session: AsyncSession,
        user_id: int,
        to_address: str,
        amount: Decimal,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        출금 요청 생성

        Args:
            user_id: 사용자 ID
            to_address: 회원 외부 TRON 지갑 주소
            amount: 출금액 (USDT)
            idempotency_key: 중복 요청 방지 키 (선택)
        """
        # 주소 유효성 검사
        if not tron_client.is_valid_address(to_address):
            raise ValueError("유효하지 않은 TRON 주소입니다")

        amount = Decimal(str(amount))

        # 금액 유효성 검사 강화
        if amount <= 0:
            raise ValueError("출금액은 0보다 커야 합니다")

        if amount < self.MIN_WITHDRAWAL:
            raise ValueError(f"최소 출금액은 {self.MIN_WITHDRAWAL} USDT입니다")

        # 단건 한도 검사
        if amount > self.max_single:
            raise ValueError(f"단건 출금 한도 초과: 최대 {self.max_single} USDT")

        # Idempotency Key 생성 (1분 윈도우)
        current_minute = int(datetime.utcnow().timestamp() // 60)
        if not idempotency_key:
            idempotency_key = self._generate_idempotency_key(
                user_id, to_address, amount, current_minute
            )

        # 중복 요청 확인 (최근 5분 내 동일 키)
        five_minutes_ago = datetime.utcnow().replace(second=0, microsecond=0)
        result = await session.execute(
            select(Withdrawal).where(
                and_(
                    Withdrawal.user_id == user_id,
                    Withdrawal.to_address == to_address,
                    Withdrawal.amount == amount,
                    Withdrawal.created_at >= five_minutes_ago,
                    Withdrawal.status.in_(["pending", "processing"])
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.warning(
                f"중복 출금 요청 감지: user_id={user_id}, amount={amount}, "
                f"existing_id={existing.withdrawal_id}"
            )
            # 기존 요청 정보 반환 (새로 생성하지 않음)
            return {
                "withdrawal_id": existing.withdrawal_id,
                "user_id": user_id,
                "to_address": to_address,
                "amount": float(amount),
                "status": existing.status,
                "duplicate": True
            }

        # 일일 한도 검사
        today = date.today()
        result = await session.execute(
            select(func.sum(Withdrawal.amount))
            .where(
                and_(
                    Withdrawal.user_id == user_id,
                    Withdrawal.status.in_(["pending", "processing", "completed"]),
                    func.date(Withdrawal.created_at) == today
                )
            )
        )
        daily_total = result.scalar() or Decimal(0)

        if daily_total + amount > self.max_daily:
            remaining = self.max_daily - daily_total
            raise ValueError(f"일일 출금 한도 초과: 잔여 {remaining} USDT")

        # 출금 요청 생성
        withdrawal = Withdrawal(
            user_id=user_id,
            to_address=to_address,
            amount=amount,
            status="pending"
        )
        session.add(withdrawal)
        await session.commit()
        await session.refresh(withdrawal)

        logger.info(f"출금 요청 생성: #{withdrawal.withdrawal_id}, user={user_id}, amount={amount}")

        return {
            "withdrawal_id": withdrawal.withdrawal_id,
            "user_id": user_id,
            "to_address": to_address,
            "amount": float(amount),
            "status": "pending"
        }
    
    async def process_pending(self) -> Dict[str, int]:
        """
        대기 중인 출금 처리 (DB 잠금으로 이중 처리 방지)
        """
        # 메모리 락으로 동시 실행 방지
        if self._processing_lock.locked():
            logger.warning("이미 출금 처리 중 - 스킵")
            return {"processed": 0, "failed": 0, "skipped": True}

        async with self._processing_lock:
            logger.info("출금 처리 시작...")

            try:
                async with async_session() as session:
                    # 대기 중인 출금 조회 (FOR UPDATE로 잠금)
                    # FOR UPDATE SKIP LOCKED: 이미 처리 중인 건은 스킵
                    result = await session.execute(
                        select(Withdrawal)
                        .where(Withdrawal.status == "pending")
                        .order_by(Withdrawal.created_at)
                        .with_for_update(skip_locked=True)
                    )
                    pending = result.scalars().all()

                    if not pending:
                        logger.info("대기 중인 출금 없음")
                        return {"processed": 0, "failed": 0}

                    logger.info(f"대기 중인 출금: {len(pending)}건")

                    # 메인 지갑 잔액 확인
                    main_balance = tron_client.get_usdt_balance(settings.main_wallet_address)
                    logger.info(f"메인 지갑 잔액: {main_balance} USDT")

                    processed = 0
                    failed = 0

                    for withdrawal in pending:
                        if main_balance < withdrawal.amount:
                            logger.warning(f"잔액 부족: #{withdrawal.withdrawal_id}")
                            continue

                        try:
                            await self._process_withdrawal(session, withdrawal)
                            main_balance -= withdrawal.amount
                            processed += 1
                        except Exception as e:
                            logger.error(f"출금 실패 #{withdrawal.withdrawal_id}: {e}")
                            withdrawal.status = "failed"
                            withdrawal.error_message = str(e)[:500]  # 에러 메시지 길이 제한
                            await session.commit()
                            failed += 1

                        await asyncio.sleep(2)  # Rate limit

                    logger.info(f"출금 처리 완료: {processed}건, 실패: {failed}건")
                    return {"processed": processed, "failed": failed}

            except Exception as e:
                logger.error(f"출금 배치 처리 오류: {e}")
                return {"processed": 0, "failed": 0, "error": str(e)}
    
    async def _process_withdrawal(
        self,
        session: AsyncSession,
        withdrawal: Withdrawal
    ):
        """개별 출금 처리 (원자성 보장)"""
        logger.info(f"출금 처리 시작: #{withdrawal.withdrawal_id}")

        # 상태를 processing으로 변경 (다른 프로세스가 처리하지 않도록)
        withdrawal.status = "processing"
        await session.commit()

        try:
            # USDT 전송
            result = tron_client.send_usdt(
                private_key=self.main_wallet_key,
                to_address=withdrawal.to_address,
                amount=withdrawal.amount
            )

            if result["success"]:
                withdrawal.tx_id = result["tx_id"]
                withdrawal.status = "completed"
                withdrawal.processed_at = datetime.utcnow()
                await session.commit()

                logger.info(f"출금 완료: #{withdrawal.withdrawal_id}, TX: {result['tx_id']}")
            else:
                withdrawal.status = "failed"
                withdrawal.error_message = result.get("error", "Unknown error")[:500]
                await session.commit()
                raise ValueError(result.get("error"))

        except Exception as e:
            # 트랜잭션 실패 시 상태 복구
            withdrawal.status = "failed"
            withdrawal.error_message = str(e)[:500]
            await session.commit()
            raise
    
    async def get_withdrawal(
        self,
        session: AsyncSession,
        withdrawal_id: int
    ) -> Optional[Withdrawal]:
        """출금 조회"""
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.withdrawal_id == withdrawal_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_withdrawals(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 50
    ) -> List[Withdrawal]:
        """사용자 출금 내역"""
        result = await session.execute(
            select(Withdrawal)
            .where(Withdrawal.user_id == user_id)
            .order_by(Withdrawal.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


# 싱글톤 인스턴스
withdrawal_processor = WithdrawalProcessor()
