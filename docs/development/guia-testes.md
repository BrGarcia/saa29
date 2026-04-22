# Guia de Testes - SAA29

Documento sincronizado com a suite atual em 22/04/2026.

## 1. Filosofia

O projeto usa uma abordagem de TDD e valida tres frentes principais:

- testes unitarios de rotas e servicos;
- testes de seguranca;
- testes de arquitetura e performance.

## 2. Executar Testes

```bash
# Suite completa
pytest tests -q

# Suites por pasta
pytest tests/unit -q
pytest tests/security -q
pytest tests/architecture -q

# Arquivos especificos
pytest tests/unit/test_auth.py -q
pytest tests/unit/test_aeronaves.py -q
pytest tests/unit/test_panes.py -q
pytest tests/unit/test_equipamentos.py -q
pytest tests/unit/test_inventario.py -q

# Cobertura
pytest tests --cov=app --cov-report=term-missing
pytest tests --cov=app --cov-report=html
```

## 3. Estrutura da Suite

### `tests/unit`

Cobertura funcional dos modulos:

- `test_auth.py`
- `test_aeronaves.py`
- `test_panes.py`
- `test_equipamentos.py`
- `test_inventario.py`

### `tests/security`

Cobertura de seguranca:

- `test_csrf.py`
- `test_refresh_token.py`

### `tests/architecture`

Cobertura de arquitetura e verificacoes auxiliares:

- `test_architecture_solid.py`
- `test_performance_audit.py`
- `test_quality_helpers.py`

## 4. Infraestrutura de Testes

O `tests/conftest.py` atual fornece:

| Fixture | Descricao |
|---------|-----------|
| `criar_tabelas` | Cria e derruba o schema em SQLite in-memory |
| `db` | Sessao async com rollback ao final de cada teste |
| `client` | `AsyncClient` com `get_db` sobrescrito |
| `usuario_no_banco` | Usuario persistido direto no banco |
| `usuario_e_token` | Usuario autenticado com JWT e headers prontos |
| `client_autenticado` | Client com `get_current_user` sobrescrito |
| `usuario_mantenedor_e_token` | Usuario com papel de mantenedor |
| `usuario_encarregado_e_token` | Usuario com papel de encarregado |
| `dados_usuario_valido` | Payload base de usuario |
| `dados_usuario_secundario` | Segundo usuario para duplicidade |
| `dados_usuario_mantenedor` | Payload de mantenedor |
| `dados_aeronave_valida` | Payload base de aeronave |
| `dados_aeronave_secundaria` | Aeronave extra para testes |
| `dados_equipamento_valido` | Payload base de equipamento |
| `dados_tipo_controle_valido` | Payload de tipo de controle |

### Banco de testes

- SQLite in-memory;
- `STORAGE_BACKEND=local` forcado no setup de teste;
- `X-Skip-CSRF: true` ja e adicionado pelo client de teste;
- rate limiting e desativado durante a execucao dos testes.

## 5. Como Escrever um Teste

Estrutura recomendada:

```python
@pytest.mark.asyncio
async def test_criar_pane_sucesso(client, usuario_e_token, dados_aeronave_valida):
    ...
```

### Padrão

1. Prepare o estado com fixtures.
2. Execute a chamada HTTP com o `AsyncClient`.
3. Verifique status code e payload.
4. Cubra a regra de negocio principal e o erro esperado.

## 6. Casos que Merecem Cobertura

| Cenario | Esperado |
|---------|----------|
| Happy path | `200` ou `201` |
| Campo obrigatorio ausente | `422` |
| Recurso inexistente | `404` |
| Duplicidade | `409` |
| Sem autenticacao | `401` |
| Token invalido | `401` |
| Permissao insuficiente | `403` |
| Regra de negocio violada | `409` ou `400`, conforme o endpoint |

## 7. Padroes Ja Usados na Suite

- As chamadas autenticadas usam `Authorization: Bearer <token>`.
- Alguns testes reutilizam `usuario_e_token["headers"]`.
- O modulo de panes e o de equipamentos exigem atencao especial em relacoes e permissao por papel.

## 8. Meta de Qualidade

| Metrica | Meta |
|---------|------|
| Cobertura total | >= 80% |
| Cobertura por modulo | >= 75% |
| Falhas em `main` | 0 |
| Tempo total | abaixo de 30s, se possivel |

## 9. Observacao Final

Se voce mudar `app/bootstrap/main.py`, dependencias de autenticacao ou os modelos de dominio, rode pelo menos `tests/unit`, `tests/security` e `tests/architecture` antes de considerar a mudanca pronta.
