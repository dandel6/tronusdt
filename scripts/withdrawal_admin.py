#!/usr/bin/env python3
"""
출금 관리 CLI (Tier 1 - 서버 전용)

기능:
- 대기 중인 출금 조회
- 대량 출금 승인 (임계값 초과)
- 출금 거부
- 출금 수동 처리
- 출금 내역 조회
"""
import asyncio
import sys
import os
from getpass import getpass
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import init_db, async_session
from app.db.models import Withdrawal, WithdrawalStatus
from app.wallet.tron_client import TronClient
from sqlalchemy import select, func, and_


# 대량 출금 임계값 (이 금액 이상은 CLI에서만 승인 가능)
LARGE_WITHDRAWAL_THRESHOLD = float(os.environ.get("LARGE_WITHDRAWAL_THRESHOLD", "1000"))


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_warning(msg: str):
    print(f"\n⚠️  경고: {msg}")


def confirm_action(prompt: str) -> bool:
    confirm = input(f"\n{prompt} (yes 입력): ").strip()
    return confirm.lower() == "yes"


def require_password() -> bool:
    """CLI 접근 비밀번호 확인"""
    cli_password = os.environ.get("CLI_ADMIN_PASSWORD")
    if not cli_password:
        print("❌ CLI_ADMIN_PASSWORD 환경변수가 설정되지 않았습니다.")
        return False

    password = getpass("CLI 관리자 비밀번호: ")
    if password != cli_password:
        print("❌ 비밀번호가 틀렸습니다.")
        return False
    return True


async def list_pending_withdrawals():
    """대기 중인 출금 목록"""
    print_header("대기 중인 출금 목록")

    await init_db()

    async with async_session() as session:
        # 대기 중인 출금 조회
        result = await session.execute(
            select(Withdrawal)
            .where(Withdrawal.status == WithdrawalStatus.PENDING)
            .order_by(Withdrawal.created_at.asc())
        )
        withdrawals = result.scalars().all()

        if not withdrawals:
            print("\n✅ 대기 중인 출금이 없습니다.")
            return

        total_amount = sum(float(w.amount) for w in withdrawals)
        large_count = sum(1 for w in withdrawals if float(w.amount) >= LARGE_WITHDRAWAL_THRESHOLD)

        print(f"\n총 {len(withdrawals)}건 (대량: {large_count}건) | 총액: {total_amount:,.2f} USDT")
        print(f"대량 출금 기준: {LARGE_WITHDRAWAL_THRESHOLD:,.0f} USDT 이상")
        print("-" * 90)
        print(f"{'ID':<8} {'User ID':<12} {'Amount':<15} {'To Address':<40} {'Type':<8}")
        print("-" * 90)

        for w in withdrawals:
            amount = float(w.amount)
            wtype = "🔴 대량" if amount >= LARGE_WITHDRAWAL_THRESHOLD else "일반"
            addr_short = w.to_address[:20] + "..." if len(w.to_address) > 20 else w.to_address
            print(f"{w.id:<8} {w.user_id:<12} {amount:<15,.2f} {addr_short:<40} {wtype:<8}")


async def list_large_pending():
    """대량 출금만 조회"""
    print_header(f"대량 출금 목록 ({LARGE_WITHDRAWAL_THRESHOLD:,.0f} USDT 이상)")

    await init_db()

    async with async_session() as session:
        result = await session.execute(
            select(Withdrawal)
            .where(
                and_(
                    Withdrawal.status == WithdrawalStatus.PENDING,
                    Withdrawal.amount >= LARGE_WITHDRAWAL_THRESHOLD
                )
            )
            .order_by(Withdrawal.created_at.asc())
        )
        withdrawals = result.scalars().all()

        if not withdrawals:
            print("\n✅ 대량 출금 요청이 없습니다.")
            return withdrawals

        print("-" * 100)
        print(f"{'ID':<8} {'User ID':<12} {'Amount':<18} {'To Address':<45} {'Created':<15}")
        print("-" * 100)

        for w in withdrawals:
            created = w.created_at.strftime("%m-%d %H:%M") if w.created_at else "N/A"
            print(f"{w.id:<8} {w.user_id:<12} {float(w.amount):<18,.2f} {w.to_address:<45} {created:<15}")

        return withdrawals


