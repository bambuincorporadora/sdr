from pydantic import BaseModel


class EvolutionMedia(BaseModel):
    url: str | None = None
    media_key: str | None = None
    direct_path: str | None = None
    message_type: str | None = None
    mime_type: str | None = None


class EvolutionMessage(BaseModel):
    mensagem_id: str
    contato: str
    tipo: str  # texto | audio | imagem | documento
    conteudo: str | None = None  # texto ou url de midia
    canal: str = "whatsapp"
    conversa_id: str | None = None
    nome: str | None = None
    media: EvolutionMedia | None = None
