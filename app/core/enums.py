"""
app/core/enums.py
Centraliza todos os Enumeradores do sistema SAA29.
"""

import enum


class StatusPane(str, enum.Enum):
    """
    Status possíveis de uma pane aeronáutica.
    Transições permitidas:
        ABERTA → EM_PESQUISA
        ABERTA → RESOLVIDA
        EM_PESQUISA → RESOLVIDA
    """
    ABERTA = "ABERTA"
    EM_PESQUISA = "EM_PESQUISA"
    RESOLVIDA = "RESOLVIDA"


class StatusItem(str, enum.Enum):
    """Status de um item de equipamento (por número de série)."""
    ATIVO = "ATIVO"
    ESTOQUE = "ESTOQUE"
    REMOVIDO = "REMOVIDO"


class StatusVencimento(str, enum.Enum):
    """Status de um controle de vencimento de manutenção."""
    OK = "OK"
    VENCENDO = "VENCENDO"   # próximo ao vencimento (threshold configurável)
    VENCIDO = "VENCIDO"


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
    Perfis do sistema (v1.0):
        - MANTENEDOR: execução de manutenção
        - ENCARREGADO: gestão operacional (+ permissões do mantenedor)
        - ADMINISTRADOR: gestão total do sistema (+ cadastro de aeronaves e efetivo)
    """
    MANTENEDOR = "MANTENEDOR"
    ENCARREGADO = "ENCARREGADO"
    ADMINISTRADOR = "ADMINISTRADOR"


class StatusAeronave(str, enum.Enum):
    """Status operacional de uma aeronave."""
    OPERACIONAL = "OPERACIONAL"
    MANUTENCAO = "MANUTENCAO"
    INATIVA = "INATIVA"


class TipoAnexo(str, enum.Enum):
    """Tipo de arquivo permitido como anexo de pane."""
    IMAGEM = "IMAGEM"
    DOCUMENTO = "DOCUMENTO"
