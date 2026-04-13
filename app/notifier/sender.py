"""알림 인터페이스. 텔레그램은 토큰 발급 후 활성화."""
from abc import ABC, abstractmethod
import httpx
from app.config import settings

class Notifier(ABC):
    @abstractmethod
    async def send(self, text: str) -> None: ...

class ConsoleNotifier(Notifier):
    async def send(self, text: str) -> None:
        print("===== MORNING BRIEF =====")
        print(text)
        print("=========================")

class TelegramNotifier(Notifier):
    async def send(self, text: str) -> None:
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            print("[WARN] Telegram not configured, falling back to console.")
            return await ConsoleNotifier().send(text)
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown",
            })
            r.raise_for_status()

def get_notifier() -> Notifier:
    return TelegramNotifier() if settings.telegram_bot_token else ConsoleNotifier()
