from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from pdfminer.high_level import extract_text as extract_pdf_text
from pydantic import BaseModel

try:
    from docx import Document as DocxDocument
except ImportError:  # pragma: no cover - optional dependency
    DocxDocument = None

from app.config import get_settings
from app.services.evolution import EvolutionClient, EvolutionMediaError
from app.utils.db import get_supabase_client

logger = logging.getLogger(__name__)


class AttachmentProcessingError(Exception):
    ...


class AttachmentExtractionResult(BaseModel):
    attachment_id: str | None = None
    markdown: str
    metadata: dict[str, Any] = {}
    summary: str
    caption: str | None = None


class AttachmentService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = get_supabase_client()
        self.evolution = EvolutionClient()
        self.bucket = self.settings.attachments_bucket

    async def process_document(
        self,
        *,
        conversa_id: str,
        mensagem_id: str,
        media: Any,
        conteudo: str | None,
        caption: str | None = None,
    ) -> AttachmentExtractionResult:
        temp_path = await self._download_media(media=media, conteudo=conteudo)
        try:
            mime_type = self._guess_mime_type(temp_path, media)
            if mime_type not in {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
                raise AttachmentProcessingError(f"mime_type_nao_suportado:{mime_type}")
            sha256 = self._file_sha256(temp_path)
            attachment_id, storage_path = await self._store_attachment(
                conversa_id=conversa_id,
                mensagem_id=mensagem_id,
                mime_type=mime_type,
                sha256=sha256,
                temp_path=temp_path,
            )
            markdown, metadata = await asyncio.to_thread(self._extract_markdown, temp_path, mime_type)
            summary = (markdown[:800] + "...") if len(markdown) > 800 else markdown
            await self._store_extraction(attachment_id, markdown, metadata)
            return AttachmentExtractionResult(
                attachment_id=attachment_id,
                markdown=markdown,
                metadata=metadata,
                summary=summary,
                caption=caption,
            )
        finally:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

    async def _download_media(self, *, media: Any, conteudo: str | None) -> str:
        if media and getattr(media, "url", None):
            url = media.url
        elif conteudo and conteudo.startswith("http"):
            url = conteudo
        elif media and media.media_key:
            try:
                url = await self.evolution.resolve_media_url(
                    media_key=media.media_key,
                    direct_path=getattr(media, "direct_path", None),
                    message_type=getattr(media, "message_type", None),
                )
            except EvolutionMediaError as exc:
                raise AttachmentProcessingError(f"nao_foi_possivel_resolver: {exc}") from exc
        else:
            raise AttachmentProcessingError("url_indisponivel")

        self._validate_url(url)
        timeout = httpx.Timeout(10.0, read=40.0)
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        total = 0
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as http:
                async with http.stream("GET", url) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes(64 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > self.settings.document_max_bytes:
                            raise AttachmentProcessingError("documento_maior_que_limite")
                        temp_file.write(chunk)
        except Exception as exc:  # pragma: no cover - network issues
            temp_file.close()
            os.unlink(temp_file.name)
            raise AttachmentProcessingError(f"download_falhou:{exc}") from exc
        temp_file.flush()
        temp_file.close()
        return temp_file.name

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"https"}:
            raise AttachmentProcessingError("url_invalida")
        host = (parsed.hostname or "").lower()
        allowed_hosts = self.settings.trusted_media_hosts
        if allowed_hosts and host not in allowed_hosts:
            raise AttachmentProcessingError("host_nao_permitido")

    def _guess_mime_type(self, path: str, media: Any) -> str:
        if media and getattr(media, "mime_type", None):
            return media.mime_type  # type: ignore[attr-defined]
        mime, _ = mimetypes.guess_type(path)
        return mime or "application/octet-stream"

    def _file_sha256(self, path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    async def _store_attachment(
        self,
        *,
        conversa_id: str,
        mensagem_id: str,
        mime_type: str,
        sha256: str,
        temp_path: str,
    ) -> tuple[str, str | None]:
        ext = Path(temp_path).suffix or mimetypes.guess_extension(mime_type) or ".bin"
        storage_path = f"{conversa_id}/{mensagem_id}/{uuid4().hex}{ext}"
        storage_url: str | None = None
        try:
            with open(temp_path, "rb") as fh:
                self.client.storage.from_(self.bucket).upload(storage_path, fh, {"content-type": mime_type})
            storage_url = storage_path
        except Exception as exc:  # pragma: no cover - storage opcional
            logger.warning("Falha ao salvar documento no storage caminho=%s error=%s", storage_path, exc)

        def _insert():
            res = (
                self.client.table("attachments")
                .insert(
                    {
                        "conversa_id": conversa_id,
                        "mensagem_id": mensagem_id,
                        "mime_type": mime_type,
                        "ext": ext,
                        "size_bytes": os.path.getsize(temp_path),
                        "sha256": sha256,
                        "storage_path": storage_url,
                        "status": "uploaded",
                    }
                )
                .execute()
            )
            return res.data[0]["id"]

        attachment_id = await asyncio.to_thread(_insert)
        return attachment_id, storage_url

    async def _store_extraction(self, attachment_id: str, markdown: str, metadata: dict[str, Any]) -> None:
        def _insert():
            return (
                self.client.table("attachment_extractions")
                .insert(
                    {
                        "attachment_id": attachment_id,
                        "markdown": markdown,
                        "metadata": metadata,
                        "tokens_est": len(markdown.split()),
                    }
                )
                .execute()
            )

        await asyncio.to_thread(_insert)

    def _extract_markdown(self, path: str, mime_type: str) -> tuple[str, dict[str, Any]]:
        if mime_type == "application/pdf":
            text = extract_pdf_text(path) or ""
            metadata = {"source": "pdf"}
        elif mime_type in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }:
            if DocxDocument is None:
                raise AttachmentProcessingError("python-docx-nao-disponivel")
            doc = DocxDocument(path)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            text = "\n\n".join(paragraphs)
            metadata = {"source": "docx", "paragraphs": len(paragraphs)}
        else:
            raise AttachmentProcessingError("mime_type_nao_suportado")
        markdown = text.strip()
        if not markdown:
            raise AttachmentProcessingError("documento_sem_conteudo")
        return markdown, metadata


attachment_service = AttachmentService()
