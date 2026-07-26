"""
HD Wallet 관리
BIP44 경로: m/44'/195'/0'/0/{user_id}
195 = Tron 코인 타입 (SLIP-0044)
"""
import base64
import logging
from datetime import datetime
from typing import Tuple, Optional
from mnemonic import Mnemonic
from hdwallet import HDWallet
from tronpy.keys import PrivateKey
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import UserWallet

# 보안 로깅 설정
logger = logging.getLogger(__name__)


class HDWalletManager:
    """
    HD Wallet 관리자
    - BIP39 니모닉에서 BIP44 경로로 주소 파생
    - 개인키 암호화 저장
    """
    
    # BIP44 경로 템플릿
    DERIVATION_PATH = "m/44'/195'/0'/0/{index}"
    
    def __init__(self):
        self.mnemonic_handler = Mnemonic("english")
        self._master_seed: Optional[bytes] = None
        self._fernet: Optional[Fernet] = None
    
    def initialize(self):
        """마스터 시드 초기화"""
        # 니모닉 존재 여부 검증
        if not settings.master_mnemonic:
            raise ValueError(
                "MASTER_MNEMONIC이 설정되지 않았습니다. "
                ".env 파일에 24단어 니모닉을 설정하세요."
            )

        # 니모닉 길이 검증 (24단어 = 약 200자 이상)
        words = settings.master_mnemonic.strip().split()
        if len(words) != 24:
            raise ValueError(
                f"니모닉은 24단어여야 합니다. 현재: {len(words)}단어. "
                "보안을 위해 24단어(256비트) 니모닉을 사용하세요."
            )

        # 니모닉 유효성 검증
        if not self.mnemonic_handler.check(settings.master_mnemonic):
            raise ValueError("유효하지 않은 니모닉입니다. BIP39 표준 단어를 확인하세요.")

        # 마스터 시드 생성
        self._master_seed = self.mnemonic_handler.to_seed(settings.master_mnemonic)

        # 암호화 키 초기화
        self._init_encryption()

        print("HD Wallet 초기화 완료")

    def _init_encryption(self):
        """Fernet 암호화 키 초기화 (환경변수 Salt 사용)"""
        # API 시크릿 키 검증
        if not settings.api_secret_key or len(settings.api_secret_key) < 16:
            raise ValueError(
                "API_SECRET_KEY가 설정되지 않았거나 너무 짧습니다. "
                ".env 파일에 최소 16자 이상의 랜덤 문자열을 설정하세요."
            )

        # 암호화 Salt 검증 (환경변수에서 로드)
        if not settings.encryption_salt or len(settings.encryption_salt) < 16:
            raise ValueError(
                "ENCRYPTION_SALT가 설정되지 않았거나 너무 짧습니다. "
                ".env 파일에 최소 16자 이상의 랜덤 문자열을 설정하세요. "
                "생성 방법: python -c \"import secrets; print(secrets.token_hex(16))\""
            )

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=settings.encryption_salt.encode(),  # 환경변수에서 Salt 로드
            iterations=480000,  # OWASP 권장값으로 증가 (100000 -> 480000)
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(settings.api_secret_key.encode()))
        self._fernet = Fernet(derived_key)
    
    def encrypt_private_key(self, private_key: str) -> str:
        """개인키 암호화"""
        return self._fernet.encrypt(private_key.encode()).decode()
    
    def decrypt_private_key(self, encrypted: str) -> str:
        """개인키 복호화"""
        return self._fernet.decrypt(encrypted.encode()).decode()
    
    def derive_wallet(self, user_id: int) -> Tuple[str, str, str]:
        """
        사용자 ID로 지갑 파생
        
        Returns:
            (address, private_key_hex, derivation_path)
        """
        if not self._master_seed:
            raise ValueError("HD Wallet이 초기화되지 않았습니다")
        
        # BIP44 경로
        path = self.DERIVATION_PATH.format(index=user_id)
        
        # HD Wallet 파생
        hdwallet = HDWallet(symbol="TRX")
        hdwallet.from_seed(self._master_seed)
        hdwallet.from_path(path)
        
        # 개인키 추출
        private_key_hex = hdwallet.private_key()
        
        # Tron 주소 생성
        private_key = PrivateKey(bytes.fromhex(private_key_hex))
        address = private_key.public_key.to_base58check_address()
        
        return address, private_key_hex, path
    
    async def create_user_wallet(
        self, 
        session: AsyncSession, 
        user_id: int
    ) -> dict:
        """
        사용자 지갑 생성 또는 기존 지갑 반환
        """
        # 기존 지갑 확인
        result = await session.execute(
            select(UserWallet).where(UserWallet.user_id == user_id)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            return {
                "user_id": user_id,
                "address": existing.wallet_address,
                "is_new": False
            }
        
        # 새 지갑 생성
        address, private_key_hex, path = self.derive_wallet(user_id)
        encrypted_key = self.encrypt_private_key(private_key_hex)
        
        # DB 저장
        wallet = UserWallet(
            user_id=user_id,
            wallet_address=address,
            private_key_encrypted=encrypted_key,
            derivation_path=path
        )
        session.add(wallet)
        await session.commit()
        
        print(f"✅ 지갑 생성: user_id={user_id}, address={address}")
        
        return {
            "user_id": user_id,
            "address": address,
            "is_new": True
        }
    
    async def get_user_wallet(
        self, 
        session: AsyncSession, 
        user_id: int
    ) -> Optional[UserWallet]:
        """사용자 지갑 조회"""
        result = await session.execute(
            select(UserWallet).where(UserWallet.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_wallet_by_address(
        self, 
        session: AsyncSession, 
        address: str
    ) -> Optional[UserWallet]:
        """주소로 지갑 조회"""
        result = await session.execute(
            select(UserWallet).where(UserWallet.wallet_address == address)
        )
        return result.scalar_one_or_none()
    
    async def get_all_addresses(self, session: AsyncSession) -> list:
        """모든 사용자 주소 조회"""
        result = await session.execute(select(UserWallet.wallet_address))
        return [row[0] for row in result.fetchall()]
    
    async def get_private_key(
        self,
        session: AsyncSession,
        user_id: int,
        reason: str = "unspecified",
        caller: str = "unknown"
    ) -> str:
        """
        사용자 개인키 조회 (복호화)

        보안 경고: 이 함수는 내부 시스템 용도로만 사용되어야 합니다.
        - 출금 처리 (withdrawal_processor)
        - 스위핑 처리 (auto_sweeper)

        Args:
            session: DB 세션
            user_id: 사용자 ID
            reason: 접근 사유 (감사 로그용)
            caller: 호출자 식별자 (감사 로그용)

        Returns:
            복호화된 개인키
        """
        wallet = await self.get_user_wallet(session, user_id)
        if not wallet:
            raise ValueError(f"지갑을 찾을 수 없습니다: user_id={user_id}")

        # 보안 감사 로그 기록
        logger.warning(
            "개인키 접근 감지",
            extra={
                "event": "private_key_access",
                "user_id": user_id,
                "wallet_address": wallet.wallet_address[:10] + "...",  # 마스킹
                "reason": reason,
                "caller": caller,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return self.decrypt_private_key(wallet.private_key_encrypted)

    async def get_private_key_by_address(
        self,
        session: AsyncSession,
        address: str,
        reason: str = "unspecified",
        caller: str = "unknown"
    ) -> str:
        """
        주소로 개인키 조회 (복호화) - 스위핑 전용

        Args:
            session: DB 세션
            address: 지갑 주소
            reason: 접근 사유 (감사 로그용)
            caller: 호출자 식별자 (감사 로그용)
        """
        wallet = await self.get_wallet_by_address(session, address)
        if not wallet:
            raise ValueError(f"지갑을 찾을 수 없습니다: address={address}")

        # 보안 감사 로그 기록
        logger.warning(
            "개인키 접근 감지 (주소 기반)",
            extra={
                "event": "private_key_access",
                "user_id": wallet.user_id,
                "wallet_address": address[:10] + "...",
                "reason": reason,
                "caller": caller,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return self.decrypt_private_key(wallet.private_key_encrypted)
    
    @staticmethod
    def generate_mnemonic() -> str:
        """새 24단어 니모닉 생성"""
        return Mnemonic("english").generate(strength=256)
    
    @staticmethod
    def validate_mnemonic(mnemonic: str) -> bool:
        """니모닉 유효성 검사"""
        return Mnemonic("english").check(mnemonic)


# 싱글톤 인스턴스
hd_wallet = HDWalletManager()
