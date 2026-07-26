#!/usr/bin/env python3
"""
콜드월렛 관리 CLI (Tier 1 - 서버 전용)

기능:
- 콜드월렛 설정
- Hot → Cold 이체 (자금 보관)
- Cold → Hot 이체 (출금용 충전)
- 잔액 조회
- 이체 내역 조회
"""
import asyncio
import sys
import os
from getpass import getpass
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import init_db, async_session
from app.db.models import SystemSetting, ColdWalletTransfer
from app.wallet.tron_client import TronClient
from sqlalchemy import select, desc


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_warning(msg: str):
    print(f"\n⚠️  경고: {msg}")


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


async def get_cold_wallet_address(session) -> str:
    """콜드월렛 주소 조회"""
    result = await session.execute(
        select(SystemSetting).where(SystemSetting.key == "cold_wallet_address")
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def show_wallet_balances():
    """지갑 잔액 조회"""
    print_header("지갑 잔액 조회")

    await init_db()
    client = TronClient()

    async with async_session() as session:
        cold_address = await get_cold_wallet_address(session)

        # Hot Wallet
        print("\n🔥 Hot Wallet (메인 지갑):")
        print(f"   주소: {settings.main_wallet_address}")
        try:
            hot_usdt = await client.get_usdt_balance(settings.main_wallet_address)
            hot_trx = await client.get_trx_balance(settings.main_wallet_address)
            print(f"   USDT: {hot_usdt:,.2f}")
            print(f"   TRX: {hot_trx:,.2f}")
        except Exception as e:
            print(f"   ❌ 조회 실패: {e}")

        # Cold Wallet
        print("\n🧊 Cold Wallet:")
        if cold_address:
            print(f"   주소: {cold_address}")
            try:
                cold_usdt = await client.get_usdt_balance(cold_address)
                cold_trx = await client.get_trx_balance(cold_address)
                print(f"   USDT: {cold_usdt:,.2f}")
                print(f"   TRX: {cold_trx:,.2f}")
            except Exception as e:
                print(f"   ❌ 조회 실패: {e}")
        else:
            print("   ❌ 설정되지 않음 (메뉴 1번에서 설정)")


async def set_cold_wallet():
    """콜드월렛 주소 설정"""
    print_header("콜드월렛 주소 설정")

    await init_db()

    async with async_session() as session:
        current = await get_cold_wallet_address(session)
        if current:
            print(f"\n현재 설정된 주소: {current}")

        new_address = input("\n새 콜드월렛 주소 (TRON): ").strip()

        if not new_address:
            print("취소됨.")
            return

        # 주소 형식 검증
        if not new_address.startswith("T") or len(new_address) != 34:
            print("❌ 유효하지 않은 TRON 주소입니다.")
            return

        # 잔액 확인으로 주소 검증
        client = TronClient()
        try:
            balance = await client.get_usdt_balance(new_address)
            print(f"   주소 확인됨. 현재 잔액: {balance:,.2f} USDT")
        except Exception as e:
            print_warning(f"주소 확인 실패: {e}")
            if not confirm_action("그래도 설정하시겠습니까?"):
                print("취소됨.")
                return

        if not confirm_action("이 주소를 콜드월렛으로 설정하시겠습니까?"):
            print("취소됨.")
            return

        # 설정 저장
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == "cold_wallet_address")
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = new_address
            setting.updated_at = datetime.utcnow()
            setting.updated_by = "CLI_ADMIN"
        else:
            setting = SystemSetting(
                key="cold_wallet_address",
                value=new_address,
                description="콜드월렛 주소",
                created_by="CLI_ADMIN"
            )
            session.add(setting)

        await session.commit()
        print(f"\n✅ 콜드월렛 설정됨: {new_address}")


