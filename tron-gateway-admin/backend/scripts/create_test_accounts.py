import asyncio
import sys
import os
import uuid
import secrets
import hashlib

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db import init_db, async_session
from app.db.admin_models import Admin, AdminRole, Partner
from app.auth import hash_password

async def create_test_accounts():
    await init_db()
    
    async with async_session() as session:
        print("🔍 테스트 계정 생성을 시작합니다...")

        # 0. Super Admin 생성
        result = await session.execute(select(Admin).where(Admin.email == 'admin@example.com'))
        if not result.scalar_one_or_none():
            admin = Admin(
                email='admin@example.com',
                username='admin',
                password_hash=hash_password('password123'),
                full_name='Super Admin',
                role=AdminRole.SUPER_ADMIN,
                is_active=True
            )
            session.add(admin)
            print("✅ Super Admin 계정 생성 완료")
        else:
            print("ℹ️ Super Admin 계정 이미 존재함")

        # 1. Partner 생성 (없으면)
        result = await session.execute(select(Partner).where(Partner.code == 'TEST01'))
        partner = result.scalar_one_or_none()
        
        if not partner:
            api_key = secrets.token_hex(32)
            api_secret = secrets.token_hex(32)
            api_secret_hash = hashlib.sha256(api_secret.encode()).hexdigest()
            
            partner = Partner(
                name="테스트 업체",
                code="TEST01",
                description="테스트용 파트너 업체입니다.",
                api_key=api_key,
                api_secret_hash=api_secret_hash
            )
            session.add(partner)
            await session.commit()
            await session.refresh(partner)
            print(f"✅ 파트너 생성 완료: {partner.name} (Code: {partner.code})")
        else:
            print(f"ℹ️ 기존 파트너 사용: {partner.name}")

        # 2. Partner Admin 생성
        result = await session.execute(select(Admin).where(Admin.email == 'partner_admin@example.com'))
        if not result.scalar_one_or_none():
            admin = Admin(
                email='partner_admin@example.com',
                username='partner_admin',
                password_hash=hash_password('password123'),
                full_name='Partner Admin',
                role=AdminRole.PARTNER_ADMIN,
                partner_id=partner.partner_id,
                is_active=True
            )
            session.add(admin)
            print("✅ Partner Admin 계정 생성 완료")
        else:
            print("ℹ️ Partner Admin 계정 이미 존재함")

        # 3. Partner Staff 생성
        result = await session.execute(select(Admin).where(Admin.email == 'partner_staff@example.com'))
        if not result.scalar_one_or_none():
            staff = Admin(
                email='partner_staff@example.com',
                username='partner_staff',
                password_hash=hash_password('password123'),
                full_name='Partner Staff',
                role=AdminRole.PARTNER_STAFF,
                partner_id=partner.partner_id,
                is_active=True
            )
            session.add(staff)
            print("✅ Partner Staff 계정 생성 완료")
        else:
            print("ℹ️ Partner Staff 계정 이미 존재함")

        await session.commit()
        
        print("\n" + "="*50)
        print("🎉 모든 테스트 계정 준비 완료")
        print("="*50)
        print("1. Super Admin (최상위 관리자)")
        print("   - Email: admin@example.com")
        print("   - PW:    password123")
        print("-" * 30)
        print("2. Partner Admin (업체 대표)")
        print("   - Email: partner_admin@example.com")
        print("   - PW:    password123")
        print("-" * 30)
        print("3. Partner Staff (업체 직원)")
        print("   - Email: partner_staff@example.com")
        print("   - PW:    password123")
        print("="*50)

if __name__ == "__main__":
    asyncio.run(create_test_accounts())
