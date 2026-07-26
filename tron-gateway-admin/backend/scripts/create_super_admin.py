#!/usr/bin/env python3
"""
초기 Super Admin 계정 생성 스크립트
처음 시스템 설정 시 한 번만 실행
"""
import asyncio
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from getpass import getpass
from app.db import init_db, async_session
from app.db.admin_models import Admin, AdminRole
from app.auth import hash_password


async def create_super_admin():
    """Super Admin 계정 생성"""
    print("=" * 60)
    print("  TRON Gateway - Super Admin 계정 생성")
    print("=" * 60 + "\n")
    
    # 데이터베이스 초기화
    await init_db()
    
    # 입력 받기
    print("Super Admin 계정 정보를 입력하세요.\n")
    
    email = input("이메일: ").strip()
    if not email:
        print("❌ 이메일은 필수입니다.")
        return
    
    username = input("사용자명: ").strip()
    if not username:
        print("❌ 사용자명은 필수입니다.")
        return
    
    password = getpass("비밀번호: ")
    if len(password) < 8:
        print("❌ 비밀번호는 8자 이상이어야 합니다.")
        return
    
    password_confirm = getpass("비밀번호 확인: ")
    if password != password_confirm:
        print("❌ 비밀번호가 일치하지 않습니다.")
        return
    
    full_name = input("이름 (선택): ").strip() or None
    
    # 계정 생성
    async with async_session() as session:
        # 중복 체크
        from sqlalchemy import select, or_
        result = await session.execute(
            select(Admin).where(
                or_(Admin.email == email, Admin.username == username)
            )
        )
        if result.scalar_one_or_none():
            print("❌ 이미 존재하는 이메일 또는 사용자명입니다.")
            return
        
        # 생성
        admin = Admin(
            email=email,
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            role=AdminRole.SUPER_ADMIN,
            is_active=True
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        
        print("\n" + "=" * 60)
        print("  ✅ Super Admin 계정이 생성되었습니다!")
        print("=" * 60)
        print(f"\n  이메일: {email}")
        print(f"  사용자명: {username}")
        print(f"  역할: Super Admin (최상위 관리자)")
        print("\n  이제 대시보드에 로그인할 수 있습니다.")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(create_super_admin())
