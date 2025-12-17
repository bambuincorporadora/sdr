import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class EvolutionError(Exception):
    """Erro base para operacoes na Evolution."""


class EvolutionSendError(EvolutionError):
    """Erro ao enviar mensagem."""


class EvolutionMediaError(EvolutionError):
    """Erro ao resolver ou baixar midia."""


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

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        timeout = kwargs.pop("timeout", httpx.Timeout(10.0, read=15.0))
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, headers=self.headers, **kwargs)
        return resp

    async def send_text(self, contato: str, texto: str) -> None:
        if not self.base_url:
            raise EvolutionSendError("base_url_nao_configurada")
        if self.instance:
            url = f"{self.base_url}/message/sendText/{self.instance}"
            payload = {"number": contato, "options": {"delay": 1200, "presence": "composing"}, "text": texto}
        else:
            url = f"{self.base_url}/messages"
            payload = {"to": contato, "type": "text", "text": texto}
        try:
            resp = await self._request("POST", url, json=payload)
        except httpx.HTTPError as exc:  # pragma: no cover - network failure
            logger.error("HTTP erro Evolution texto destino=%s error=%s", _mask_contact(contato), exc)
            raise EvolutionSendError("http_error") from exc
        if resp.status_code >= 400:
            logger.error(
                "Falha Evolution texto status=%s destino=%s body=%s",
                resp.status_code,
                _mask_contact(contato),
                resp.text[:200],
            )
            raise EvolutionSendError(f"status_{resp.status_code}")
        logger.info("Texto enviado Evolution status=%s destino=%s", resp.status_code, _mask_contact(contato))

    async def send_media(self, contato: str, media_url: str, media_type: str = "image") -> None:
        if not self.base_url:
            raise EvolutionSendError("base_url_nao_configurada")
        if self.instance:
            url = f"{self.base_url}/message/sendFile/{self.instance}"
            payload = {"number": contato, "file": media_url, "caption": ""}
        else:
            url = f"{self.base_url}/messages"
            payload = {"to": contato, "type": media_type, "url": media_url}
        try:
            resp = await self._request("POST", url, json=payload)
        except httpx.HTTPError as exc:  # pragma: no cover - network failure
            logger.error("HTTP erro Evolution midia destino=%s error=%s", _mask_contact(contato), exc)
            raise EvolutionSendError("http_error") from exc
        if resp.status_code >= 400:
            logger.error(
                "Falha Evolution midia status=%s destino=%s body=%s",
                resp.status_code,
                _mask_contact(contato),
                resp.text[:200],
            )
            raise EvolutionSendError(f"status_{resp.status_code}")
        logger.info("Midia enviada Evolution status=%s destino=%s", resp.status_code, _mask_contact(contato))

    async def resolve_media_url(
        self,
        *,
        media_key: str,
        direct_path: str | None = None,
        message_type: str | None = None,
        message_id: str | None = None,
    ) -> str:
        if not self.base_url:
            raise EvolutionMediaError("base_url_nao_configurada")
        if not media_key:
            raise EvolutionMediaError("media_key_ausente")
        if self.instance:
            url = f"{self.base_url}/message/downloadMedia/{self.instance}"
        else:
            url = f"{self.base_url}/media/download"
        payload: dict[str, str | None] = {
            "mediaKey": media_key,
            "directPath": direct_path,
            "messageType": message_type,
            "messageId": message_id,
        }
        try:
            resp = await self._request("POST", url, json=payload, timeout=httpx.Timeout(15.0, read=60.0))
        except httpx.HTTPError as exc:  # pragma: no cover
            logger.error("HTTP erro ao resolver midia key=%s error=%s", media_key[:8], exc)
            raise EvolutionMediaError("http_error") from exc
        if resp.status_code >= 400:
            logger.error(
                "Falha ao resolver midia status=%s body=%s",
                resp.status_code,
                resp.text[:200],
            )
            raise EvolutionMediaError(f"status_{resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:  # pragma: no cover - mau payload
            logger.error("Resposta invalida resolver midia error=%s body=%s", exc, resp.text[:200])
            raise EvolutionMediaError("payload_invalido") from exc
        resolved = data.get("url") or data.get("mediaUrl")
        if not resolved:
            raise EvolutionMediaError("url_nao_disponivel")
        return resolved
