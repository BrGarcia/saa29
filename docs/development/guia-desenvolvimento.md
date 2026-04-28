# Guia de Desenvolvimento - SAA29

Documento sincronizado com o codigo-fonte em 22/04/2026.

## 1. Ambiente de Desenvolvimento

### Requisitos

- Python 3.12+
- Git 2.x
- SQLite como banco padrao local
- PostgreSQL 16+ apenas se voce for testar migracao manual

### Setup rapido

```bash
git clone <repo>
cd SAA29
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env

# Cria o schema no banco configurado em DATABASE_URL
python -m alembic upgrade head

# Bootstrap inicial: admin e frota padrao
python scripts/db/init_db.py

# Seed de desenvolvimento
python scripts/db/seed.py

# Sementes auxiliares de dominio
python scripts/seed_equipamentos.py
python scripts/seed_30_panes.py

# Executa a aplicacao
python scripts/run_app.py
```

## 2. Scripts Reais do Repositorio

Os entry points atualmente usados no repositorio sao:

- `scripts/run_app.py` para subir a aplicacao com Uvicorn.
- `scripts/db/init_db.py` para bootstrap de admin e frota padrao.
- `scripts/db/seed.py` para dados de desenvolvimento.
- `scripts/seed_equipamentos.py` para catalogo, slots e itens de teste.
- `scripts/seed_30_panes.py` para panes de exemplo.
- `scripts/maintenance/r2_manager.py` para backup e restore do banco SQLite via R2.
- `scripts/maintenance/reset_admin.py` para reset de senha do administrador.

Observacao:

- o arquivo `scripts/start.sh` ainda existe no repositorio, mas ha referencias legadas nele. Para desenvolvimento local, prefira os comandos acima.

## 3. Banco de Dados

### Padrao atual

- `DATABASE_URL=sqlite+aiosqlite:///./saa29_local.db`
- `app/bootstrap/database.py` cria a engine async e habilita `PRAGMA foreign_keys=ON`, `journal_mode=WAL` e `synchronous=NORMAL` para SQLite.

### Regra operacional atual

- O banco atual ja esta em uso e deve ser preservado.
- As panes ja cadastradas precisam permanecer intactas durante a fase de ajuste fino.
- Nao recrie, resete, trunque nem rode seed sobre a base ativa.
- Qualquer mudanca de schema ou dados exige backup previo do banco original.
- Quando houver risco, teste a mudanca primeiro em uma copia do banco.

### Quando usar PostgreSQL

- apenas para testes de migracao ou ambiente externo;
- requer `asyncpg` instalado no ambiente;
- exige que `DATABASE_URL` use o formato `postgresql+asyncpg://...`.

### Manutencao basica

- backup local: copie `saa29_local.db`;
- inspeção: use `sqlite3 saa29_local.db` ou DBeaver/DB Browser for SQLite;
- migracoes: sempre revise o arquivo gerado em `migrations/versions/` antes de aplicar.

### Cuidados obrigatorios na base ativa

- Antes de aplicar migracao ou ajuste manual na base ativa, crie uma copia preservada do arquivo original.
- `scripts/db/seed.py`, `scripts/seed_equipamentos.py` e `scripts/seed_30_panes.py` devem ser usados apenas em banco descartavel ou copia de trabalho.
- Se a mudanca tocar dados existentes, valide primeiro em uma copia do banco e registre o plano de retorno.

## 4. Estrutura de um modulo

```
app/modules/<modulo>/
├── models.py
├── schemas.py
├── service.py
└── router.py
```

Responsabilidades:

| Arquivo | Faz | Nao faz |
|---------|-----|---------|
| `models.py` | Define entidades e relacoes ORM | Regras de negocio |
| `schemas.py` | Valida e serializa dados | Acessa banco |
| `service.py` | Aplica regras e orquestra casos de uso | Fala HTTP |
| `router.py` | Recebe request e devolve response | Implementa regra de negocio |

## 5. Fluxo Recomendado de Mudanca

1. Ajuste `models.py` e `schemas.py`.
2. Atualize o `service.py`.
3. Ajuste o `router.py`.
4. Gere migracao com Alembic.
5. Rode a suite de testes.
6. Atualize a documentacao em `docs/`.

## 6. Bootstrap e Variaveis de Ambiente

O projeto carrega configuracao por `app/bootstrap/config.py`.

Variaveis relevantes do `.env.example`:

- `DATABASE_URL`
- `APP_ENV`
- `APP_DEBUG`
- `APP_SECRET_KEY`
- `DEFAULT_ADMIN_USER`
- `DEFAULT_ADMIN_PASSWORD`
- `JWT_ALGORITHM`
- `JWT_EXPIRE_MINUTES`
- `UPLOAD_DIR`
- `MAX_UPLOAD_SIZE_MB`
- `STORAGE_BACKEND`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT`
- `R2_BUCKET_NAME`

Observacoes:

- `APP_SECRET_KEY` e obrigatoria e nao pode ser fraca.
- `DEFAULT_ADMIN_PASSWORD` e obrigatoria para bootstrap e seed.
- `STORAGE_BACKEND` aceita `local` ou `r2`.

## 7. Deploy Local e Railway

### Local

- Use SQLite com `DATABASE_URL=sqlite+aiosqlite:///./saa29_local.db`.
- Para arquivos, deixe `STORAGE_BACKEND=local`.

### Railway

- Se usar SQLite em volume, a base precisa ficar em um caminho persistente.
- Se usar R2, configure `STORAGE_BACKEND=r2` e as credenciais do bucket.
- Para PostgreSQL, use banco externo e instale `asyncpg` no ambiente.

## 8. Gerar Chave Segura

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 9. Convenções de Segurança

Para manter a integridade do sistema após a auditoria de 2026, todos os desenvolvedores devem seguir estas convenções:

### Frontend (JS)
- **Manipulação de DOM:** Nunca utilize `element.innerHTML = dado_da_api` diretamente. Use sempre a função utilitária `escapeHtml(dado_da_api)` para prevenir XSS.
- **Eventos:** Não utilize atributos `on*` (ex: `onclick`) no HTML. Use `addEventListener` em arquivos JS separados para conformidade com a CSP.

### Backend (Python/FastAPI)
- **Buscas Textuais:** Ao realizar buscas utilizando `LIKE` no SQLAlchemy, utilize a função `_escape_like(termo)` disponível em `app.modules.equipamentos.service` (ou similar) para prevenir injeção de caracteres curinga.
- **Rotas HTML:** Toda nova rota em `app/web/pages/router.py` **deve** incluir a dependência `Depends(get_current_user)` ou superior (RBAC) para garantir a arquitetura Zero Trust.
- **Exceções de Auth:** Sempre utilize `raise HTTPException` explicitamente em blocos de validação de token para garantir que o erro seja capturado corretamente pelo middleware e não retorne 500.

### Banco de Dados
- **Conexões:** O lifespan da aplicação em `main.py` gerencia o fechamento do pool via `dispose_engine()`. Não manipule o ciclo de vida da engine manualmente nos módulos.
- **Limpeza:** A tarefa de limpeza de tokens expirados é automática. Se criar novas tabelas de tokens ou sessões, registre-as na rotina `limpar_tokens_expirados`.

## 10. Observacao Pratica

O ponto de entrada da aplicacao e `app/bootstrap/main.py`, nao um `app/main.py` direto. Isso importa para comandos de deploy, testes e para qualquer wrapper de execucao local.
