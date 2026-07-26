#!/usr/bin/env python3
"""
Switch Database to MySQL
"""
import sys
import os
import asyncio
from pathlib import Path

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from getpass import getpass

async def setup_mysql():
    print("=" * 60)
    print("  Configure MySQL Connection")
    print("=" * 60 + "\n")
    
    print("Please enter your MySQL credentials.")
    print("If you just installed MySQL, the user is likely 'root'.")
    
    host = input("Host [localhost]: ").strip() or "localhost"
    port = input("Port [3306]: ").strip() or "3306"
    user = input("Username [root]: ").strip() or "root"
    password = getpass("Password: ")
    
    db_name = input("Database Name [tron_gateway]: ").strip() or "tron_gateway"
    
    # Connection URL (Synchronous for checking)
    # Using pymysql directly to check connection and create DB
    try:
        import pymysql
        
        print(f"\n🔌 Connecting to MySQL at {host}:{port}...")
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            port=int(port)
        )
        
        cursor = conn.cursor()
        print(f"📦 Checking database '{db_name}'...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✅ Database '{db_name}' is ready.")
        
        conn.close()
        
    except ImportError:
        print("❌ 'pymysql' is not installed. Please run 'pip install -r requirements.txt' first.")
        return
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("Please check your password and ensure MySQL server is running.")
        return

    # Update .env file
    env_path = Path(__file__).parent.parent / ".env"
    
    # Async connection string for SQLAlchemy
    db_url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{db_name}"
    
    new_lines = []
    if env_path.exists():
        try:
            lines = env_path.read_text(encoding='utf-8').splitlines()
        except UnicodeDecodeError:
            # Fallback for Windows CP949 encoding
            lines = env_path.read_text(encoding='cp949').splitlines()
        
        for line in lines:
            if line.startswith("DATABASE_URL="):
                new_lines.append(f"DATABASE_URL={db_url}")
            else:
                new_lines.append(line)
    else:
        print("❌ .env file not found!")
        return
        
    env_path.write_text("\n".join(new_lines), encoding='utf-8')
    
    print("\n" + "=" * 60)
    print("✅ Configuration successful!")
    print("=" * 60)
    print(f"Updated .env with MySQL connection string.")
    print("\nNext steps:")
    print("1. Restart the server (python -m app.main)")
    print("2. Re-create Admin account (scripts/create_admin.py)")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    asyncio.run(setup_mysql())
