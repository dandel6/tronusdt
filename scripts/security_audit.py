#!/usr/bin/env python3
"""
보안 감사 CLI (Tier 1 - 서버 전용)

기능:
- 로그인 실패 기록 조회
- 의심스러운 활동 탐지
- IP 차단 관리
- 감사 로그 조회
- 보안 설정 검토
"""
import asyncio
import sys
import os
from getpass import getpass
from datetime import datetime, timedelta
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import init_db, async_session
from app.db.admin_models import Admin, AdminSession, AuditLog
from app.db.models import Withdrawal, Deposit, SystemSetting
from sqlalchemy import select, func, desc, and_


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_warning(msg: str):
    print(f"\n⚠️  {msg}")


def print_alert(msg: str):
    print(f"\n🚨 {msg}")


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


async def check_failed_logins():
    """로그인 실패 기록 조회"""
    print_header("로그인 실패 기록")

    await init_db()

    async with async_session() as session:
        # 최근 24시간 로그인 실패
        since = datetime.utcnow() - timedelta(hours=24)

        result = await session.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.action == "login_failed",
                    AuditLog.created_at >= since
                )
            )
            .order_by(desc(AuditLog.created_at))
        )
        failures = result.scalars().all()

        print(f"\n최근 24시간 로그인 실패: {len(failures)}건")

        if not failures:
            print("✅ 로그인 실패 기록이 없습니다.")
            return

        # IP별 집계
        ip_counts = Counter(f.ip_address for f in failures if f.ip_address)
        if ip_counts:
            print("\n📊 IP별 실패 횟수:")
            for ip, count in ip_counts.most_common(10):
                warning = " ⚠️ 브루트포스 의심" if count >= 5 else ""
                print(f"   {ip}: {count}회{warning}")

        # 상세 로그
        print("\n📋 최근 실패 기록 (20건):")
        print("-" * 80)
        print(f"{'Time':<20} {'Admin ID':<10} {'IP Address':<18} {'Details':<25}")
        print("-" * 80)

        for f in failures[:20]:
            time_str = f.created_at.strftime("%Y-%m-%d %H:%M:%S")
            admin_id = str(f.admin_id) if f.admin_id else "N/A"
            ip = f.ip_address or "N/A"
            details = (f.details or "")[:23]
            print(f"{time_str:<20} {admin_id:<10} {ip:<18} {details:<25}")


async def check_suspicious_activity():
    """의심스러운 활동 탐지"""
    print_header("의심스러운 활동 탐지")

    await init_db()
    alerts = []

    async with async_session() as session:
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        # 1. 잠긴 계정 확인
        result = await session.execute(
            select(Admin).where(Admin.locked_until > now)
        )
        locked_admins = result.scalars().all()
        if locked_admins:
            alerts.append(f"🔒 잠긴 계정: {len(locked_admins)}개")
            for admin in locked_admins:
                print(f"   - {admin.username} (해제: {admin.locked_until})")

        # 2. 시간당 로그인 실패 5회 이상인 IP
        result = await session.execute(
            select(AuditLog.ip_address, func.count(AuditLog.log_id))
            .where(
                and_(
                    AuditLog.action == "login_failed",
                    AuditLog.created_at >= hour_ago
                )
            )
            .group_by(AuditLog.ip_address)
            .having(func.count(AuditLog.log_id) >= 5)
        )
        suspicious_ips = result.all()
        if suspicious_ips:
            alerts.append(f"🎯 브루트포스 의심 IP: {len(suspicious_ips)}개")
            for ip, count in suspicious_ips:
                print(f"   - {ip}: {count}회/시간")

        # 3. 대량 출금 요청 (24시간 내 5건 이상)
        result = await session.execute(
            select(Withdrawal.user_id, func.count(Withdrawal.id), func.sum(Withdrawal.amount))
            .where(Withdrawal.created_at >= day_ago)
            .group_by(Withdrawal.user_id)
            .having(func.count(Withdrawal.id) >= 5)
        )
        high_volume_users = result.all()
        if high_volume_users:
            alerts.append(f"💸 대량 출금 사용자: {len(high_volume_users)}명")
            for user_id, count, total in high_volume_users:
                print(f"   - User {user_id}: {count}건, {float(total):,.2f} USDT")

        # 4. 비정상적인 시간대 로그인 (새벽 2-5시)
        result = await session.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.action == "login",
                    AuditLog.created_at >= day_ago,
                    func.extract('hour', AuditLog.created_at).between(2, 5)
                )
            )
        )
        late_logins = result.scalars().all()
        if late_logins:
            alerts.append(f"🌙 새벽 로그인: {len(late_logins)}건")

        # 5. 동시 다중 세션 (같은 계정 5개 이상 활성 세션)
        result = await session.execute(
            select(AdminSession.admin_id, func.count(AdminSession.id))
            .where(
                and_(
                    AdminSession.is_revoked == False,
                    AdminSession.expires_at > now
                )
            )
            .group_by(AdminSession.admin_id)
            .having(func.count(AdminSession.id) >= 5)
        )
        multi_sessions = result.all()
        if multi_sessions:
            alerts.append(f"👥 다중 세션: {len(multi_sessions)}계정")

        # 결과 출력
        if alerts:
            print("\n🚨 탐지된 이상 활동:")
            for alert in alerts:
                print(f"   {alert}")
        else:
            print("\n✅ 의심스러운 활동이 탐지되지 않았습니다.")


