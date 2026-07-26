#!/usr/bin/env python3
"""
긴급 제어 CLI (Tier 1 - 서버 전용)

기능:
- 출금 긴급 중지/재개
- 입금 모니터링 중지/재개
- 스위핑 중지/재개
- 시스템 상태 조회
- 긴급 모드 활성화 (모든 기능 중지)
"""
import asyncio
import sys
import os
from getpass import getpass
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import init_db, async_session
from app.db.models import SystemSetting
from sqlalchemy import select


# 시스템 제어 키
CONTROL_KEYS = {
    "withdrawal_enabled": "출금 활성화",
    "deposit_monitor_enabled": "입금 모니터링 활성화",
    "sweep_enabled": "스위핑 활성화",
    "emergency_mode": "긴급 모드 (모든 기능 중지)",
}


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_warning(msg: str):
    print(f"\n⚠️  경고: {msg}")


def print_status(enabled: bool):
    return "🟢 활성화" if enabled else "🔴 비활성화"


def confirm_action(prompt: str) -> bool:
    confirm = input(f"\n{prompt} (yes 입력): ").strip()
    return confirm.lower() == "yes"


def require_password() -> bool:
    cli_password = os.environ.get("CLI_ADMIN_PASSWORD")
    if not cli_password:
        print("❌ CLI_ADMIN_PASSWORD 환경변수가 설정되지 않았습니다.")
        return False

    password = getpass("CLI 관리자 비밀번호: ")
    if password != cli_password:
        print("❌ 비밀번호가 틀렸습니다.")
        return False
    return True


async def get_setting(session, key: str, default: bool = True) -> bool:
    """시스템 설정 조회"""
    result = await session.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting:
        return setting.value.lower() == "true"
    return default


async def set_setting(session, key: str, value: bool, reason: str = ""):
    """시스템 설정 변경"""
    result = await session.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()

    str_value = "true" if value else "false"

    if setting:
        setting.value = str_value
        setting.updated_at = datetime.utcnow()
        setting.updated_by = "CLI_ADMIN"
        setting.update_reason = reason
    else:
        new_setting = SystemSetting(
            key=key,
            value=str_value,
            description=CONTROL_KEYS.get(key, key),
            created_by="CLI_ADMIN"
        )
        session.add(new_setting)

    await session.commit()


async def show_system_status():
    """시스템 상태 조회"""
    print_header("시스템 상태")

    await init_db()

    async with async_session() as session:
        print("\n📊 제어 상태:")
        print("-" * 50)

        for key, label in CONTROL_KEYS.items():
            if key == "emergency_mode":
                # 긴급 모드는 반대로 표시 (true = 모두 중지)
                enabled = await get_setting(session, key, False)
                status = "🔴 긴급 모드 ON" if enabled else "🟢 정상"
            else:
                enabled = await get_setting(session, key, True)
                status = print_status(enabled)

            print(f"  {label:<25}: {status}")

        # 메인 지갑 상태
        print("\n💰 메인 지갑:")
        print("-" * 50)
        print(f"  주소: {settings.main_wallet_address}")

        try:
            from app.wallet.tron_client import TronClient
            client = TronClient()
            usdt = await client.get_usdt_balance(settings.main_wallet_address)
            trx = await client.get_trx_balance(settings.main_wallet_address)
            print(f"  USDT: {usdt:,.2f}")
            print(f"  TRX: {trx:,.2f}")
        except Exception as e:
            print(f"  ❌ 조회 실패: {e}")

        # 대기 중인 작업
        print("\n📋 대기 중인 작업:")
        print("-" * 50)

        from app.db.models import Withdrawal, WithdrawalStatus, Deposit
        from sqlalchemy import func

        # 대기 출금
        result = await session.execute(
            select(func.count(Withdrawal.id), func.sum(Withdrawal.amount))
            .where(Withdrawal.status == WithdrawalStatus.PENDING)
        )
        w_count, w_total = result.one()
        print(f"  대기 출금: {w_count or 0}건 ({float(w_total or 0):,.2f} USDT)")

        # 미스윕 입금
        result = await session.execute(
            select(func.count(Deposit.id), func.sum(Deposit.amount))
            .where(Deposit.swept == False)
        )
        d_count, d_total = result.one()
        print(f"  미스윕 입금: {d_count or 0}건 ({float(d_total or 0):,.2f} USDT)")


async def toggle_withdrawal():
    """출금 활성화/비활성화"""
    print_header("출금 제어")

    await init_db()

    async with async_session() as session:
        current = await get_setting(session, "withdrawal_enabled", True)
        print(f"\n현재 상태: {print_status(current)}")

        new_status = not current
        action = "활성화" if new_status else "비활성화"

        if not new_status:
            print_warning("출금을 비활성화하면 모든 출금이 중지됩니다!")

        reason = input(f"변경 사유 ({action}): ").strip()

        if not confirm_action(f"출금을 {action}하시겠습니까?"):
            print("취소됨.")
            return

        await set_setting(session, "withdrawal_enabled", new_status, reason)
        print(f"\n✅ 출금 {action}됨.")


