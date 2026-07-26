"""
Telegram 알림
"""
from typing import Optional
import httpx
from app.config import settings


class TelegramNotifier:
    """Telegram Bot 알림"""
    
    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.bot_token and self.chat_id)
    
    async def send(self, message: str) -> bool:
        """메시지 전송"""
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                })
                return response.status_code == 200
                
        except Exception as e:
            print(f"❌ Telegram 전송 실패: {e}")
            return False
    
    async def alert_deposit(self, user_id: int, amount: float, tx_id: str):
        """입금 알림"""
        message = (
            "💰 <b>입금 감지</b>\n"
            f"User: {user_id}\n"
            f"Amount: {amount} USDT\n"
            f"TX: <code>{tx_id}</code>"
        )
        await self.send(message)
    
    async def alert_withdrawal(self, user_id: int, amount: float, to_address: str, tx_id: str):
        """출금 알림"""
        message = (
            "📤 <b>출금 완료</b>\n"
            f"User: {user_id}\n"
            f"Amount: {amount} USDT\n"
            f"To: <code>{to_address}</code>\n"
            f"TX: <code>{tx_id}</code>"
        )
        await self.send(message)
    
    async def alert_sweep(self, from_address: str, amount: float, tx_id: str):
        """스위핑 알림"""
        message = (
            "🧹 <b>스위핑 완료</b>\n"
            f"From: <code>{from_address}</code>\n"
            f"Amount: {amount} USDT\n"
            f"TX: <code>{tx_id}</code>"
        )
        await self.send(message)
    
    async def alert_low_balance(self, balance: float):
        """잔액 부족 알림"""
        message = (
            "⚠️ <b>메인 지갑 잔액 부족</b>\n"
            f"현재 잔액: {balance} USDT\n"
            f"임계값: {settings.alert_low_balance_threshold} USDT"
        )
        await self.send(message)
    
    async def alert_large_withdrawal(self, user_id: int, amount: float, to_address: str):
        """대량 출금 알림"""
        message = (
            "🚨 <b>대량 출금 요청</b>\n"
            f"User: {user_id}\n"
            f"Amount: {amount} USDT\n"
            f"To: <code>{to_address}</code>\n"
            "확인이 필요합니다."
        )
        await self.send(message)
    
    async def alert_error(self, error_type: str, details: str):
        """오류 알림"""
        message = (
            f"❌ <b>오류 발생: {error_type}</b>\n"
            f"{details}"
        )
        await self.send(message)

    async def alert_startup(self, env_name: str = "Production"):
        """서버 시작 알림"""
        message = (
            "🚀 <b>TRON USDT Gateway 시작</b>\n"
            f"환경: {env_name}\n"
            "시스템이 온라인 상태입니다."
        )
        await self.send(message)

    async def alert_shutdown(self):
        """서버 종료 알림"""
        message = (
            "🛑 <b>TRON USDT Gateway 종료</b>\n"
            "시스템이 중단되었습니다."
        )
        await self.send(message)


# 싱글톤 인스턴스
notifier = TelegramNotifier()
