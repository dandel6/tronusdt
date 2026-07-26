#!/usr/bin/env python3
"""
TRON Gateway 관리자 CLI (통합 런처)

보안 등급: Tier 1 - 서버 전용
모든 민감한 관리 기능에 대한 단일 진입점

사용법:
  python admin_cli.py              # 대화형 메뉴
  python admin_cli.py wallet       # 지갑 관리 직접 실행
  python admin_cli.py withdrawal   # 출금 관리 직접 실행
  python admin_cli.py emergency    # 긴급 제어 직접 실행
  python admin_cli.py cold         # 콜드월렛 직접 실행
  python admin_cli.py security     # 보안 감사 직접 실행
"""
import os
import sys
import subprocess
from getpass import getpass

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

MODULES = {
    "1": ("wallet", "wallet_manager.py", "지갑 관리", "니모닉, 개인키 조회/관리"),
    "2": ("withdrawal", "withdrawal_admin.py", "출금 관리", "대량 출금 승인, 수동 처리"),
    "3": ("emergency", "emergency_control.py", "긴급 제어", "출금/입금/스위핑 중지/재개"),
    "4": ("cold", "cold_wallet.py", "콜드월렛", "Hot↔Cold 자금 이체"),
    "5": ("security", "security_audit.py", "보안 감사", "로그인 실패, 이상 탐지, IP 차단"),
    "6": ("setup", "setup.py", "초기 설정", "니모닉/지갑 생성, .env 설정"),
    "7": ("admin", "create_admin.py", "Super Admin 생성", "새 Super Admin 계정 생성"),
}


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ████████╗██████╗  ██████╗ ███╗   ██╗     ██████╗██╗     ██╗   ║
║   ╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║    ██╔════╝██║     ██║   ║
║      ██║   ██████╔╝██║   ██║██╔██╗ ██║    ██║     ██║     ██║   ║
║      ██║   ██╔══██╗██║   ██║██║╚██╗██║    ██║     ██║     ██║   ║
║      ██║   ██║  ██║╚██████╔╝██║ ╚████║    ╚██████╗███████╗██║   ║
║      ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝     ╚═════╝╚══════╝╚═╝   ║
║                                                                  ║
║              USDT Gateway - Admin CLI (Tier 1)                   ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


def print_menu():
    print("\n" + "=" * 60)
    print("  관리 도구 선택")
    print("=" * 60)

    for key, (_, _, name, desc) in MODULES.items():
        print(f"  {key}. {name:<15} - {desc}")

    print("\n  0. 종료")
    print("=" * 60)


def verify_cli_password():
    """CLI 비밀번호 확인 (환경변수 미설정 시 경고)"""
    cli_password = os.environ.get("CLI_ADMIN_PASSWORD")

    if not cli_password:
        print("\n⚠️  경고: CLI_ADMIN_PASSWORD 환경변수가 설정되지 않았습니다.")
        print("   보안을 위해 다음 명령으로 설정하세요:")
        print("   export CLI_ADMIN_PASSWORD='your-secure-password-here'\n")

        set_now = input("지금 임시로 설정하시겠습니까? (y/n): ").strip().lower()
        if set_now == 'y':
            password = getpass("CLI 관리자 비밀번호 설정: ")
            if len(password) < 8:
                print("❌ 비밀번호는 8자 이상이어야 합니다.")
                return False
            os.environ["CLI_ADMIN_PASSWORD"] = password
            print("✅ 임시 비밀번호 설정됨 (이 세션에서만 유효)")
        else:
            return False

    return True


def run_module(module_key: str):
    """모듈 실행"""
    if module_key not in MODULES:
        print(f"❌ 알 수 없는 모듈: {module_key}")
        return

    _, script_file, name, _ = MODULES[module_key]
    script_path = os.path.join(SCRIPTS_DIR, script_file)

    if not os.path.exists(script_path):
        print(f"❌ 스크립트를 찾을 수 없습니다: {script_path}")
        return

    print(f"\n🚀 {name} 시작...")
    print("-" * 40)

    # 서브프로세스로 실행 (환경변수 유지)
    try:
        subprocess.run([sys.executable, script_path], env=os.environ)
    except KeyboardInterrupt:
        print("\n\n중단됨.")


def main():
    # 명령줄 인자 처리
    if len(sys.argv) > 1:
        module_name = sys.argv[1].lower()

        # 모듈 이름으로 찾기
        for key, (name, _, _, _) in MODULES.items():
            if name == module_name:
                if not verify_cli_password():
                    return
                run_module(key)
                return

        print(f"❌ 알 수 없는 모듈: {module_name}")
        print("사용 가능한 모듈: wallet, withdrawal, emergency, cold, security, setup, admin")
        return

    # 대화형 모드
    print_banner()

    if not verify_cli_password():
        return

    while True:
        print_menu()
        choice = input("\n선택: ").strip()

        if choice == "0":
            print("\n👋 종료합니다.\n")
            break
        elif choice in MODULES:
            run_module(choice)
        else:
            print("❌ 잘못된 선택입니다.")


if __name__ == "__main__":
    main()