async def view_audit_logs():
    """감사 로그 조회"""
    print_header("감사 로그 조회")

    await init_db()

    print("\n조회 옵션:")
    print("  1. 전체 (최근 50건)")
    print("  2. 로그인/로그아웃")
    print("  3. 관리자 관리")
    print("  4. 출금 관련")
    print("  5. 설정 변경")

    choice = input("\n선택: ").strip()

    action_filter = None
    if choice == "2":
        action_filter = ["login", "logout", "login_failed", "logout_all"]
    elif choice == "3":
        action_filter = ["create_admin", "update_admin", "delete_admin"]
    elif choice == "4":
        action_filter = ["withdrawal_approve", "withdrawal_reject", "withdrawal_manual"]
    elif choice == "5":
        action_filter = ["update_config", "change_password", "2fa_enabled", "2fa_disabled"]

    async with async_session() as session:
        query = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(50)

        if action_filter:
            query = query.where(AuditLog.action.in_(action_filter))

        result = await session.execute(query)
        logs = result.scalars().all()

        if not logs:
            print("\n로그가 없습니다.")
            return

        print("\n" + "-" * 100)
        print(f"{'Time':<20} {'Admin':<12} {'Action':<20} {'Resource':<20} {'IP':<15}")
        print("-" * 100)

        for log in logs:
            time_str = log.created_at.strftime("%Y-%m-%d %H:%M")
            admin = str(log.admin_id) if log.admin_id else "N/A"
            action = log.action[:18]
            resource = (log.resource_id or "")[:18]
            ip = (log.ip_address or "N/A")[:13]
            print(f"{time_str:<20} {admin:<12} {action:<20} {resource:<20} {ip:<15}")


async def check_security_config():
    """보안 설정 검토"""
    print_header("보안 설정 검토")

    issues = []
    recommendations = []

    # 1. 환경변수 검사
    print("\n📋 환경변수 검사:")

    # JWT Secret
    jwt_key = settings.jwt_secret_key
    if not jwt_key or len(jwt_key) < 32:
        issues.append("JWT_SECRET_KEY가 없거나 32자 미만입니다")
        print("   ❌ JWT_SECRET_KEY: 취약")
    else:
        print("   ✅ JWT_SECRET_KEY: 설정됨")

    # Encryption Salt
    enc_salt = getattr(settings, 'encryption_salt', None)
    if not enc_salt or len(enc_salt) < 16:
        issues.append("ENCRYPTION_SALT가 없거나 16자 미만입니다")
        print("   ❌ ENCRYPTION_SALT: 취약")
    else:
        print("   ✅ ENCRYPTION_SALT: 설정됨")

    # CLI Password
    cli_pwd = os.environ.get("CLI_ADMIN_PASSWORD")
    if not cli_pwd or len(cli_pwd) < 12:
        recommendations.append("CLI_ADMIN_PASSWORD를 12자 이상으로 설정하세요")
        print("   ⚠️  CLI_ADMIN_PASSWORD: 권장 길이 미달")
    else:
        print("   ✅ CLI_ADMIN_PASSWORD: 설정됨")

    # 2. 데이터베이스 검사
    print("\n📋 데이터베이스 검사:")

    await init_db()

    async with async_session() as session:
        # 비활성화되지 않은 Super Admin 수
        result = await session.execute(
            select(func.count(Admin.admin_id))
            .where(
                and_(
                    Admin.role == "super_admin",
                    Admin.is_active == True
                )
            )
        )
        super_admin_count = result.scalar()
        if super_admin_count > 3:
            recommendations.append(f"Super Admin이 {super_admin_count}명입니다. 최소화를 권장합니다")
            print(f"   ⚠️  Super Admin: {super_admin_count}명 (3명 이하 권장)")
        else:
            print(f"   ✅ Super Admin: {super_admin_count}명")

        # 2FA 미설정 Super Admin
        result = await session.execute(
            select(Admin)
            .where(
                and_(
                    Admin.role == "super_admin",
                    Admin.is_active == True,
                    Admin.is_2fa_enabled == False
                )
            )
        )
        no_2fa_admins = result.scalars().all()
        if no_2fa_admins:
            issues.append(f"2FA 미설정 Super Admin: {len(no_2fa_admins)}명")
            print(f"   ❌ 2FA 미설정 Super Admin: {len(no_2fa_admins)}명")
            for admin in no_2fa_admins:
                print(f"      - {admin.username}")
        else:
            print("   ✅ 모든 Super Admin 2FA 설정됨")

        # 오래된 세션
        week_ago = datetime.utcnow() - timedelta(days=7)
        result = await session.execute(
            select(func.count(AdminSession.id))
            .where(
                and_(
                    AdminSession.is_revoked == False,
                    AdminSession.created_at < week_ago
                )
            )
        )
        old_sessions = result.scalar()
        if old_sessions > 0:
            recommendations.append(f"7일 이상 된 활성 세션: {old_sessions}개")
            print(f"   ⚠️  오래된 세션: {old_sessions}개")

    # 3. 결과 요약
    print("\n" + "=" * 50)
    if issues:
        print_alert("발견된 보안 문제:")
        for issue in issues:
            print(f"   ❌ {issue}")

    if recommendations:
        print_warning("권장 사항:")
        for rec in recommendations:
            print(f"   ⚠️  {rec}")

    if not issues and not recommendations:
        print("\n✅ 보안 설정이 양호합니다.")


