"""
Admin Backend Configuration Module
환경변수를 통해 보안 설정을 관리합니다.
"""
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Admin Backend 설정"""

    # ============ JWT 보안 설정 ============
    jwt_secret_key: str = ""  # 필수: 최소 32자 이상의 랜덤 문자열
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ============ 보안 설정 ============
    max_failed_attempts: int = 5
    lockout_duration_minutes: int = 30
    min_password_length: int = 12  # 보안 강화: 8 -> 12

    # ============ 데이터베이스 ============
    database_url: str = "sqlite+aiosqlite:///./data/gateway.db"

    # ============ CORS 설정 ============
    cors_origins: str = ""  # 쉼표로 구분된 허용 도메인

    class Config:
        env_file = ".env"
        extra = "ignore"

    def validate_jwt_secret(self) -> bool:
        """JWT 시크릿 키 유효성 검증"""
        if not self.jwt_secret_key:
            raise ValueError("JWT_SECRET_KEY is required. Set it in environment variables.")
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters.")
        return True


settings = Settings()
