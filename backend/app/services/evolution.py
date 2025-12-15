import httpx

from app.config import get_settings

settings = get_settings()


class EvolutionClient:
    def __init__(self) -> None:
        self.base_url = settings.evolution_base_url.rstrip("/")
        self.token = settings.evolution_token
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def send_text(self, contato: str, texto: str) -> None:
        if not self.base_url:
            return
        url = f"{self.base_url}/messages"
        payload = {"to": contato, "type": "text", "text": texto}
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload, headers=self.headers)

    async def send_media(self, contato: str, media_url: str, media_type: str = "image") -> None:
        if not self.base_url:
            return
        url = f"{self.base_url}/messages"
        payload = {"to": contato, "type": media_type, "url": media_url}
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload, headers=self.headers)
