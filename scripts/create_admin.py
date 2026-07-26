#!/usr/bin/env python3
"""
Root level Super Admin creation script
"""
import asyncio
import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from getpass import getpass
from app.db import init_db, async_session
from app.db.admin_models import Admin, AdminRole
from app.auth import hash_password

async def create_super_admin():
    print("=" * 60)
    print("  TRON Gateway - Super Admin Account Creation")
    print("=" * 60 + "\n")
    
    # Initialize DB
    await init_db()
    
    print("Please enter Super Admin details.\n")
    
    username = input("Username: ").strip()
    if not username:
        print("❌ Username is required.")
        return
    
    password = getpass("Password: ")
    if len(password) < 4: # Lowered limit for test convenience
        print("❌ Password too short.")
        return
        
    # Create account
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Admin).where(Admin.username == username)
        )
        if result.scalar_one_or_none():
            print("❌ Username already exists.")
            return
        
        admin = Admin(
            username=username,
            password_hash=hash_password(password),
            role=AdminRole.SUPER_ADMIN,
            is_active=True
        )
        session.add(admin)
        await session.commit()
        
        print("\n✅ Admin created successfully!")
        print(f"Username: {username}")

if __name__ == "__main__":
    asyncio.run(create_super_admin())
