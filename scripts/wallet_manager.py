#!/usr/bin/env python3
"""
메인 지갑 관리 CLI (Tier 1 - 서버 전용)

기능:
- 메인 지갑 정보 조회
- 니모닉 조회 (보안 경고)
- 메인 지갑 개인키 조회
- 사용자 지갑 개인키 복호화
- 니모닉/메인지갑 변경 (위험)
"""
import asyncio
import sys
import os
from getpass import getpass
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import init_db, async_session
from app.db.models import UserWallet
from app.wallet.hd_wallet import HDWallet
from app.wallet.tron_client import TronClient


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_warning(msg: str):
    print(f"\n⚠️  경고: {msg}")


def confirm_action(prompt: str) -> bool:
    """위험한 작업 전 확인"""
    print_warning("이 작업은 되돌릴 수 없습니다!")
    confirm = input(f"\n{prompt} (yes를 입력하세요): ").strip()
    return confirm.lower() == "yes"


def require_password() -> bool:
    """CLI 접근 비밀번호 확인"""
    cli_password = os.environ.get("CLI_ADMIN_PASSWORD")
    if not cli_password:
        print("❌ CLI_ADMIN_PASSWORD 환경변수가 설정되지 않았습니다.")
        print("   export CLI_ADMIN_PASSWORD='your-secure-password'")
        return False

    password = getpass("CLI 관리자 비밀번호: ")
    if password != cli_password:
        print("❌ 비밀번호가 틀렸습니다.")
        return False
    return True


async def show_wallet_info():
    """메인 지갑 정보 조회"""
    print_header("메인 지갑 정보")

    client = TronClient()
    address = settings.main_wallet_address

    print(f"\n📍 주소: {address}")

    try:
        usdt_balance = await client.get_usdt_balance(address)
        trx_balance = await client.get_trx_balance(address)
        resources = await client.get_account_resources(address)

        print(f"💰 USDT 잔액: {usdt_balance:,.2f} USDT")
        print(f"⚡ TRX 잔액: {trx_balance:,.2f} TRX")
        print(f"🔋 에너지: {resources.get('energy', 0):,}")
        print(f"📡 대역폭: {resources.get('bandwidth', 0):,}")
    except Exception as e:
        print(f"❌ 조회 실패: {e}")


async def show_mnemonic():
    """니모닉 조회 (보안 주의)"""
    print_header("마스터 니모닉 조회")

    print_warning("니모닉은 모든 사용자 자금의 근원입니다!")
    print_warning("화면에 표시된 니모닉을 절대 공유하지 마세요!")
    print_warning("주변에 사람이 없는지 확인하세요!")

    if not confirm_action("니모닉을 표시하시겠습니까?"):
        print("취소됨.")
        return

    print("\n" + "-" * 60)
    print(settings.master_mnemonic)
    print("-" * 60)

    input("\n확인 후 Enter를 누르세요 (화면이 지워집니다)...")
    os.system('cls' if os.name == 'nt' else 'clear')
    print("✅ 화면이 지워졌습니다.")


async def show_main_private_key():
    """메인 지갑 개인키 조회"""
    print_header("메인 지갑 개인키 조회")

    print_warning("개인키가 노출되면 모든 자금을 잃을 수 있습니다!")

    if not confirm_action("개인키를 표시하시겠습니까?"):
        print("취소됨.")
        return

    print(f"\n📍 주소: {settings.main_wallet_address}")
    print("-" * 60)
    print(f"🔑 개인키: {settings.main_wallet_private_key}")
    print("-" * 60)

    input("\n확인 후 Enter를 누르세요 (화면이 지워집니다)...")
    os.system('cls' if os.name == 'nt' else 'clear')
    print("✅ 화면이 지워졌습니다.")


