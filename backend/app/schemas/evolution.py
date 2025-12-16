from pydantic import BaseModel


class EvolutionMessage(BaseModel):
    mensagem_id: str
    contato: str
    tipo: str  # texto | audio | imagem | documento
    conteudo: str | None = None  # texto ou url de midia
    canal: str = "whatsapp"
    conversa_id: str | None = None
    nome: str | None = None