async def transfer_hot_to_cold():
    """Hot → Cold 이체"""
    print_header("Hot → Cold 이체")

    await init_db()
    client = TronClient()

    async with async_session() as session:
        cold_address = await get_cold_wallet_address(session)

        if not cold_address:
            print("❌ 콜드월렛이 설정되지 않았습니다.")
            return

        # 잔액 확인
        hot_usdt = await client.get_usdt_balance(settings.main_wallet_address)
        hot_trx = await client.get_trx_balance(settings.main_wallet_address)

        print(f"\n🔥 Hot Wallet 잔액:")
        print(f"   USDT: {hot_usdt:,.2f}")
        print(f"   TRX: {hot_trx:,.2f}")
        print(f"\n🧊 Cold Wallet: {cold_address}")

        # 최소 유지 금액 (출금용)
        min_keep = float(input("\nHot Wallet에 남겨둘 최소 금액 (USDT, 기본 1000): ").strip() or "1000")

        available = hot_usdt - min_keep
        if available <= 0:
            print(f"❌ 이체 가능 금액이 없습니다. (유지 금액: {min_keep:,.2f})")
            return

        print(f"\n이체 가능 금액: {available:,.2f} USDT")

        amount_str = input("이체할 금액 (USDT): ").strip()
        try:
            amount = float(amount_str)
        except ValueError:
            print("❌ 유효한 금액을 입력하세요.")
            return

        if amount <= 0 or amount > available:
            print(f"❌ 0 ~ {available:,.2f} 사이의 금액을 입력하세요.")
            return

        print(f"\n📤 이체 정보:")
        print(f"   From: Hot Wallet ({settings.main_wallet_address[:20]}...)")
        print(f"   To: Cold Wallet ({cold_address[:20]}...)")
        print(f"   금액: {amount:,.2f} USDT")

        if not confirm_action("이체를 실행하시겠습니까?"):
            print("취소됨.")
            return

        try:
            print("\n📡 전송 중...")
            tx_id = await client.transfer_usdt(
                from_address=settings.main_wallet_address,
                to_address=cold_address,
                amount=amount,
                private_key=settings.main_wallet_private_key
            )

            # 이체 기록 저장
            transfer = ColdWalletTransfer(
                direction="hot_to_cold",
                amount=Decimal(str(amount)),
                tx_id=tx_id,
                from_address=settings.main_wallet_address,
                to_address=cold_address,
                status="completed",
                created_by="CLI_ADMIN"
            )
            session.add(transfer)
            await session.commit()

            print(f"\n✅ 이체 완료!")
            print(f"   TX ID: {tx_id}")
            print(f"   TronScan: https://tronscan.org/#/transaction/{tx_id}")

        except Exception as e:
            print(f"\n❌ 이체 실패: {e}")


