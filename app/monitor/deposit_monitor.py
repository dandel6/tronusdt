"""
입금 모니터링
TronGrid API 폴링으로 입금 감지
"""
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Callable, Awaitable, List
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session, UserWallet, Deposit, SystemSetting
from app.wallet import hd_wallet, tron_client

logger = logging.getLogger(__name__)


class DepositMonitor:
    """
    입금 모니터링
    - TronGrid API 폴링
    - 입금 감지 및 DB 기록
    - 25 컨펌 대기
    """
    
    LAST_POLL_KEY = "last_poll_timestamp"
    
    def __init__(self):
        self.is_running = False
        self.poll_interval = settings.polling_interval_seconds
        self.required_confirmations = settings.required_confirmations
        
        # 입금 콜백 (웹훅, 알림 등)
        self.on_deposit_callback: Optional[Callable[[dict], Awaitable[None]]] = None
    
    async def start(self):
        """모니터링 시작"""
        if self.is_running:
            print("⚠️ 모니터 이미 실행 중")
            return
        
        self.is_running = True
        print(f"🔍 입금 모니터 시작 (폴링 주기: {self.poll_interval}초)")
        
        while self.is_running:
            try:
                await self.poll_deposits()
            except Exception as e:
                print(f"❌ 모니터 오류: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """모니터링 중지"""
        self.is_running = False
        print("🛑 입금 모니터 중지")
    
    async def poll_deposits(self):
        """모든 사용자 주소 입금 확인"""
        async with async_session() as session:
            # 마지막 폴링 시간 조회
            last_timestamp = await self._get_last_poll_timestamp(session)
            
            # 모든 사용자 주소 조회
            addresses = await hd_wallet.get_all_addresses(session)
            
            if not addresses:
                return
            
            new_deposits = 0
            
            for address in addresses:
                try:
                    count = await self._check_address_deposits(
                        session, address, last_timestamp
                    )
                    new_deposits += count
                except Exception as e:
                    print(f"❌ 주소 확인 실패 ({address}): {e}")
                
                await asyncio.sleep(0.1)  # Rate limit
            
            # 마지막 폴링 시간 업데이트
            await self._set_last_poll_timestamp(session)
            
            if new_deposits > 0:
                print(f"💰 새 입금 {new_deposits}건 감지")
    
    async def _check_address_deposits(
        self,
        session: AsyncSession,
        address: str,
        min_timestamp: int = None
    ) -> int:
        """특정 주소의 입금 확인"""
        
        # TronGrid API로 TRC-20 트랜잭션 조회
        transactions = await tron_client.get_trc20_transactions(
            address=address,
            only_to=True,
            only_confirmed=True,
            min_timestamp=min_timestamp
        )
        
        new_count = 0
        
        for tx in transactions:
            try:
                if await self._process_transaction(session, tx, address):
                    new_count += 1
            except Exception as e:
                print(f"❌ 트랜잭션 처리 실패: {e}")
        
        return new_count
    
    async def _process_transaction(
        self,
        session: AsyncSession,
        tx: dict,
        to_address: str
    ) -> bool:
        """
        트랜잭션 처리 (TOCTOU 방지: INSERT 후 IntegrityError 처리)

        tx_id가 Primary Key이므로 중복 INSERT 시 IntegrityError 발생
        이를 통해 race condition에서도 중복 입금을 방지
        """
        tx_id = tx.get("transaction_id")
        if not tx_id:
            logger.warning("트랜잭션 ID 없음 - 스킵")
            return False

        # 사용자 지갑 조회
        wallet = await hd_wallet.get_wallet_by_address(session, to_address)
        if not wallet:
            logger.warning(f"알 수 없는 주소로 입금: {to_address}")
            return False

        # 금액 계산 (USDT 6 decimals)
        raw_value = tx.get("value", 0)
        try:
            amount = Decimal(str(raw_value)) / Decimal(10 ** 6)
        except Exception:
            logger.error(f"금액 파싱 실패: {raw_value}")
            return False

        # 최소 금액 검증
        if amount <= Decimal("0"):
            logger.warning(f"0 이하 금액 입금 감지 - 스킵: {tx_id}")
            return False

        from_address = tx.get("from", "unknown")
        block_timestamp = tx.get("block_timestamp", 0)

        # 입금 기록 생성 (tx_id가 PK이므로 중복 시 IntegrityError)
        deposit = Deposit(
            tx_id=tx_id,
            user_id=wallet.user_id,
            from_address=from_address,
            amount=amount,
            block_timestamp=block_timestamp,
            confirmations=settings.required_confirmations,
            status="confirmed"
        )

        try:
            session.add(deposit)
            await session.commit()
        except IntegrityError:
            # 이미 처리된 트랜잭션 (다른 프로세스에서 먼저 처리)
            await session.rollback()
            logger.debug(f"이미 처리된 트랜잭션: {tx_id}")
            return False

        logger.info(
            f"입금 감지: user={wallet.user_id}, amount={amount} USDT, tx={tx_id[:16]}..."
        )

        # 콜백 호출 (입금 알림)
        if self.on_deposit_callback:
            try:
                await self.on_deposit_callback({
                    "user_id": wallet.user_id,
                    "amount": float(amount),
                    "tx_id": tx_id,
                    "from_address": from_address,
                    "to_address": to_address
                })
            except Exception as e:
                logger.error(f"입금 콜백 실패: {e}")

        return True
    
    async def _get_last_poll_timestamp(self, session: AsyncSession) -> Optional[int]:
        """마지막 폴링 시간 조회"""
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == self.LAST_POLL_KEY)
        )
        setting = result.scalar_one_or_none()
        return int(setting.value) if setting else None
    
    async def _set_last_poll_timestamp(self, session: AsyncSession):
        """마지막 폴링 시간 저장"""
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == self.LAST_POLL_KEY)
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = str(timestamp)
        else:
            setting = SystemSetting(key=self.LAST_POLL_KEY, value=str(timestamp))
            session.add(setting)
        
        await session.commit()
    
    async def get_unswept_deposits(self, session: AsyncSession) -> List[Deposit]:
        """스위핑 안 된 입금 조회"""
        result = await session.execute(
            select(Deposit).where(
                and_(
                    Deposit.status == "confirmed",
                    Deposit.swept == False
                )
            )
        )
        return result.scalars().all()


# 싱글톤 인스턴스
deposit_monitor = DepositMonitor()
