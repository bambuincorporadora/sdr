import httpx

from app.config import get_settings

settings = get_settings()


class EvolutionClient:
    def __init__(self) -> None:
        self.base_url = settings.evolution_base_url.rstrip("/")
        self.token = settings.evolution_token
        self.instance = settings.evolution_instance
        self.headers = {"apikey": self.token} if self.token else {}

    async def send_text(self, contato: str, texto: str) -> None:
        if not self.base_url:
            print("[evolution] base_url nao configurada, ignorando envio")
            return
        if self.instance:
            url = f"{self.base_url}/message/sendText/{self.instance}"
            payload = {"number": contato, "options": {"delay": 1200, "presence": "composing"}, "text": texto}
        else:
            url = f"{self.base_url}/messages"
            payload = {"to": contato, "type": "text", "text": texto}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=self.headers)
        if resp.status_code >= 400:
            print(f"[evolution] falha ao enviar texto: status={resp.status_code}, body={resp.text}, url={url}, payload={payload}")
        else:
            print(f"[evolution] texto enviado status={resp.status_code} para {contato}")

    async def send_media(self, contato: str, media_url: str, media_type: str = "image") -> None:
        if not self.base_url:
            print("[evolution] base_url nao configurada, ignorando envio de midia")
            return
        if self.instance:
            url = f"{self.base_url}/message/sendFile/{self.instance}"
            payload = {"number": contato, "file": media_url, "caption": ""}
        else:
            url = f"{self.base_url}/messages"
            payload = {"to": contato, "type": media_type, "url": media_url}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=self.headers)
        if resp.status_code >= 400:
            print(f"[evolution] falha ao enviar midia: status={resp.status_code}, body={resp.text}, url={url}, payload={payload}")
        else:
            print(f"[evolution] midia enviada status={resp.status_code} para {contato}")
