"""
app/core/exceptions.py
Exceções de domínio tipadas para o SAA29.
Facilitam o tratamento de erros e evitam try/except repetitivos nos routers.
"""
from fastapi import HTTPException, status

class SAA29BaseException(HTTPException):
    """Classe base para todas as exceções do sistema."""
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)

class EntidadeNaoEncontradaError(SAA29BaseException):
    """Lançada quando um recurso (Aeronave, Item, Usuário) não existe."""
    def __init__(self, detail: str = "Recurso não encontrado"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)

class ConflitoNegocioError(SAA29BaseException):
    """Lançada quando uma regra de negócio impede a operação (ex: item já em uso)."""
    def __init__(self, detail: str = "Conflito na regra de negócio"):
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT)

class PermissaoNegadaError(SAA29BaseException):
    """Lançada quando o usuário não tem autorização para a ação."""
    def __init__(self, detail: str = "Acesso negado"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)