async def manage_blocked_ips():
    """IP 차단 관리"""
    print_header("IP 차단 관리")

    await init_db()

    async with async_session() as session:
        # 차단된 IP 목록 조회
        result = await session.execute(
            select(SystemSetting)
            .where(SystemSetting.key.like("blocked_ip_%"))
        )
        blocked = result.scalars().all()

        print(f"\n현재 차단된 IP: {len(blocked)}개")
        for b in blocked:
            ip = b.key.replace("blocked_ip_", "")
            reason = b.value
            print(f"   {ip}: {reason}")

        print("\n옵션:")
        print("  1. IP 차단 추가")
        print("  2. IP 차단 해제")
        print("  3. 돌아가기")

        choice = input("\n선택: ").strip()

        if choice == "1":
            ip = input("차단할 IP: ").strip()
            reason = input("차단 사유: ").strip() or "수동 차단"

            new_block = SystemSetting(
                key=f"blocked_ip_{ip}",
                value=reason,
                description=f"차단된 IP: {ip}",
                created_by="CLI_ADMIN"
            )
            session.add(new_block)
            await session.commit()
            print(f"✅ {ip} 차단됨")

        elif choice == "2":
            ip = input("차단 해제할 IP: ").strip()
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key == f"blocked_ip_{ip}")
            )
            block = result.scalar_one_or_none()
            if block:
                await session.delete(block)
                await session.commit()
                print(f"✅ {ip} 차단 해제됨")
            else:
                print(f"❌ {ip}는 차단 목록에 없습니다")


async def revoke_all_sessions():
    """모든 세션 무효화"""
    print_header("모든 세션 무효화")

    print_warning("모든 관리자가 로그아웃됩니다!")

    confirm = input("\n정말로 모든 세션을 무효화하시겠습니까? (yes 입력): ").strip()
    if confirm.lower() != "yes":
        print("취소됨.")
        return

    await init_db()

    async with async_session() as session:
        result = await session.execute(
            select(AdminSession).where(AdminSession.is_revoked == False)
        )
        sessions = result.scalars().all()

        count = 0
        for s in sessions:
            s.is_revoked = True
            s.revoked_at = datetime.utcnow()
            count += 1

        await session.commit()
        print(f"\n✅ {count}개 세션 무효화됨")


def show_menu():
    print_header("보안 감사 CLI")
    print("""
  1. 로그인 실패 기록 조회
  2. 의심스러운 활동 탐지
  3. 감사 로그 조회
  4. 보안 설정 검토
  5. IP 차단 관리
  6. 모든 세션 무효화 (위험)

  0. 종료
""")


async def main():
    if not require_password():
        return

    while True:
        show_menu()
        choice = input("선택: ").strip()

        if choice == "1":
            await check_failed_logins()
        elif choice == "2":
            await check_suspicious_activity()
        elif choice == "3":
            await view_audit_logs()
        elif choice == "4":
            await check_security_config()
        elif choice == "5":
            await manage_blocked_ips()
        elif choice == "6":
            await revoke_all_sessions()
        elif choice == "0":
            print("\n👋 종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다.")

        input("\n계속하려면 Enter를 누르세요...")


if __name__ == "__main__":
    asyncio.run(main())