async def toggle_deposit_monitor():
    """입금 모니터링 활성화/비활성화"""
    print_header("입금 모니터링 제어")

    await init_db()

    async with async_session() as session:
        current = await get_setting(session, "deposit_monitor_enabled", True)
        print(f"\n현재 상태: {print_status(current)}")

        new_status = not current
        action = "활성화" if new_status else "비활성화"

        if not new_status:
            print_warning("모니터링을 비활성화하면 새 입금이 감지되지 않습니다!")

        reason = input(f"변경 사유 ({action}): ").strip()

        if not confirm_action(f"입금 모니터링을 {action}하시겠습니까?"):
            print("취소됨.")
            return

        await set_setting(session, "deposit_monitor_enabled", new_status, reason)
        print(f"\n✅ 입금 모니터링 {action}됨.")


async def toggle_sweep():
    """스위핑 활성화/비활성화"""
    print_header("스위핑 제어")

    await init_db()

    async with async_session() as session:
        current = await get_setting(session, "sweep_enabled", True)
        print(f"\n현재 상태: {print_status(current)}")

        new_status = not current
        action = "활성화" if new_status else "비활성화"

        if not new_status:
            print_warning("스위핑을 비활성화하면 입금이 메인 지갑으로 모이지 않습니다!")

        reason = input(f"변경 사유 ({action}): ").strip()

        if not confirm_action(f"스위핑을 {action}하시겠습니까?"):
            print("취소됨.")
            return

        await set_setting(session, "sweep_enabled", new_status, reason)
        print(f"\n✅ 스위핑 {action}됨.")


async def toggle_emergency_mode():
    """긴급 모드 활성화/비활성화"""
    print_header("긴급 모드 제어")

    await init_db()

    async with async_session() as session:
        current = await get_setting(session, "emergency_mode", False)

        if current:
            print("\n🔴 현재 긴급 모드 ON - 모든 기능 중지됨")
        else:
            print("\n🟢 현재 정상 모드")

        new_status = not current

        if new_status:
            print_warning("긴급 모드를 활성화하면:")
            print("  - 모든 출금이 중지됩니다")
            print("  - 입금 모니터링이 중지됩니다")
            print("  - 스위핑이 중지됩니다")
            print("  - API 요청이 거부됩니다")
            action = "활성화"
        else:
            print("\n긴급 모드를 해제하면 모든 기능이 재개됩니다.")
            action = "비활성화"

        reason = input(f"\n변경 사유 ({action}): ").strip()

        if not confirm_action(f"긴급 모드를 {action}하시겠습니까?"):
            print("취소됨.")
            return

        # 긴급 모드 변경
        await set_setting(session, "emergency_mode", new_status, reason)

        # 긴급 모드 활성화 시 모든 기능 비활성화
        if new_status:
            await set_setting(session, "withdrawal_enabled", False, "긴급 모드")
            await set_setting(session, "deposit_monitor_enabled", False, "긴급 모드")
            await set_setting(session, "sweep_enabled", False, "긴급 모드")
            print("\n🔴 긴급 모드 활성화됨 - 모든 기능 중지")
        else:
            await set_setting(session, "withdrawal_enabled", True, "긴급 모드 해제")
            await set_setting(session, "deposit_monitor_enabled", True, "긴급 모드 해제")
            await set_setting(session, "sweep_enabled", True, "긴급 모드 해제")
            print("\n🟢 긴급 모드 해제됨 - 모든 기능 재개")


async def view_control_log():
    """제어 변경 로그 조회"""
    print_header("제어 변경 로그")

    await init_db()

    async with async_session() as session:
        result = await session.execute(
            select(SystemSetting)
            .where(SystemSetting.key.in_(CONTROL_KEYS.keys()))
            .order_by(SystemSetting.updated_at.desc())
        )
        settings_list = result.scalars().all()

        if not settings_list:
            print("\n변경 기록이 없습니다.")
            return

        print("-" * 90)
        print(f"{'Key':<25} {'Value':<10} {'Updated By':<15} {'Reason':<30}")
        print("-" * 90)

        for s in settings_list:
            updated_by = s.updated_by or s.created_by or "SYSTEM"
            reason = (s.update_reason or "")[:28]
            print(f"{s.key:<25} {s.value:<10} {updated_by:<15} {reason:<30}")


def show_menu():
    print_header("긴급 제어 CLI")
    print("""
  1. 시스템 상태 조회
  2. 출금 활성화/비활성화
  3. 입금 모니터링 활성화/비활성화
  4. 스위핑 활성화/비활성화
  5. 긴급 모드 ON/OFF (모든 기능)
  6. 제어 변경 로그

  0. 종료
""")


async def main():
    if not require_password():
        return

    while True:
        show_menu()
        choice = input("선택: ").strip()

        if choice == "1":
            await show_system_status()
        elif choice == "2":
            await toggle_withdrawal()
        elif choice == "3":
            await toggle_deposit_monitor()
        elif choice == "4":
            await toggle_sweep()
        elif choice == "5":
            await toggle_emergency_mode()
        elif choice == "6":
            await view_control_log()
        elif choice == "0":
            print("\n👋 종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다.")

        input("\n계속하려면 Enter를 누르세요...")


if __name__ == "__main__":
    asyncio.run(main())
