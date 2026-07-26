"""
TRON USDT Gateway - Admin API Server
모든 라우터 통합
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.utils.notifier import notifier

# 라우터 임포트
from app.auth.auth_router import router as auth_router
from app.api.partner_router import router as partner_router
from app.api.dashboard_router import router as dashboard_router
from app.api.system_router import router as system_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 생명주기 관리"""
    # Startup
    print("🚀 Starting TRON Gateway Admin API...")
    await init_db()
    await notifier.alert_startup()
    yield
    # Shutdown
    await notifier.alert_shutdown()
    print("🛑 Shutting down...")


app = FastAPI(
    title="TRON USDT Gateway Admin API",
    description="3단계 RBAC 관리자 대시보드 API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://admin.yourdomain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router)
app.include_router(partner_router)
app.include_router(dashboard_router)
app.include_router(system_router)

# 기존 API 라우터도 포함 (하위 호환성)
# from app.api.server import app as legacy_app
# for route in legacy_app.routes:
#     app.routes.append(route)


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "ok", "service": "tron-gateway-admin"}


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "name": "TRON USDT Gateway Admin API",
        "version": "2.0.0",
        "docs": "/docs"
    }
