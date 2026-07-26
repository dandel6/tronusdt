"""
TRON USDT Gateway - 메인 엔트리포인트
"""
import asyncio
import signal
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db import init_db
from app.wallet import hd_wallet
from app.monitor import deposit_monitor
from app.sweeper import auto_sweeper
from app.withdrawal import withdrawal_processor
from app.api import app


# 스케줄러
scheduler = AsyncIOScheduler()


async def startup():
    """서비스 시작"""
    print("=" * 60)
    print("  TRON USDT Gateway - v2.0 (USERNAME LOGIN)")
    print("  입출금 자동화 서비스")
    print("=" * 60 + "\n")
    
    # 1. 데이터베이스 초기화
    print("📦 데이터베이스 초기화...")
    await init_db()
    
    # 2. HD Wallet 초기화
    print("🔐 HD Wallet 초기화...")
    hd_wallet.initialize()
    
    # 3. 스케줄러 설정
    setup_scheduler()
    scheduler.start()
    
    # 4. 입금 모니터 시작 (백그라운드)
    print("👀 입금 모니터 시작...")
    asyncio.create_task(deposit_monitor.start())
    
    # 5. 자동 스위퍼 시작 (백그라운드)
    print("🧹 자동 스위퍼 시작...")
    asyncio.create_task(auto_sweeper.start())
    
    print("\n✅ 모든 서비스 시작 완료!")
    print("=" * 60)
    print(f"  API: http://{settings.host}:{settings.port}")
    print(f"  Docs: http://{settings.host}:{settings.port}/docs")
    print("=" * 60 + "\n")


def setup_scheduler():
    """정기 작업 스케줄링"""
    
    # 출금 처리: 매 5분
    scheduler.add_job(
        withdrawal_processor.process_pending,
        'interval',
        minutes=5,
        id='process_withdrawals'
    )
    
    print("📅 스케줄된 작업:")
    print("   - 출금 처리: 5분마다")
    print(f"   - 입금 모니터: {settings.polling_interval_seconds}초마다")
    print(f"   - 자동 스위핑: {settings.polling_interval_seconds}초마다")


async def shutdown():
    """서비스 종료"""
    print("\n🛑 서비스 종료 중...")
    deposit_monitor.stop()
    auto_sweeper.stop()
    scheduler.shutdown()


# FastAPI 이벤트
@app.on_event("startup")
async def on_startup():
    await startup()


@app.on_event("shutdown")
async def on_shutdown():
    await shutdown()


def main():
    """메인 실행"""
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