async def approve_withdrawal():
    """출금 승인"""
    print_header("출금 승인")

    withdrawal_id = input("출금 ID: ").strip()
    if not withdrawal_id:
        print("❌ 출금 ID를 입력하세요.")
        return

    await init_db()

    async with async_session() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == int(withdrawal_id))
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            print(f"❌ 출금 ID '{withdrawal_id}'를 찾을 수 없습니다.")
            return

        if withdrawal.status != WithdrawalStatus.PENDING:
            print(f"❌ 이 출금은 이미 처리되었습니다. (상태: {withdrawal.status.value})")
            return

        amount = float(withdrawal.amount)

        print(f"\n📋 출금 정보:")
        print(f"   ID: {withdrawal.id}")
        print(f"   User ID: {withdrawal.user_id}")
        print(f"   금액: {amount:,.2f} USDT")
        print(f"   받는 주소: {withdrawal.to_address}")
        print(f"   요청일: {withdrawal.created_at}")

        if amount >= LARGE_WITHDRAWAL_THRESHOLD:
            print_warning(f"대량 출금입니다! ({amount:,.2f} USDT)")

        if not confirm_action("이 출금을 승인하시겠습니까?"):
            print("취소됨.")
            return

        # 승인 처리 - 상태를 PROCESSING으로 변경
        withdrawal.status = WithdrawalStatus.PROCESSING
        withdrawal.approved_at = datetime.utcnow()
        withdrawal.approved_by = "CLI_ADMIN"

        await session.commit()
        print(f"\n✅ 출금 ID {withdrawal_id} 승인됨. 자동 처리기가 곧 전송합니다.")


async def approve_all_large():
    """모든 대량 출금 일괄 승인"""
    print_header("대량 출금 일괄 승인")

    withdrawals = await list_large_pending()
    if not withdrawals:
        return

    total = sum(float(w.amount) for w in withdrawals)

    print(f"\n총 {len(withdrawals)}건, {total:,.2f} USDT")
    print_warning("모든 대량 출금을 승인합니다!")

    if not confirm_action("정말로 모두 승인하시겠습니까?"):
        print("취소됨.")
        return

    await init_db()

    async with async_session() as session:
        for w in withdrawals:
            result = await session.execute(
                select(Withdrawal).where(Withdrawal.id == w.id)
            )
            withdrawal = result.scalar_one_or_none()
            if withdrawal and withdrawal.status == WithdrawalStatus.PENDING:
                withdrawal.status = WithdrawalStatus.PROCESSING
                withdrawal.approved_at = datetime.utcnow()
                withdrawal.approved_by = "CLI_ADMIN_BATCH"

        await session.commit()

    print(f"\n✅ {len(withdrawals)}건 승인 완료.")


async def reject_withdrawal():
    """출금 거부"""
    print_header("출금 거부")

    withdrawal_id = input("출금 ID: ").strip()
    if not withdrawal_id:
        print("❌ 출금 ID를 입력하세요.")
        return

    await init_db()

    async with async_session() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == int(withdrawal_id))
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            print(f"❌ 출금 ID '{withdrawal_id}'를 찾을 수 없습니다.")
            return

        if withdrawal.status != WithdrawalStatus.PENDING:
            print(f"❌ 이 출금은 이미 처리되었습니다. (상태: {withdrawal.status.value})")
            return

        print(f"\n📋 출금 정보:")
        print(f"   금액: {float(withdrawal.amount):,.2f} USDT")
        print(f"   받는 주소: {withdrawal.to_address}")

        reason = input("거부 사유: ").strip()

        if not confirm_action("이 출금을 거부하시겠습니까?"):
            print("취소됨.")
            return

        withdrawal.status = WithdrawalStatus.REJECTED
        withdrawal.rejected_at = datetime.utcnow()
        withdrawal.rejected_by = "CLI_ADMIN"
        withdrawal.reject_reason = reason or "CLI에서 거부됨"

        await session.commit()
        print(f"\n✅ 출금 ID {withdrawal_id} 거부됨.")


