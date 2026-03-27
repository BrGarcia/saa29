# Guia de Testes – SAA29

## Filosofia

Seguimos **TDD (Test-Driven Development)** conforme o Método Akita:

```
1. Escrever o teste (RED – falha esperada)
2. Implementar o mínimo para passar (GREEN)
3. Refatorar mantendo os testes verdes (REFACTOR)
```

**Nunca** submeter código funcional sem o teste correspondente.

---

## Executar Testes

```bash
# Todos os testes
pytest tests/ -v

# Um módulo específico
pytest tests/test_panes.py -v

# Uma classe específica
pytest tests/test_panes.py::TestCriarPane -v

# Um teste específico
pytest tests/test_panes.py::TestCriarPane::test_criar_pane_sucesso -v

# Com cobertura
pytest tests/ --cov=app --cov-report=term-missing
pytest tests/ --cov=app --cov-report=html  # relatório em htmlcov/

# Apenas testes rápidos (unit)
pytest tests/ -m unit

# Ignorar testes lentos
pytest tests/ -m "not slow"
```

---

## Infraestrutura de Testes (conftest.py)

O `tests/conftest.py` fornece:

| Fixture | Escopo | Descrição |
|---------|--------|-----------|
| `criar_tabelas` | `session` | Cria/derruba todas as tabelas (SQLite in-memory) |
| `db` | `function` | Sessão com rollback automático após cada teste |
| `client` | `function` | `AsyncClient` httpx com `get_db` sobrescrito |
| `dados_usuario_valido` | `function` | Dict com dados mock de usuário |
| `dados_aeronave_valida` | `function` | Dict com dados mock de aeronave |
| `dados_pane_valida` | `function` | Dict com dados mock de pane |
| `dados_equipamento_valido` | `function` | Dict com dados mock de equipamento |

### Banco de testes
- **SQLite in-memory** – sem necessidade de PostgreSQL rodando
- Rollback automático após cada teste (sem contaminação de dados)
- Rápido – adequado para CI

---

## Como Escrever um Teste

### Estrutura Given / When / Then

```python
@pytest.mark.asyncio
async def test_criar_pane_sucesso(self, client: AsyncClient, dados_pane_valida: dict):
    """
    DADO um usuário autenticado e uma aeronave existente
    QUANDO enviar POST /panes/ com dados válidos
    ENTÃO retornar pane com status=ABERTA e HTTP 201
    """
    # GIVEN
    # (fixtures já criam o estado necessário)
    headers = {"Authorization": "Bearer <token_válido>"}
    
    # WHEN
    response = await client.post("/panes/", json=dados_pane_valida, headers=headers)
    
    # THEN
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ABERTA"          # RN-02
    assert body["data_conclusao"] is None
    assert "id" in body
```

### Testando regras de negócio específicas

```python
async def test_criar_pane_descricao_vazia_padrao(self, client, headers):
    """RN-05: descrição vazia deve virar 'AGUARDANDO EDICAO'"""
    payload = {**dados_pane_valida, "descricao": ""}
    
    response = await client.post("/panes/", json=payload, headers=headers)
    
    assert response.status_code == 201
    assert response.json()["descricao"] == "AGUARDANDO EDICAO"
```

---

## Casos a Sempre Testar

Para cada endpoint, cubra:

| Cenário | Exemplo |
|---------|---------|
| Happy path | Dados válidos → 201/200 |
| Campo obrigatório faltando | Sem `matricula` → 422 |
| Recurso não encontrado | ID inexistente → 404 |
| Duplicata | username repetido → 409 |
| Sem autenticação | Sem token → 401 |
| Token inválido | Token adulterado → 401 |
| Regra de negócio violada | Concluir pane já resolvida → 409 |
| Edge case | Descrição vazia → padrão "AGUARDANDO EDICAO" |

---

## Mocks e Fixtures Adicionais

Se precisar de um usuário autenticado em múltiplos testes, crie uma fixture:

```python
# tests/conftest.py (adicionar)
@pytest_asyncio.fixture
async def token_autenticado(client: AsyncClient, dados_usuario_valido: dict) -> str:
    """Cria usuário e retorna token JWT para uso nos testes."""
    # 1. Criar usuário
    await client.post("/auth/usuarios", json=dados_usuario_valido)
    # 2. Fazer login
    response = await client.post("/auth/login", data={
        "username": dados_usuario_valido["username"],
        "password": dados_usuario_valido["password"],
    })
    return response.json()["access_token"]

@pytest_asyncio.fixture
def auth_headers(token_autenticado: str) -> dict:
    return {"Authorization": f"Bearer {token_autenticado}"}
```

---

## Métricas de Qualidade

| Métrica | Meta |
|---------|------|
| Cobertura total | ≥ 80% |
| Cobertura por módulo | ≥ 75% |
| Testes falhando | 0 em `main` |
| Tempo total da suite | < 30 segundos |
