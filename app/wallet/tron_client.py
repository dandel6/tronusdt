"""
Tron 블록체인 클라이언트
TronGrid API 연동
"""
from typing import Dict, Any, Optional, List
from decimal import Decimal
import asyncio
import httpx
from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

from app.config import settings


class TronClient:
    """
    Tron 블록체인 클라이언트
    - TronGrid API 연동
    - API 키 로테이션 지원
    """
    
    # USDT 컨트랙트 (6 decimals)
    USDT_DECIMALS = 6
    
    def __init__(self):
        self.api_url = settings.trongrid_api_url
        self.api_keys = settings.api_keys
        self._current_key_index = 0
        self._client: Optional[Tron] = None
    
    def _get_api_key(self) -> str:
        """API 키 로테이션"""
        if not self.api_keys:
            return ""
        key = self.api_keys[self._current_key_index]
        self._current_key_index = (self._current_key_index + 1) % len(self.api_keys)
        return key
    
    def _get_headers(self) -> dict:
        """API 요청 헤더"""
        headers = {"Content-Type": "application/json"}
        api_key = self._get_api_key()
        if api_key:
            headers["TRON-PRO-API-KEY"] = api_key
        return headers
    
    def get_client(self, private_key: str = None) -> Tron:
        """TronPy 클라이언트 생성"""
        api_key = self._get_api_key()
        if api_key:
            provider = HTTPProvider(self.api_url, api_key=api_key)
        else:
            provider = HTTPProvider(self.api_url)
        
        client = Tron(provider=provider)
        
        if private_key:
            client.private_key = PrivateKey(bytes.fromhex(private_key))
        
        return client
    
    # ==========================================
    # 잔액 조회
    # ==========================================
    
    def get_usdt_balance(self, address: str) -> Decimal:
        """USDT 잔액 조회"""
        try:
            client = self.get_client()
            contract = client.get_contract(settings.usdt_contract)
            balance = contract.functions.balanceOf(address)
            return Decimal(balance) / Decimal(10 ** self.USDT_DECIMALS)
        except Exception as e:
            print(f"❌ USDT 잔액 조회 실패 ({address}): {e}")
            return Decimal(0)
    
    def get_trx_balance(self, address: str) -> Decimal:
        """TRX 잔액 조회"""
        try:
            client = self.get_client()
            balance = client.get_account_balance(address)
            return Decimal(str(balance))
        except Exception as e:
            print(f"❌ TRX 잔액 조회 실패 ({address}): {e}")
            return Decimal(0)
    
    def get_account_resources(self, address: str) -> Dict[str, int]:
        """계정 리소스 조회 (에너지, 대역폭)"""
        try:
            client = self.get_client()
            resources = client.get_account_resource(address)
            return {
                "energy_limit": resources.get("EnergyLimit", 0),
                "energy_used": resources.get("EnergyUsed", 0),
                "energy_available": resources.get("EnergyLimit", 0) - resources.get("EnergyUsed", 0),
                "bandwidth_limit": resources.get("freeNetLimit", 0),
                "bandwidth_used": resources.get("freeNetUsed", 0),
            }
        except Exception as e:
            print(f"❌ 리소스 조회 실패 ({address}): {e}")
            return {"energy_limit": 0, "energy_used": 0, "energy_available": 0}
    
    # ==========================================
    # TRC-20 트랜잭션 조회 (TronGrid API)
    # ==========================================
    
    async def get_trc20_transactions(
        self,
        address: str,
        only_to: bool = True,
        only_confirmed: bool = True,
        limit: int = 100,
        min_timestamp: int = None
    ) -> List[Dict]:
        """
        TRC-20 트랜잭션 조회
        
        Args:
            address: 조회할 주소
            only_to: 받은 트랜잭션만 (입금)
            only_confirmed: 확인된 트랜잭션만
            limit: 최대 조회 수
            min_timestamp: 이 시간 이후 트랜잭션만
        """
        params = {
            "limit": limit,
            "contract_address": settings.usdt_contract,
            "only_confirmed": str(only_confirmed).lower(),
        }
        
        if only_to:
            params["only_to"] = "true"
        
        if min_timestamp:
            params["min_timestamp"] = min_timestamp
        
        url = f"{self.api_url}/v1/accounts/{address}/transactions/trc20"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._get_headers(), params=params)
                
                if response.status_code == 404:
                    return []  # 계정 미활성화
                
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
                
        except Exception as e:
            print(f"❌ TRC-20 트랜잭션 조회 실패 ({address}): {e}")
            return []
    
    # ==========================================
    # USDT 전송
    # ==========================================
    
    def send_usdt(
        self,
        private_key: str,
        to_address: str,
        amount: Decimal,
        fee_limit: int = 100_000_000  # 100 TRX
    ) -> Dict[str, Any]:
        """
        USDT TRC-20 전송
        
        Args:
            private_key: 발신자 개인키
            to_address: 수신자 주소
            amount: 전송량 (USDT)
            fee_limit: 최대 수수료 (SUN)
        """
        try:
            client = self.get_client(private_key)
            from_address = client.private_key.public_key.to_base58check_address()
            
            contract = client.get_contract(settings.usdt_contract)
            amount_sun = int(amount * Decimal(10 ** self.USDT_DECIMALS))
            
            txn = (
                contract.functions.transfer(to_address, amount_sun)
                .with_owner(from_address)
                .fee_limit(fee_limit)
                .build()
                .sign(client.private_key)
            )
            
            result = txn.broadcast().wait()
            
            print(f"✅ USDT 전송: {amount} USDT, {from_address} → {to_address}")
            print(f"   TX: {result['id']}")
            
            return {
                "success": True,
                "tx_id": result["id"],
                "amount": float(amount),
                "from": from_address,
                "to": to_address
            }
            
        except Exception as e:
            print(f"❌ USDT 전송 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==========================================
    # 트랜잭션 확인
    # ==========================================
    
    def get_transaction_info(self, tx_id: str) -> Dict[str, Any]:
        """트랜잭션 정보 조회"""
        try:
            client = self.get_client()
            info = client.get_transaction_info(tx_id)
            return {
                "confirmed": bool(info.get("id")),
                "block_number": info.get("blockNumber"),
                "fee": info.get("fee", 0) / 1_000_000,
                "energy_used": info.get("receipt", {}).get("energy_usage_total", 0),
                "result": info.get("receipt", {}).get("result", "UNKNOWN")
            }
        except Exception as e:
            return {"confirmed": False, "error": str(e)}
    
    def get_latest_block(self) -> int:
        """최신 블록 번호 조회"""
        try:
            client = self.get_client()
            block = client.get_latest_block()
            return block["block_header"]["raw_data"]["number"]
        except Exception as e:
            print(f"❌ 블록 조회 실패: {e}")
            return 0
    
    def is_valid_address(self, address: str) -> bool:
        """주소 유효성 검사"""
        try:
            client = self.get_client()
            return client.is_address(address)
        except:
            return False


# 싱글톤 인스턴스
tron_client = TronClient()
