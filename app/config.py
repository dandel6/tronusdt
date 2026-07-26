"""설정 모듈"""
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

# 데이터 디렉토리 생성
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # ============ 마스터 시드 ============
    master_mnemonic: str = ""
    
    # ============ 메인 핫월렛 ============
    main_wallet_address: str = ""
    main_wallet_private_key: str = ""
    
    # ============ 콜드월렛 ============
    cold_wallet_address: Optional[str] = None
    
    # ============ TronGrid API ============
    trongrid_api_url: str = "https://api.trongrid.io"
    trongrid_api_key_1: str = ""
    trongrid_api_key_2: str = ""
    trongrid_api_key_3: str = ""
    
    @property
    def api_keys(self) -> List[str]:
        """사용 가능한 API 키 목록"""
        keys = [self.trongrid_api_key_1, self.trongrid_api_key_2, self.trongrid_api_key_3]
        return [k for k in keys if k]
    
    # ============ USDT 컨트랙트 ============
    usdt_contract: str = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    
    # ============ 데이터베이스 ============
    database_url: str = "sqlite+aiosqlite:///./data/gateway.db"
    
    # ============ 서버 설정 ============
    host: str = "0.0.0.0"
    port: int = 8000
    api_secret_key: str = ""

    # ============ JWT 보안 설정 ============
    jwt_secret_key: str = ""  # 필수: 최소 32자 이상의 랜덤 문자열
    jwt_algorithm: str = "HS256"

    # ============ 암호화 설정 ============
    encryption_salt: str = ""  # 필수: 최소 16자 이상의 랜덤 문자열

    # ============ CORS 설정 ============
    cors_origins: str = ""  # 쉼표로 구분된 허용 도메인 (예: "https://admin.example.com,https://app.example.com")
    
    # ============ 스위핑 설정 ============
    sweep_threshold_usdt: float = 10.0
    polling_interval_seconds: int = 300  # 5분
    required_confirmations: int = 25
    
    # ============ 에너지 설정 ============
    energy_per_transfer: int = 65000
    use_staking: bool = False
    use_energy_rental: bool = True
    
    # ============ 출금 설정 ============
    max_daily_withdrawal: float = 10000.0
    max_single_withdrawal: float = 5000.0
    
    # ============ 알림 설정 ============
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    alert_low_balance_threshold: float = 1000.0
    alert_large_withdrawal_threshold: float = 500.0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
