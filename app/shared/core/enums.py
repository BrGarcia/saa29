"""
app/core/enums.py
Centraliza todos os Enumeradores do sistema SAA29.
"""

import enum


class StatusPane(str, enum.Enum):
    """
    Status possíveis de uma pane aeronáutica.
    Transições permitidas:
        ABERTA → RESOLVIDA
    """
    ABERTA = "ABERTA"
    RESOLVIDA = "RESOLVIDA"


class StatusItem(str, enum.Enum):
    """Status de um item de equipamento (por número de série)."""
    ATIVO = "ATIVO"
    ESTOQUE = "ESTOQUE"
    REMOVIDO = "REMOVIDO"


class StatusVencimento(str, enum.Enum):
    """Status de um controle de vencimento de manutenção."""
    OK = "OK"
    VENCENDO = "VENCENDO"
    VENCIDO = "VENCIDO"
    PRORROGADO = "PRORROGADO"


class OrigemControle(str, enum.Enum):
    """
    Define se o controle de vencimento foi herdado automaticamente
    do tipo de equipamento ou adicionado especificamente ao item.
    """
    PADRAO = "PADRAO"       # herdado do equipamento
    ESPECIFICO = "ESPECIFICO"   # adicionado diretamente ao item


class TipoPapel(str, enum.Enum):
    """
    Papel/função de um usuário responsável por uma pane.
    Perfis do sistema (v2.0):
        - MANTENEDOR: execução de manutenção
        - ENCARREGADO: gestão operacional (+ permissões do mantenedor)
        - INSPETOR: fiscalização e validação (não executa)
        - ADMINISTRADOR: gestão total do sistema (+ cadastro de aeronaves e efetivo)
    """
    MANTENEDOR = "MANTENEDOR"
    ENCARREGADO = "ENCARREGADO"
    INSPETOR = "INSPETOR"
    ADMINISTRADOR = "ADMINISTRADOR"


class StatusAeronave(str, enum.Enum):
    """Status operacional de uma aeronave."""
    DISPONIVEL = "DISPONIVEL"
    OPERACIONAL = "OPERACIONAL"
    INDISPONIVEL = "INDISPONIVEL"
    INSPECAO = "INSPEÇÃO"
    ESTOCADA = "ESTOCADA"
    INATIVA = "INATIVA"


class TipoAnexo(str, enum.Enum):
    """Tipo de arquivo permitido como anexo de pane."""
    IMAGEM = "IMAGEM"
    DOCUMENTO = "DOCUMENTO"


class TipoIndisponibilidade(str, enum.Enum):
    """Motivos para a indisponibilidade de um mantenedor.

    PARTICULAR: indisponibilidade permanece pública (que a pessoa está
    indisponível continua visível a todos), mas a `observacao` nunca é
    exposta pela API, para qualquer solicitante — ver `efetivo.service._to_out`.
    """
    FERIAS = "FERIAS"
    DISPENSA = "DISPENSA"
    FOLGA = "FOLGA"
    SERVICO = "SERVIÇO"
    OUTRO = "OUTRO"
    PARTICULAR = "PARTICULAR"


class StatusInspecao(str, enum.Enum):
    """Status operacional de uma inspeção."""
    ABERTA = "ABERTA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"


class StatusTarefaInspecao(str, enum.Enum):
    """Status de uma tarefa de inspeção."""
    PENDENTE = "PENDENTE"
    CONCLUIDA = "CONCLUIDA"
    NA = "N/A"


class RevisionStatus(str, enum.Enum):
    """
    Estado de revisão de um documento do acervo de manuais, vindo do campo
    `revision` do índice Lucene legado (`index_2.0/`).

    O índice usa 6 valores, não os 3 documentados: além de U/R/N aparecem
    '0', '1' e '2' residualmente (16 casos em 5.719 documentos medidos). Eles
    caem em DESCONHECIDO em vez de serem forçados em um dos três estados
    esperados — ver docs/backlog/modulo_publicacoes/02_formato_indice_lucene.md
    §6 armadilha 3. Documento sem entrada no índice também é DESCONHECIDO.
    """
    UNCHANGED = "UNCHANGED"        # 'U'
    REVISED = "REVISED"            # 'R'
    NOVO = "NOVO"                  # 'N'
    DESCONHECIDO = "DESCONHECIDO"  # '0'/'1'/'2' e ausência de entrada


class TipoPublicacao(str, enum.Enum):
    """Tipo de publicação avulsa (acervo B: BO/BS/NPO/BT)."""
    BO = "BO"
    BS = "BS"
    NPO = "NPO"
    BT = "BT"
    OUTRO = "OUTRO"


class StatusPublicacaoAvulsa(str, enum.Enum):
    """
    Estado de vigência de uma publicação avulsa.

    SUBSTITUIDO aponta para a publicação que a sucede via
    `substituida_por_id` — a cadeia de substituição é o que permite navegar
    da revisão antiga para a vigente sem descartar o histórico.
    """
    VIGENTE = "VIGENTE"
    CANCELADO = "CANCELADO"
    SUBSTITUIDO = "SUBSTITUIDO"


class StatusEdicao(str, enum.Enum):
    """
    Estado de uma edição do acervo de manuais no ciclo de republicação.

    ARQUIVADA descarta apenas artefatos de disco/R2 (PDFs, catalog.db da
    edição); as linhas de catálogo NUNCA sofrem hard delete, porque sustentam
    as FKs da auditoria de acesso (03_especificacao_tecnica.md §2.1).
    """
    AGUARDANDO_ATIVACAO = "AGUARDANDO_ATIVACAO"
    VIGENTE = "VIGENTE"
    ANTERIOR = "ANTERIOR"
    ARQUIVADA = "ARQUIVADA"
