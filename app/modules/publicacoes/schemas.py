"""
app/modules/publicacoes/schemas.py
Schemas Pydantic do módulo de publicações.

Naming `XCreate`/`XUpdate`/`XOut`/`XListItem` — convenção majoritária do
projeto (`docs/backlog/00_mapa_arquitetural.md`), não `XResponse`.

O contrato de `GET /publicacoes/api/busca` é herdado da `Especificacao.MD` §4 e
preservado deliberadamente, com uma única diferença: `doc_id` é UUID e não
inteiro, porque `manuais_documentos.id` é UUID determinístico (§2.2).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.core.enums import StatusEdicao, StatusPublicacaoAvulsa, TipoPublicacao


class ManualRef(BaseModel):
    """
    Bloco `manual` de cada resultado.

    Modelo próprio em vez de `dict` solto para que o `response_model` valide de
    fato e o bloco apareça no OpenAPI.
    """

    path: str
    description: str


class ResultadoBusca(BaseModel):
    doc_id: uuid.UUID
    title: str
    manual: ManualRef
    chapter: str
    page: int | None
    snippet: str
    """
    Trecho com os termos delimitados por `\\x02`/`\\x03`, NÃO por `<mark>`.

    O cliente escapa o snippet inteiro e só então troca os sentinelas pela tag
    (`publicacoes.js`) — é a única exceção justificada ao `escapeHtml` no
    projeto. Emitir HTML daqui seria XSS: o texto ao redor vem de PDF e, nas
    avulsas, de ementa digitada por usuário (achado B8).
    """
    viewer_url: str


class RespostaBusca(BaseModel):
    query: str
    total: int
    """Número de PÁGINAS que casam, não de documentos (§2.4)."""
    took_ms: int
    results: list[ResultadoBusca]


class ProcedimentoFim(BaseModel):
    """Uma mensagem de falha resolvida para o procedimento correspondente."""

    mensagem: str
    procedimento: str
    doc_id: uuid.UUID | None
    """NULL quando o procedimento não tem PDF no acervo (4 dos 253 do piloto)."""
    title: str | None
    viewer_url: str | None


class RespostaFim(BaseModel):
    total: int
    results: list[ProcedimentoFim]


class StatusPublicacoes(BaseModel):
    """
    Estado do módulo para a UI e para o diagnóstico de operação.

    `indice_disponivel=False` é resposta normal antes da primeira indexação — a
    UI mostra estado vazio, não erro (E-12).
    """

    indice_disponivel: bool
    edicao: str | None
    manuais: int
    documentos: int
    documentos_sem_texto: int
    """Dimensiona a necessidade de OCR (M4 tarefa 8)."""
    paginas_indexadas: int
    mensagens_fim: int
    atualizado_em: float | None


class EdicaoListItem(BaseModel):
    """Uma edição na tela de gerência (`/configuracoes`)."""

    id: uuid.UUID
    rotulo: str
    status: StatusEdicao
    data_publicacao: datetime
    manuais: int
    documentos: int
    indice_disponivel: bool
    """
    O `catalog.<rotulo>.db` está em disco?

    A UI só oferece "Ativar" quando `True` — ativar sem índice é recusado com
    409 pelo servidor, e oferecer um botão que será recusado é pior do que não
    oferecer.
    """
    tem_relatorio: bool
    snapshot_key: str | None


class RelatorioEdicaoOut(BaseModel):
    """
    Relatório de diff da publicação, como **texto puro**.

    Markdown cru de propósito: é o que `publicar.py` gravou, e a UI o exibe em
    `<pre>` escapado. Renderizar markdown exigiria um renderer no cliente para
    exibir contagens e nomes de arquivo — risco de XSS sem ganho.
    """

    edicao_id: uuid.UUID
    rotulo: str
    relatorio: str | None


class DuplicacaoOut(BaseModel):
    """Sobreposição por hash entre a edição vigente e a anterior (M4 tarefa 5)."""

    vigente: str | None
    anterior: str | None
    documentos_vigente: int
    documentos_anterior: int
    duplicados_por_hash: int
    bytes_potencialmente_economizaveis: int | None
    """
    Sempre `None` hoje: o tamanho do arquivo não é guardado no catálogo.
    Explícito em vez de estimado — um número inventado aqui viraria base de
    decisão de disco na VPS (D-04).
    """


class FavoritoCreate(BaseModel):
    """Exatamente um dos dois deve vir preenchido — mesmo XOR do `CheckConstraint` (achado B1)."""

    documento_id: uuid.UUID | None = None
    avulsa_id: uuid.UUID | None = None


class FavoritoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    documento_id: uuid.UUID | None
    avulsa_id: uuid.UUID | None
    created_at: datetime


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titulo: str
    capitulo: str
    ata_codigo: str | None
    paginas: int | None
    has_text: bool


# --------------------------------------------------------------------------
# Publicações avulsas (acervo B, M2)
# --------------------------------------------------------------------------


class PublicacaoAvulsaCreate(BaseModel):
    tipo: TipoPublicacao
    numero: str = Field(..., max_length=60)
    ano: int = Field(..., ge=1990, le=2100)
    data_emissao: date
    data_recebimento: date
    emissor: str = Field(..., max_length=100)
    titulo: str = Field(..., max_length=300)
    ementa: str = Field(
        ...,
        min_length=20,
        description="Campo mais valioso — mínimo de caracteres por ser o principal insumo de busca (R15)",
    )
    sistema_ata_id: uuid.UUID | None = None
    aplicabilidade: list[uuid.UUID] = Field(
        default_factory=list,
        description="IDs de aeronave. Vazio = aplicável à frota inteira (§9.2)",
    )


class PublicacaoAvulsaUpdate(BaseModel):
    titulo: str | None = Field(default=None, max_length=300)
    ementa: str | None = Field(default=None, min_length=20)
    emissor: str | None = Field(default=None, max_length=100)
    sistema_ata_id: uuid.UUID | None = None
    status_novo: StatusPublicacaoAvulsa | None = Field(
        default=None,
        alias="status",
        description="VIGENTE|CANCELADO|SUBSTITUIDO — usar junto com substituida_por_id ao substituir",
    )
    substituida_por_id: uuid.UUID | None = None


class AnexoAvulsaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome_original: str
    tamanho_bytes: int
    principal: bool
    created_at: datetime


class PublicacaoAvulsaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: TipoPublicacao
    numero: str
    ano: int
    data_emissao: date
    data_recebimento: date
    emissor: str
    titulo: str
    ementa: str
    status: StatusPublicacaoAvulsa
    sistema_ata_id: uuid.UUID | None
    substituida_por_id: uuid.UUID | None
    ativo: bool
    created_at: datetime
    anexos: list[AnexoAvulsaOut] = Field(default_factory=list)


class PublicacaoAvulsaListItem(BaseModel):
    id: uuid.UUID
    tipo: TipoPublicacao
    numero: str
    ano: int
    titulo: str
    status: StatusPublicacaoAvulsa
    data_recebimento: date
    snippet: str | None = None
    """
    Trecho da ementa ao redor do termo buscado, com sentinelas `\\x02`/`\\x03`
    — NUNCA `<mark>` cru (achado B8). Só preenchido quando a busca tem
    `texto`; None quando a listagem é sem filtro de texto.
    """


class RespostaListaAvulsas(BaseModel):
    total: int
    results: list[PublicacaoAvulsaListItem]


class DocumentoViewerOut(BaseModel):
    """
    Metadados exibidos no cabeçalho do viewer.

    `equivalente_vigente_id` é o que sustenta o banner "REVISÃO ANTERIOR"
    exigido em `03_especificacao_tecnica.md` §2.2: como o `document_id` inclui
    a edição (achado B2), abrir um link antigo abre o documento da edição
    ANTIGA de propósito — mas a UI precisa oferecer o caminho de volta para a
    edição vigente, casando por `(manual_codigo, file_key)`.
    """

    id: uuid.UUID
    titulo: str
    manual: ManualRef
    capitulo: str
    paginas: int | None
    edicao_rotulo: str
    edicao_vigente: bool
    equivalente_vigente_id: uuid.UUID | None