async def decrypt_user_wallet():
    """사용자 지갑 개인키 복호화"""
    print_header("사용자 지갑 개인키 복호화")

    user_id = input("사용자 ID: ").strip()
    if not user_id:
        print("❌ 사용자 ID를 입력하세요.")
        return

    await init_db()

    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(UserWallet).where(UserWallet.user_id == user_id)
        )
        wallet = result.scalar_one_or_none()

        if not wallet:
            print(f"❌ 사용자 ID '{user_id}'의 지갑을 찾을 수 없습니다.")
            return

        print(f"\n📍 주소: {wallet.wallet_address}")
        print(f"📅 생성일: {wallet.created_at}")

        if not confirm_action("개인키를 복호화하시겠습니까?"):
            print("취소됨.")
            return

        try:
            hd_wallet = HDWallet()
            private_key = hd_wallet.decrypt_private_key(wallet.private_key_encrypted)

            print("-" * 60)
            print(f"🔑 개인키: {private_key}")
            print("-" * 60)

            input("\n확인 후 Enter를 누르세요 (화면이 지워집니다)...")
            os.system('cls' if os.name == 'nt' else 'clear')
            print("✅ 화면이 지워졌습니다.")
        except Exception as e:
            print(f"❌ 복호화 실패: {e}")


async def list_user_wallets():
    """사용자 지갑 목록 조회"""
    print_header("사용자 지갑 목록")

    await init_db()

    async with async_session() as session:
        from sqlalchemy import select, func

        # 총 개수
        count_result = await session.execute(select(func.count(UserWallet.id)))
        total = count_result.scalar()

        print(f"\n총 {total}개의 지갑")

        # 최근 10개
        result = await session.execute(
            select(UserWallet)
            .order_by(UserWallet.created_at.desc())
            .limit(10)
        )
        wallets = result.scalars().all()

        print("\n최근 생성된 지갑 (10개):")
        print("-" * 80)
        print(f"{'User ID':<15} {'Address':<45} {'Created':<20}")
        print("-" * 80)

        for w in wallets:
            created = w.created_at.strftime("%Y-%m-%d %H:%M") if w.created_at else "N/A"
            print(f"{w.user_id:<15} {w.wallet_address:<45} {created:<20}")


async def export_wallet_backup():
    """지갑 백업 내보내기"""
    print_header("지갑 백업 내보내기")

    print_warning("백업 파일에는 민감한 정보가 포함됩니다!")
    print("백업 파일은 암호화된 USB나 오프라인 저장소에 보관하세요.")

    if not confirm_action("백업 파일을 생성하시겠습니까?"):
        print("취소됨.")
        return

    backup_data = {
        "exported_at": datetime.now().isoformat(),
        "main_wallet": {
            "address": settings.main_wallet_address,
            "note": "개인키는 .env 파일에서 직접 백업하세요"
        },
        "mnemonic_hint": f"첫 단어: {settings.master_mnemonic.split()[0]}...",
        "warning": "이 파일은 참조용입니다. 실제 키는 .env 파일을 백업하세요."
    }

    import json
    filename = f"wallet_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filename, 'w') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 백업 파일 생성됨: {filename}")
    print("⚠️  실제 개인키와 니모닉은 .env 파일을 직접 백업하세요!")


def show_menu():
    """메뉴 표시"""
    print_header("지갑 관리 CLI")
    print("""
  1. 메인 지갑 정보 조회
  2. 마스터 니모닉 조회 (위험)
  3. 메인 지갑 개인키 조회 (위험)
  4. 사용자 지갑 개인키 복호화 (위험)
  5. 사용자 지갑 목록 조회
  6. 지갑 백업 내보내기

  0. 종료
""")


async def main():
    if not require_password():
        return

    while True:
        show_menu()
        choice = input("선택: ").strip()

        if choice == "1":
            await show_wallet_info()
        elif choice == "2":
            await show_mnemonic()
        elif choice == "3":
            await show_main_private_key()
        elif choice == "4":
            await decrypt_user_wallet()
        elif choice == "5":
            await list_user_wallets()
        elif choice == "6":
            await export_wallet_backup()
        elif choice == "0":
            print("\n👋 종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다.")

        input("\n계속하려면 Enter를 누르세요...")


if __name__ == "__main__":
    asyncio.run(main())
