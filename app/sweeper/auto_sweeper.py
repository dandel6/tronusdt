"""
자동 스위핑 (Auto-Sweeping)
사용자 입금 지갑 → 메인 핫월렛으로 자동 이동
"""
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session, UserWallet, Deposit, SweepLog
from app.wallet import hd_wallet, tron_client

logger = logging.getLogger(__name__)


class AutoSweeper:
    """
    자동 스위핑
    - 입금 감지 후 메인 핫월렛으로 자동 이동
    - 임계값 기반 스위핑 (선택적)
    - 실패 시 재시도
    """
    
    MAX_RETRY = 3
    
    def __init__(self):
        self.is_running = False
        self.threshold = Decimal(str(settings.sweep_threshold_usdt))
        self.main_wallet = settings.main_wallet_address
    
    async def start(self):
        """스위핑 서비스 시작"""
        if self.is_running:
            print("⚠️ 스위퍼 이미 실행 중")
            return
        
        self.is_running = True
        print(f"🧹 자동 스위퍼 시작 (임계값: {self.threshold} USDT)")
        
        while self.is_running:
            try:
                await self.sweep_all()
            except Exception as e:
                print(f"❌ 스위퍼 오류: {e}")
            
            await asyncio.sleep(settings.polling_interval_seconds)
    
    def stop(self):
        """스위핑 서비스 중지"""
        self.is_running = False
        print("🛑 자동 스위퍼 중지")
    
    async def sweep_all(self) -> Dict[str, Any]:
        """모든 스위핑 대상 처리"""
        async with async_session() as session:
            # 스위핑 대상 조회
            targets = await self._get_sweep_targets(session)
            
            if not targets:
                return {"swept": 0, "total_amount": 0, "failed": 0}
            
            print(f"🧹 스위핑 대상: {len(targets)}건")
            
            swept = 0
            total_amount = Decimal(0)
            failed = 0
            
            for target in targets:
                try:
                    result = await self._sweep_address(session, target)
                    if result["success"]:
                        swept += 1
                        total_amount += Decimal(str(result["amount"]))
                except Exception as e:
                    print(f"❌ 스위핑 실패 ({target['address']}): {e}")
                    failed += 1
                
                await asyncio.sleep(2)  # Rate limit
            
            print(f"✅ 스위핑 완료: {swept}건, {total_amount} USDT")
            return {
                "swept": swept,
                "total_amount": float(total_amount),
                "failed": failed
            }
    
    async def _get_sweep_targets(self, session: AsyncSession) -> List[Dict]:
        """스위핑 대상 조회"""
        # 스위핑 안 된 입금 조회
        result = await session.execute(
            select(Deposit, UserWallet)
            .join(UserWallet, Deposit.user_id == UserWallet.user_id)
            .where(
                and_(
                    Deposit.status == "confirmed",
                    Deposit.swept == False
                )
            )
        )
        rows = result.fetchall()
        
        # 주소별로 그룹화
        address_map = {}
        for deposit, wallet in rows:
            addr = wallet.wallet_address
            if addr not in address_map:
                address_map[addr] = {
                    "address": addr,
                    "user_id": wallet.user_id,
                    "deposits": [],
                    "total_amount": Decimal(0)
                }
            address_map[addr]["deposits"].append(deposit)
            address_map[addr]["total_amount"] += deposit.amount
        
        # 임계값 필터링 (0이면 모두 스위핑)
        targets = []
        for addr, data in address_map.items():
            if self.threshold <= 0 or data["total_amount"] >= self.threshold:
                # 실제 온체인 잔액 확인
                actual_balance = tron_client.get_usdt_balance(addr)
                if actual_balance > 0:
                    data["actual_balance"] = actual_balance
                    targets.append(data)
        
        return targets
    
    async def _sweep_address(
        self,
        session: AsyncSession,
        target: Dict
    ) -> Dict[str, Any]:
        """
        특정 주소 스위핑 (원자성 보장)

        순서:
        1. 스위핑 로그 생성 (status=processing)
        2. 온체인 전송 시도
        3. 성공: status=completed, 입금 레코드 업데이트
        4. 실패: status=failed (입금 레코드는 건드리지 않음)
        """
        address = target["address"]
        user_id = target["user_id"]
        actual_balance = target["actual_balance"]

        logger.info(f"스위핑 시작: {address[:10]}... → 메인월렛, 잔액: {actual_balance} USDT")

        # 개인키 조회 (감사 로그 포함)
        private_key = await hd_wallet.get_private_key_by_address(
            session,
            address,
            reason="sweeping",
            caller="auto_sweeper"
        )

        # 1단계: 스위핑 로그 생성 (processing 상태로 먼저 저장)
        sweep_log = SweepLog(
            from_address=address,
            to_address=self.main_wallet,
            amount=actual_balance,
            status="processing"  # pending이 아닌 processing으로 시작
        )
        session.add(sweep_log)
        await session.commit()
        await session.refresh(sweep_log)

        try:
            # 2단계: USDT 전송 (온체인 트랜잭션)
            result = tron_client.send_usdt(
                private_key=private_key,
                to_address=self.main_wallet,
                amount=actual_balance
            )

            if result["success"]:
                # 3단계: 성공 - 로그 및 입금 레코드 업데이트
                sweep_log.tx_id = result["tx_id"]
                sweep_log.status = "completed"
                sweep_log.completed_at = datetime.utcnow()

                # 입금 레코드 업데이트 (연관된 입금만)
                for deposit in target.get("deposits", []):
                    deposit.swept = True
                    deposit.sweep_tx_id = result["tx_id"]

                await session.commit()

                logger.info(f"스위핑 완료: {address[:10]}..., TX: {result['tx_id'][:16]}...")

                return {
                    "success": True,
                    "tx_id": result["tx_id"],
                    "amount": float(actual_balance),
                    "from": address,
                    "to": self.main_wallet
                }
            else:
                # 전송 실패 (온체인 오류)
                raise ValueError(result.get("error", "Unknown error"))

        except Exception as e:
            # 4단계: 실패 - 로그만 업데이트 (입금 레코드는 그대로)
            sweep_log.status = "failed"
            sweep_log.error_message = str(e)[:500]
            await session.commit()

            logger.error(f"스위핑 실패: {address[:10]}..., 오류: {e}")

            return {
                "success": False,
                "error": str(e)
            }
    
    async def force_sweep(self, session: AsyncSession, address: str) -> Dict[str, Any]:
        """강제 스위핑 (관리자용)"""
        wallet = await hd_wallet.get_wallet_by_address(session, address)
        if not wallet:
            raise ValueError(f"지갑을 찾을 수 없습니다: {address}")
        
        actual_balance = tron_client.get_usdt_balance(address)
        if actual_balance <= 0:
            raise ValueError("스위핑할 잔액이 없습니다")
        
        target = {
            "address": address,
            "user_id": wallet.user_id,
            "deposits": [],
            "actual_balance": actual_balance
        }
        
        return await self._sweep_address(session, target)


# 싱글톤 인스턴스
auto_sweeper = AutoSweeper()