async def transfer_cold_to_hot():
    """Cold → Hot 이체 (수동)"""
    print_header("Cold → Hot 이체")

    print_warning("콜드월렛의 개인키는 이 시스템에 저장되어 있지 않습니다.")
    print("콜드월렛에서 직접 전송하거나, 하드웨어 지갑을 사용하세요.\n")

    await init_db()
    client = TronClient()

    async with async_session() as session:
        cold_address = await get_cold_wallet_address(session)

        if not cold_address:
            print("❌ 콜드월렛이 설정되지 않았습니다.")
            return

        # 잔액 확인
        cold_usdt = await client.get_usdt_balance(cold_address)
        hot_usdt = await client.get_usdt_balance(settings.main_wallet_address)

        print(f"🧊 Cold Wallet 잔액: {cold_usdt:,.2f} USDT")
        print(f"🔥 Hot Wallet 잔액: {hot_usdt:,.2f} USDT")
        print(f"\n📥 Hot Wallet 주소: {settings.main_wallet_address}")

        print("\n아래 방법 중 하나를 사용하세요:")
        print("  1. 하드웨어 지갑(Ledger/Trezor)에서 직접 전송")
        print("  2. TronLink 등 월렛 앱에서 전송")
        print("  3. 콜드월렛 개인키를 임시로 입력하여 전송 (비권장)")

        choice = input("\n선택 (3 입력시 개인키로 전송): ").strip()

        if choice != "3":
            print("\n외부에서 전송 후 이 화면에서 기록을 남겨주세요.")
            tx_id = input("전송 완료된 TX ID (선택): ").strip()
            amount_str = input("전송한 금액 (USDT): ").strip()

            if tx_id and amount_str:
                try:
                    amount = float(amount_str)
                    transfer = ColdWalletTransfer(
                        direction="cold_to_hot",
                        amount=Decimal(str(amount)),
                        tx_id=tx_id,
                        from_address=cold_address,
                        to_address=settings.main_wallet_address,
                        status="completed",
                        created_by="CLI_ADMIN_MANUAL"
                    )
                    session.add(transfer)
                    await session.commit()
                    print("✅ 이체 기록이 저장되었습니다.")
                except Exception as e:
                    print(f"❌ 기록 저장 실패: {e}")
            return

        # 개인키로 직접 전송
        print_warning("개인키를 입력하면 화면에 노출됩니다!")
        print_warning("주변에 사람이 없는지 확인하세요!")

        cold_private_key = getpass("콜드월렛 개인키: ")

        amount_str = input("이체할 금액 (USDT): ").strip()
        try:
            amount = float(amount_str)
        except ValueError:
            print("❌ 유효한 금액을 입력하세요.")
            return

        if amount <= 0 or amount > cold_usdt:
            print(f"❌ 0 ~ {cold_usdt:,.2f} 사이의 금액을 입력하세요.")
            return

        if not confirm_action("이체를 실행하시겠습니까?"):
            print("취소됨.")
            return

        try:
            print("\n📡 전송 중...")
            tx_id = await client.transfer_usdt(
                from_address=cold_address,
                to_address=settings.main_wallet_address,
                amount=amount,
                private_key=cold_private_key
            )

            transfer = ColdWalletTransfer(
                direction="cold_to_hot",
                amount=Decimal(str(amount)),
                tx_id=tx_id,
                from_address=cold_address,
                to_address=settings.main_wallet_address,
                status="completed",
                created_by="CLI_ADMIN"
            )
            session.add(transfer)
            await session.commit()

            print(f"\n✅ 이체 완료!")
            print(f"   TX ID: {tx_id}")

        except Exception as e:
            print(f"\n❌ 이체 실패: {e}")


async def view_transfer_history():
    """이체 내역 조회"""
    print_header("콜드월렛 이체 내역")

    await init_db()

    async with async_session() as session:
        result = await session.execute(
            select(ColdWalletTransfer)
            .order_by(desc(ColdWalletTransfer.created_at))
            .limit(20)
        )
        transfers = result.scalars().all()

        if not transfers:
            print("\n이체 내역이 없습니다.")
            return

        print("-" * 100)
        print(f"{'Date':<18} {'Direction':<12} {'Amount':<15} {'TX ID':<30} {'Status':<10}")
        print("-" * 100)

        for t in transfers:
            date = t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "N/A"
            direction = "Hot→Cold" if t.direction == "hot_to_cold" else "Cold→Hot"
            tx_short = (t.tx_id[:26] + "...") if t.tx_id and len(t.tx_id) > 26 else (t.tx_id or "N/A")
            print(f"{date:<18} {direction:<12} {float(t.amount):<15,.2f} {tx_short:<30} {t.status:<10}")


def show_menu():
    print_header("콜드월렛 관리 CLI")
    print("""
  1. 콜드월렛 주소 설정
  2. 지갑 잔액 조회
  3. Hot → Cold 이체 (자금 보관)
  4. Cold → Hot 이체 (출금용 충전)
  5. 이체 내역 조회

  0. 종료
""")


async def main():
    if not require_password():
        return

    while True:
        show_menu()
        choice = input("선택: ").strip()

        if choice == "1":
            await set_cold_wallet()
        elif choice == "2":
            await show_wallet_balances()
        elif choice == "3":
            await transfer_hot_to_cold()
        elif choice == "4":
            await transfer_cold_to_hot()
        elif choice == "5":
            await view_transfer_history()
        elif choice == "0":
            print("\n👋 종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다.")

        input("\n계속하려면 Enter를 누르세요...")


if __name__ == "__main__":
    asyncio.run(main())
