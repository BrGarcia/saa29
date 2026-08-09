"""
app/shared/core/db_utils.py
Utilitários de banco compartilhados entre módulos.

Existe para que módulos não precisem importar helpers privados uns dos outros
(ex.: o antigo `panes.service._escape_like` usado por `equipamentos.service`).
"""


def escape_like(text: str) -> str:
    """Escapa curingas de LIKE/ILIKE para evitar pattern matching indesejado (SEC-07).

    O resultado deve ser usado sempre com `escape="\\\\"` na query:

        coluna.ilike(f"%{escape_like(termo)}%", escape="\\\\")

    Args:
        text: Termo de busca informado pelo usuário.

    Returns:
        Termo com `\\`, `%` e `_` escapados.
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
