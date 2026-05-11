"""
app/modules/auth/roles.py
Catálogo centralizado de papéis (funcao) válidos no SAA29.

REGRA: Adicionar novos papéis APENAS aqui.  Referenciar estas constantes
nos módulos em vez de repetir strings literais — evita aliases indevidos
(ex: "ADMIN" vs "ADMINISTRADOR") e facilita auditoria de segurança.
"""

# Papéis com privilégio operacional (podem agir em nome de terceiros)
PRIVILEGED_FUNCTIONS: frozenset[str] = frozenset({"ENCARREGADO", "ADMINISTRADOR"})

# Apenas o papel de administrador
ADMIN_FUNCTIONS: frozenset[str] = frozenset({"ADMINISTRADOR"})

# Todos os papéis válidos do sistema
ALL_FUNCTIONS: frozenset[str] = frozenset(
    {"MANTENEDOR", "INSPETOR", "ENCARREGADO", "ADMINISTRADOR"}
)
