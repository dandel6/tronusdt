import sys
import os
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings

async def reset_db():
    print("WARNING: This will DROP all tables in the database.")
    
    # Create engine (ignoring 'mysql+aiomysql' string parsing for a moment, just using the URL)
    engine = create_async_engine(settings.database_url, echo=True)
    
    async with engine.begin() as conn:
        print("Dropping tables...")
        # Disable foreign key checks to allow dropping any order
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        # Drop tables
        await conn.execute(text("DROP TABLE IF EXISTS audit_logs"))
        await conn.execute(text("DROP TABLE IF EXISTS admin_sessions"))
        await conn.execute(text("DROP TABLE IF EXISTS admins"))
        await conn.execute(text("DROP TABLE IF EXISTS partners"))
        await conn.execute(text("DROP TABLE IF EXISTS system_configs"))
        
        # Re-enable foreign key checks
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        
    print("✅ All tables dropped. You can now re-run create_admin.py")
    await engine.dispose()

if __name__ == "__main__":
    if "mysql" not in settings.database_url:
        print("This script is for MySQL only.")
        sys.exit(1)
        
    asyncio.run(reset_db())