async def manual_process():
    """수동 출금 처리"""
    print_header("수동 출금 처리")

    print_warning("이 기능은 자동 처리가 실패한 경우에만 사용하세요!")

    withdrawal_id = input("출금 ID: ").strip()
    if not withdrawal_id:
        print("❌ 출금 ID를 입력하세요.")
        return

    await init_db()

    async with async_session() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == int(withdrawal_id))
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            print(f"❌ 출금 ID '{withdrawal_id}'를 찾을 수 없습니다.")
            return

        print(f"\n📋 출금 정보:")
        print(f"   상태: {withdrawal.status.value}")
        print(f"   금액: {float(withdrawal.amount):,.2f} USDT")
        print(f"   받는 주소: {withdrawal.to_address}")

        # 메인 지갑 잔액 확인
        client = TronClient()
        balance = await client.get_usdt_balance(settings.main_wallet_address)
        print(f"\n💰 메인 지갑 잔액: {balance:,.2f} USDT")

        if balance < float(withdrawal.amount):
            print("❌ 잔액이 부족합니다!")
            return

        if not confirm_action("수동으로 전송하시겠습니까?"):
            print("취소됨.")
            return

        try:
            # 전송 실행
            print("\n📡 전송 중...")
            tx_id = await client.transfer_usdt(
                from_address=settings.main_wallet_address,
                to_address=withdrawal.to_address,
                amount=float(withdrawal.amount),
                private_key=settings.main_wallet_private_key
            )

            withdrawal.status = WithdrawalStatus.COMPLETED
            withdrawal.tx_id = tx_id
            withdrawal.completed_at = datetime.utcnow()
            withdrawal.processed_by = "CLI_MANUAL"

            await session.commit()

            print(f"\n✅ 전송 완료!")
            print(f"   TX ID: {tx_id}")
            print(f"   TronScan: https://tronscan.org/#/transaction/{tx_id}")

        except Exception as e:
            print(f"\n❌ 전송 실패: {e}")
            withdrawal.error_message = str(e)
            await session.commit()


async def show_statistics():
    """출금 통계"""
    print_header("출금 통계")

    await init_db()

    async with async_session() as session:
        # 상태별 집계
        for status in WithdrawalStatus:
            result = await session.execute(
                select(
                    func.count(Withdrawal.id),
                    func.sum(Withdrawal.amount)
                ).where(Withdrawal.status == status)
            )
            count, total = result.one()
            total = total or 0
            print(f"  {status.value:<12}: {count:>5}건  |  {float(total):>15,.2f} USDT")

        # 오늘 처리된 출금
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(
                func.count(Withdrawal.id),
                func.sum(Withdrawal.amount)
            ).where(
                and_(
                    Withdrawal.status == WithdrawalStatus.COMPLETED,
                    Withdrawal.completed_at >= today
                )
            )
        )
        count, total = result.one()
        print(f"\n📅 오늘 완료: {count or 0}건 | {float(total or 0):,.2f} USDT")


def show_menu():
    print_header("출금 관리 CLI")
    print(f"""
  대량 출금 기준: {LARGE_WITHDRAWAL_THRESHOLD:,.0f} USDT 이상

  1. 대기 중인 출금 전체 조회
  2. 대량 출금만 조회
  3. 출금 승인 (단건)
  4. 대량 출금 일괄 승인
  5. 출금 거부
  6. 수동 출금 처리 (위험)
  7. 출금 통계

  0. 종료
""")


async def main():
    if not require_password():
        return

    while True:
        show_menu()
        choice = input("선택: ").strip()

        if choice == "1":
            await list_pending_withdrawals()
        elif choice == "2":
            await list_large_pending()
        elif choice == "3":
            await approve_withdrawal()
        elif choice == "4":
            await approve_all_large()
        elif choice == "5":
            await reject_withdrawal()
        elif choice == "6":
            await manual_process()
        elif choice == "7":
            await show_statistics()
        elif choice == "0":
            print("\n👋 종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다.")

        input("\n계속하려면 Enter를 누르세요...")


if __name__ == "__main__":
    asyncio.run(main())
