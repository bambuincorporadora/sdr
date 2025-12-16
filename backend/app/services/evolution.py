import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _mask_contact(contato: str) -> str:
    if not contato:
        return ""
    return f"...{contato[-4:]}"


class EvolutionClient:
    def __init__(self) -> None:
        self.base_url = settings.evolution_base_url.rstrip("/")
        self.token = settings.evolution_token
        self.instance = settings.evolution_instance
        self.headers = {"apikey": self.token} if self.token else {}

    async def send_text(self, contato: str, texto: str) -> None:
        if not self.base_url:
            logger.warning("Evolution base_url nao configurada, texto descartado destino=%s", _mask_contact(contato))
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
            logger.error(
                "Falha Evolution texto status=%s destino=%s body=%s",
                resp.status_code,
                _mask_contact(contato),
                resp.text[:200],
            )
        else:
            logger.info("Texto enviado Evolution status=%s destino=%s", resp.status_code, _mask_contact(contato))

    async def send_media(self, contato: str, media_url: str, media_type: str = "image") -> None:
        if not self.base_url:
            logger.warning("Evolution base_url nao configurada, midia descartada destino=%s", _mask_contact(contato))
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
            logger.error(
                "Falha Evolution midia status=%s destino=%s body=%s",
                resp.status_code,
                _mask_contact(contato),
                resp.text[:200],
            )
        else:
            logger.info("Midia enviada Evolution status=%s destino=%s", resp.status_code, _mask_contact(contato))
