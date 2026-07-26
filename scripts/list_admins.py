import asyncio
import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import async_session
from app.db.admin_models import Admin
from sqlalchemy import select

async def list_admins():
    print("Connecting to database...")
    
    try:
        async with async_session() as session:
            result = await session.execute(
                select(Admin).order_by(Admin.admin_id)
            )
            admins = result.scalars().all()
            
            print("\n" + "="*85)
            print(f" {'ID':<5} | {'Username':<15} | {'Email':<25} | {'Role':<15} | {'Active'}")
            print("="*85)
            
            if not admins:
                print("  (No admin accounts found)")
            
            for admin in admins:
                active_str = "✅" if admin.is_active else "❌"
                email_str = admin.email if admin.email else "(none)"
                print(f" {admin.admin_id:<5} | {admin.username:<15} | {email_str:<25} | {admin.role.value:<15} | {active_str}")
                
            print("="*85 + "\n")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(list_admins())
