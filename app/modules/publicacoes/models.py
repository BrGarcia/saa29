"""
app/modules/publicacoes/models.py
Models SQLAlchemy do módulo de publicações.

Cobre os dois acervos, conforme
docs/backlog/modulo_publicacoes/03_especificacao_tecnica.md §2.1:

- Acervo A (manuais do DVD, M1): manuais_edicoes, manuais, manuais_documentos,
  manuais_fim_map, publicacoes_acessos
- Acervo B (avulsas, M2): publicacoes_avulsas, publicacao_avulsa_anexos,
  publicacao_avulsa_aeronaves
- Transversal (M3): publicacoes_favoritos

Contrato que atravessa o módulo inteiro: o índice de busca (`catalog.db`) NÃO
mora aqui e nunca entra no Alembic — é SQLite dedicado, gerado offline por
`python -m scripts.publicacoes.indexar` e aberto em runtime com `sqlite3` puro
(ADR-004). Só o catálogo LEVE (as tabelas abaixo) vive no banco principal.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base
from app.shared.core.enums import (
    RevisionStatus,
    StatusEdicao,
    StatusPublicacaoAvulsa,
    TipoPublicacao,
)

if TYPE_CHECKING:
    from app.modules.aeronaves.models import Aeronave


class ManualEdicao(Base):
    """
    Uma edição do acervo — a unidade de republicação anual (RN-08).

    Nasce já no M1 populada com uma única linha sintética
    (`rotulo="piloto-fim"`, `status=VIGENTE`) para que `manuais.edicao_id` tenha
    destino desde a primeira migration; o fluxo de ativação/reversão só ganha UI
    e significado real no M4.

    **Nunca sofre hard delete.** `ARQUIVADA` descarta apenas artefatos de
    disco/R2 (PDFs, `catalog.db` da edição); as linhas de catálogo permanecem,
    porque sustentam as FKs de `publicacoes_acessos` (achado B4).
    """

    __tablename__ = "manuais_edicoes"
    __table_args__ = (
        # No máximo uma edição VIGENTE. Índice PARCIAL: ANTERIOR e ARQUIVADA
        # podem repetir à vontade — só o estado "em vigor" é exclusivo.
        #
        # Rede de segurança do que `service.ativar_edicao` já valida em Python
        # dentro da transação. A validação em Python dá a mensagem legível; o
        # índice cobre o caso que ela não vê: dois processos ativando ao mesmo
        # tempo, cada um na sua transação. Sem ele, o banco aceitaria duas
        # linhas VIGENTE e a busca passaria a depender de qual tem
        # `data_publicacao` maior — falha silenciosa, não erro.
        Index(
            "uq_manuais_edicoes_vigente_unica",
            "status",
            unique=True,
            sqlite_where=text("status = 'VIGENTE'"),
            postgresql_where=text("status = 'VIGENTE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rotulo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        comment="Rótulo da edição (ex: '2027', 'piloto-fim') — entra no UUID v5 dos documentos",
    )
    data_publicacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        comment="Quando a edição foi publicada no SAA29",
    )
    snapshot_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Chave do snapshot ZIP no R2 (M4)"
    )
    hash_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Hash do snapshot inteiro (M4)"
    )
    status: Mapped[StatusEdicao] = mapped_column(
        Enum(StatusEdicao, native_enum=False, length=20),
        nullable=False,
        default=StatusEdicao.AGUARDANDO_ATIVACAO,
        index=True,
    )
    publicado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="NULL quando a edição foi criada por script offline, sem usuário logado",
    )
    relatorio_diff: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Markdown do relatório de diff da publicação (M4)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    manuais: Mapped[list["Manual"]] = relationship(
        back_populates="edicao", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ManualEdicao rotulo={self.rotulo!r} status={self.status}>"


class Manual(Base):
    """Um manual (diretório de primeiro nível do acervo) dentro de uma edição."""

    __tablename__ = "manuais"
    __table_args__ = (
        UniqueConstraint("edicao_id", "codigo", name="uq_manuais_edicao_codigo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    edicao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manuais_edicoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codigo: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="Nome do diretório do manual (ex: 'FIM_1741', 'AMM_PART1_1651')",
    )
    descricao_pt: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Descrição legível — de categorias_manuais.toml, com fallback para o código",
    )
    categoria: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        default="Outros",
        index=True,
        comment="De categorias_manuais.toml (RN-04); manual desconhecido cai em 'Outros' (E-04)",
    )
    path: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Caminho relativo ao PUBLICACOES_ACERVO_DIR"
    )
    revisao: Mapped[str | None] = mapped_column(String(10), nullable=True)
    revisao_data: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    edicao: Mapped["ManualEdicao"] = relationship(back_populates="manuais")
    documentos: Mapped[list["ManualDocumento"]] = relationship(
        back_populates="manual", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Manual codigo={self.codigo!r}>"


class ManualDocumento(Base):
    """
    Um PDF do acervo — o catálogo LEVE, sem texto.

    O texto extraído página a página vive só no `catalog.db`; aqui ficam os
    metadados que a navegação e a auditoria precisam. O `id` é **determinístico**
    (UUID v5, `catalog.documento_id_deterministico`) e é o mesmo valor usado como
    `document_id` no `catalog.db`, o que dispensa tabela de mapeamento entre os
    dois bancos (§2.2).

    ⚠️ Ao levar um `document_id` do `catalog.db` para uma query ORM, converter
    **sempre** com `uuid.UUID(valor)`: o SQLite grava o tipo `Uuid` como hex sem
    hífens e a comparação crua de strings falha em silêncio (§2.2.1, achado B5).
    """

    __tablename__ = "manuais_documentos"
    __table_args__ = (
        UniqueConstraint(
            "manual_id", "file_key", name="uq_manuais_documentos_manual_file"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        comment="UUID v5 determinístico de (edição, manual, file_key) — sem default aleatório",
    )
    manual_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manuais.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capitulo: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        comment="Último segmento de `chapter` (Lucene) ou do diretório físico",
    )
    # SEM FK de propósito (achado B3): o acervo cobre 28 capítulos ATA e
    # `sistemas_ata` seeda 8 — com PRAGMA foreign_keys=ON, uma FK reprovaria a
    # indexação de 20 dos 28 capítulos do piloto. O join acontece em query,
    # quando o código existir do outro lado.
    ata_codigo: Mapped[str | None] = mapped_column(String(4), nullable=True, index=True)
    file_key: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Caminho relativo ao diretório de entrada"
    )
    titulo: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="RN-02: título do Lucene quando houver, senão nome de arquivo tratado",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=9999,
        comment="Prefixo numérico do nome do arquivo (RN-05); sem prefixo vai para o fim",
    )
    paginas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_text: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False quando o PDF não tem camada de texto (E-01) — some da busca, não da navegação",
    )
    revision_status: Mapped[RevisionStatus] = mapped_column(
        Enum(RevisionStatus, native_enum=False, length=20),
        nullable=False,
        default=RevisionStatus.DESCONHECIDO,
    )
    hash_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Dedup entre edições retidas (M4)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    manual: Mapped["Manual"] = relationship(back_populates="documentos")

    def __repr__(self) -> str:
        return f"<ManualDocumento titulo={self.titulo!r}>"


class ManualFimMap(Base):
    """
    Mensagem de falha (CAS/EICAS) → procedimento do FIM, vinda de `fim.json`.

    `documento_id` é nullable porque nem todo procedimento precisa ter PDF
    indexado. No acervo completo os 253 procedimentos do `fim.json` têm
    correspondente (medido em `test_regressao_fim_json_e_cobertura_do_piloto`),
    mas indexar um subconjunto — uma amostra, um manual só — deixa o resto sem
    documento. Um procedimento sem PDF continua sendo informação útil: a
    mensagem resolve para um código que o mecânico procura no manual em papel.
    """

    __tablename__ = "manuais_fim_map"
    __table_args__ = (
        UniqueConstraint("mensagem", name="uq_manuais_fim_map_mensagem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Sem `index=True`: a UniqueConstraint abaixo já cria o índice único que a
    # busca por mensagem usa — um segundo índice sobre a mesma coluna só custa
    # escrita.
    mensagem: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Ex: 'ADC 001'"
    )
    procedimento: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, comment="Ex: '34-15-00-810-801-A'"
    )
    documento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("manuais_documentos.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ManualFimMap {self.mensagem!r} -> {self.procedimento!r}>"


class PublicacaoAcesso(Base):
    """
    Auditoria de acesso a documento (RBAC.md §4: toda ação crítica é auditável).

    Duas decisões que parecem detalhe e não são (achado B4): `documento_id` é
    `SET NULL` e existe um **snapshot do título**. O indexador remove documentos
    que sumiram do acervo (RN-09); com CASCADE, cada reindexação apagaria em
    silêncio o histórico de quem os consultou. Auditoria que some junto com o
    objeto auditado não é auditoria.

    `edicao_id` fecha a rastreabilidade "qual revisão estava em vigor quando" —
    é o que sustenta "a pane de março seguiu o procedimento vigente em março".
    """

    __tablename__ = "publicacoes_acessos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    documento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("manuais_documentos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    documento_titulo: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="Snapshot do título no acesso — legível mesmo após remoção do documento",
    )
    edicao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manuais_edicoes.id", ondelete="RESTRICT"), nullable=False
    )
    pagina: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quando: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<PublicacaoAcesso usuario={self.usuario_id} doc={self.documento_id}>"


class PublicacaoAvulsa(Base):
    """
    BO/BS/NPO/BT — publicação avulsa (acervo B), independente do acervo de
    manuais (acervo A): não usa `catalog.db` nem `pypdfium2`, só o banco
    principal.

    `ementa` é o campo mais valioso — é o principal insumo de busca (R15 do
    parecer), daí o comprimento mínimo garantido em schemas.py em vez de aqui
    (Pydantic valida na entrada; a coluna em si só reforça `nullable=False`).

    Cadeia de substituição via `substituida_por_id`: quando uma publicação é
    substituída, ela vira `SUBSTITUIDO` e passa a apontar para a nova — o
    histórico nunca é apagado, só marcado.
    """

    __tablename__ = "publicacoes_avulsas"
    __table_args__ = (
        UniqueConstraint(
            "tipo", "numero", "ano", name="uq_publicacoes_avulsas_tipo_numero_ano"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tipo: Mapped[TipoPublicacao] = mapped_column(
        Enum(TipoPublicacao, native_enum=False, length=10), nullable=False, index=True
    )
    numero: Mapped[str] = mapped_column(
        String(60), nullable=False, comment="Ex: 'BS 314-24-0021'"
    )
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    data_emissao: Mapped[date] = mapped_column(Date, nullable=False)
    data_recebimento: Mapped[date] = mapped_column(
        Date, nullable=False, comment="Data que conta para o esquadrão (§9.2 do parecer)"
    )
    emissor: Mapped[str] = mapped_column(String(100), nullable=False)
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    ementa: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Campo mais valioso — principal insumo de busca"
    )
    sistema_ata_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sistemas_ata.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    status: Mapped[StatusPublicacaoAvulsa] = mapped_column(
        Enum(StatusPublicacaoAvulsa, native_enum=False, length=15),
        nullable=False,
        default=StatusPublicacaoAvulsa.VIGENTE,
        index=True,
    )
    substituida_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publicacoes_avulsas.id", ondelete="SET NULL"), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True, comment="Soft delete"
    )
    cadastrada_por_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    anexos: Mapped[list["PublicacaoAvulsaAnexo"]] = relationship(
        back_populates="avulsa", cascade="all, delete-orphan"
    )
    aeronaves: Mapped[list["PublicacaoAvulsaAeronave"]] = relationship(
        back_populates="avulsa", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PublicacaoAvulsa {self.tipo} {self.numero!r}/{self.ano}>"


class PublicacaoAvulsaAnexo(Base):
    """
    Um anexo de publicação avulsa — tipicamente o PDF escaneado do documento.

    Sem `updated_at` de propósito: o anexo é imutável — se o arquivo estiver
    errado, é reenviado como um novo anexo, nunca sobrescrito.
    """

    __tablename__ = "publicacao_avulsa_anexos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    avulsa_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publicacoes_avulsas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_key: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Retorno de StorageService.upload()"
    )
    nome_original: Mapped[str] = mapped_column(String(255), nullable=False)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    principal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Qual anexo abre por padrão quando há mais de um",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    avulsa: Mapped["PublicacaoAvulsa"] = relationship(back_populates="anexos")

    def __repr__(self) -> str:
        return f"<PublicacaoAvulsaAnexo {self.nome_original!r}>"


class PublicacaoAvulsaAeronave(Base):
    """
    Aplicabilidade N:N entre publicação avulsa e aeronave.

    Ausência de linhas para uma `avulsa_id` = aplicável à frota inteira
    (§9.2 do parecer) — não confundir "nenhuma linha" com "nenhuma aeronave".
    """

    __tablename__ = "publicacao_avulsa_aeronaves"

    avulsa_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publicacoes_avulsas.id", ondelete="CASCADE"), primary_key=True
    )
    aeronave_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeronaves.id", ondelete="CASCADE"), primary_key=True
    )

    avulsa: Mapped["PublicacaoAvulsa"] = relationship(back_populates="aeronaves")
    aeronave: Mapped["Aeronave"] = relationship()


class PublicacaoFavorito(Base):
    """
    Favorito transversal aos dois acervos — M3.

    **Correção da revisão de pré-implementação** (achado B1): o desenho
    original usava PK composta com `documento_id`/`avulsa_id` nullable, que é
    inválido em SQL padrão (coluna de PK não pode ser nullable — falha no
    Postgres; no SQLite "funciona" por um quirk histórico e aceita duplicatas
    silenciosamente, porque `NULL != NULL` na comparação de chave).

    Redesenhado com PK surrogate (`id`) + `CheckConstraint` XOR garantindo
    exatamente um alvo preenchido + duas `UniqueConstraint` separadas — NULLs
    são distintos em UNIQUE tanto no SQLite quanto no Postgres, então
    duplicatas reais são bloqueadas e os NULLs não conflitam entre si.
    """

    __tablename__ = "publicacoes_favoritos"
    __table_args__ = (
        CheckConstraint(
            "(documento_id IS NULL) != (avulsa_id IS NULL)",
            name="ck_publicacoes_favoritos_alvo_unico",
        ),
        UniqueConstraint(
            "usuario_id", "documento_id", name="uq_publicacoes_favoritos_usuario_documento"
        ),
        UniqueConstraint(
            "usuario_id", "avulsa_id", name="uq_publicacoes_favoritos_usuario_avulsa"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    documento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("manuais_documentos.id", ondelete="CASCADE"), nullable=True
    )
    avulsa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publicacoes_avulsas.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        alvo = self.documento_id or self.avulsa_id
        return f"<PublicacaoFavorito usuario={self.usuario_id} alvo={alvo}>"
