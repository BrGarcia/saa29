# Plano de Implementação: Deploy Local (Docker + MacBook)

Este documento descreve o plano para executar o SAA29 localmente via Docker no MacBook,
compartilhando o banco de dados SQLite com a instância em produção (Railway) por meio do
Cloudflare R2 como storage intermediário.

---

## 1. Objetivo

Permitir que o operador principal (Administrador) utilize o SAA29 a partir da sua máquina
local (MacBook), reduzindo o consumo de créditos do Railway. O Railway continuará ativo
como fallback para acesso remoto ou para outros usuários.

Adicionalmente, criar o perfil de usuário **Inspetor** (somente leitura) para que
supervisores possam acompanhar o status das panes sem risco de alterar dados.

---

## 2. Arquitetura Atual vs. Proposta

### Arquitetura Atual
```
┌────────────┐         ┌──────────────────┐         ┌──────────────┐
│  Navegador │ ──────► │  Railway (prod)  │ ──────► │  SQLite .db  │
│  (Usuário) │         │  Docker + App    │         │  (efêmero)   │
└────────────┘         └──────────────────┘         └──────┬───────┘
                                                           │
                                                    Backup periódico
                                                           │
                                                   ┌──────▼───────┐
                                                   │ Cloudflare R2│
                                                   │ (storage)    │
                                                   └──────────────┘
```

### Arquitetura Proposta
```
┌────────────────────────────────────────────────────────────────────┐
│                    Cloudflare R2 (Storage Central)                 │
│                    database/saa29_local.db                         │
└────────┬──────────────────────────────────┬───────────────────────┘
         │ restore (startup)                │ restore (startup)
         │ backup  (on change)              │ backup  (on change)
         ▼                                  ▼
┌──────────────────┐              ┌──────────────────┐
│  MacBook (local) │              │  Railway (cloud) │
│  Docker Desktop  │              │  Docker + App    │
│  restart: always │              │  (sleep/standby) │
│  localhost:8000  │              │  saa29.up.ry.app │
│                  │              │                  │
│  OPERAÇÃO DIÁRIA │              │  FALLBACK/REMOTO │
│  (Administrador) │              │  (Inspetor, etc) │
└──────────────────┘              └──────────────────┘
```

---

## 3. Pré-requisitos

| Item | Detalhe |
| :--- | :--- |
| **macOS** | Qualquer versão recente (Sonoma/Sequoia) |
| **Docker Desktop** | Versão para Apple Silicon (M1/M2/M3) |
| **Git** | Para clonar o repositório do GitHub |
| **Cloudflare R2** | Já configurado e funcional no projeto |
| **Repositório GitHub** | `BrGarcia/saa29` (branch principal) |

---

## 4. Regra de Ouro: Uso Exclusivo do Banco

> ⚠️ **IMPORTANTE:** O SQLite não suporta escrita simultânea de múltiplas instâncias
> remotas. Apenas **uma instância de escrita** (MacBook ou Railway) deve estar ativa
> por vez. A outra instância deve operar em modo leitura (Inspetor) ou estar desligada.

### Protocolo de Uso

| Cenário | MacBook | Railway |
| :--- | :---: | :---: |
| Operação normal (em casa/escritório) | ✅ Ativo (leitura + escrita) | 🟡 Sleep ou Inspetor |
| Acesso remoto / viagem | ❌ Desligado | ✅ Ativo (leitura + escrita) |
| Inspetor consultando | ✅ Ativo (escrita) | ✅ Ativo (somente leitura) |

### Fluxo de Troca

1. **MacBook → Railway:** O MacBook faz backup para R2 ao desligar/parar o container. O Railway faz restore do R2 ao iniciar.
2. **Railway → MacBook:** O Railway faz backup para R2 ao receber um shutdown signal. O MacBook faz restore do R2 ao iniciar o container.

---

## 5. Plano de Implementação

### Fase 1: Perfil "Inspetor" (Backend)

**Objetivo:** Criar um novo perfil de usuário com permissões somente leitura.

#### Passo 1.1 — Atualizar modelo de dados
- **Arquivo:** `app/auth/models.py`
- **Ação:** Documentar `INSPETOR` como valor válido no campo `funcao`.
- **Valores válidos:** `ADMINISTRADOR | ENCARREGADO | MANTENEDOR | INSPETOR`

#### Passo 1.2 — Criar middleware/dependência de permissão
- **Arquivo:** `app/dependencies.py` (ou novo `app/core/permissions.py`)
- **Ação:** Criar uma dependência FastAPI `require_write_access()` que:
  - Verifica se o usuário autenticado tem `funcao != "INSPETOR"`.
  - Retorna `HTTP 403 Forbidden` se for Inspetor tentando fazer escrita.

#### Passo 1.3 — Proteger rotas de escrita
- **Arquivos:** `app/panes/router.py`, `app/aeronaves/router.py`, `app/equipamentos/router.py`, `app/auth/router.py`
- **Ação:** Adicionar `Depends(require_write_access)` em todas as rotas `POST`, `PUT`, `PATCH` e `DELETE`.
- As rotas `GET` permanecem acessíveis para todos os perfis.

#### Passo 1.4 — Ajustar frontend (templates)
- **Arquivos:** Templates HTML em `templates/`
- **Ação:** Ocultar botões de ação (Criar, Editar, Concluir, Excluir) quando o usuário logado for `INSPETOR`.
- Usar a variável de contexto `usuario.funcao` já disponível nos templates Jinja2.

#### Passo 1.5 — Script de criação de Inspetor
- **Arquivo:** `scripts/init_db.py`
- **Ação:** Adicionar opção para criar um usuário Inspetor padrão (opcional, via variável de ambiente).

```env
# .env (exemplo)
DEFAULT_INSPECTOR_USER=inspetor
DEFAULT_INSPECTOR_PASSWORD=SenhaSegura123
```

**Estimativa de esforço:** ~2 horas

---

### Fase 2: Docker Compose para Deploy Local

**Objetivo:** Preparar o `docker-compose.yml` e configurações para execução no MacBook.

#### Passo 2.1 — Criar arquivo de ambiente local
- **Arquivo:** `.env.local` (novo, não versionado)
- **Ação:** Copiar `.env.example` e configurar para uso local:

```env
# .env.local — MacBook
DATABASE_URL=sqlite+aiosqlite:////app/data/saa29.db
APP_ENV=production
APP_DEBUG=False
APP_SECRET_KEY=<mesma chave do Railway>

# R2 — mesmas credenciais do Railway
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=<mesmo>
R2_ACCESS_KEY_ID=<mesmo>
R2_SECRET_ACCESS_KEY=<mesmo>
R2_ENDPOINT=<mesmo>
R2_BUCKET_NAME=saa29-storage
```

#### Passo 2.2 — Validar `docker-compose.yml` existente
O arquivo atual já está adequado para uso local:

```yaml
# docker-compose.yml (atual — já funcional)
services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env           # trocar para .env.local no MacBook
    volumes:
      - uploads_data:/app/uploads
      - sqlite_data:/app/data
    environment:
      - DATABASE_URL=sqlite+aiosqlite:////app/data/saa29.db
    restart: always     # ← já garante auto-start

volumes:
  uploads_data:
  sqlite_data:
```

- **Ajuste necessário:** Remover o volume `.:/app` (bind mount do código-fonte) para produção local. Isso garante que o container use apenas a imagem buildada, sem interferência de arquivos locais.

#### Passo 2.3 — Configurar Docker Desktop para auto-start
- `Docker Desktop` > `Settings` > `General` > ✅ **Start Docker Desktop when you log in**
- O `restart: always` no compose garante que o container suba junto com o Docker.

**Estimativa de esforço:** ~30 minutos

---

### Fase 3: Sincronização Segura do Banco via R2

**Objetivo:** Garantir que o banco de dados esteja sempre atualizado entre as instâncias.

#### Passo 3.1 — Backup no shutdown (graceful)
- **Arquivo:** `scripts/start.sh` (ou novo `scripts/stop.sh`)
- **Ação:** Capturar o sinal `SIGTERM` (que o Docker envia ao parar o container) e
  executar `python scripts/r2_manager.py backup` antes de encerrar o processo.
- Isso já é parcialmente suportado pelo `r2_manager.py` existente.

#### Passo 3.2 — Restore no startup (já implementado)
O `scripts/start.sh` já possui a lógica de restore:
```bash
# Já existe em start.sh (linha 13-16)
if [ -n "$R2_BUCKET_NAME" ]; then
    echo "🔄 Restaurando banco de dados do Cloudflare R2..."
    python scripts/r2_manager.py restore
fi
```

#### Passo 3.3 — Backup event-driven (opcional, recomendado)
- **Ação:** Manter o mecanismo atual de backup por evento (ao detectar mudanças no `.db`)
  ou adicionar um backup periódico simples (ex: a cada 5 minutos via `cron` dentro do container).

**Estimativa de esforço:** ~1 hora

---

### Fase 4: Procedimento Operacional

**Objetivo:** Documentar o fluxo de trabalho diário para evitar conflitos de dados.

#### 4.1 — Início do dia (MacBook)
1. Ligar o MacBook → Docker Desktop inicia automaticamente.
2. O container SAA29 inicia automaticamente (`restart: always`).
3. O `start.sh` baixa o banco mais recente do R2.
4. Acessar `http://localhost:8000` no navegador.

#### 4.2 — Saída / Fim do dia
1. O container faz backup automático para o R2 (via signal handler ou cron).
2. Desligar o MacBook normalmente.

#### 4.3 — Acesso remoto (Railway)
1. O Railway deve estar configurado para fazer restore do R2 no startup.
2. Ao acessar o Railway, os dados estarão sincronizados com o último backup do MacBook.

#### 4.4 — Inspetor acessando simultaneamente
1. O Inspetor acessa o Railway (ou o MacBook, se na mesma rede).
2. Como ele só faz leituras (`SELECT`), não há risco de conflito com o SQLite.
3. Ele verá os dados em tempo real, sem delay.

---

## 6. Guia Rápido de Deploy no MacBook

```bash
# 1. Instalar Docker Desktop para Mac (se ainda não tiver)
# https://docs.docker.com/desktop/install/mac-install/

# 2. Clonar o repositório
git clone https://github.com/BrGarcia/saa29.git
cd saa29

# 3. Criar o arquivo de ambiente local
cp .env.example .env
# Editar .env com as credenciais reais (R2, SECRET_KEY, etc.)

# 4. Build e start
docker compose up -d --build

# 5. Verificar se está rodando
docker compose logs -f

# 6. Acessar no navegador
# http://localhost:8000
```

---

## 7. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
| :--- | :---: | :---: | :--- |
| Duas instâncias escrevendo ao mesmo tempo | Baixa | 🔴 Alto (corrupção) | Protocolo operacional + perfil Inspetor |
| Esquecer de fazer backup ao trocar de instância | Média | 🟡 Médio (perda de dados recentes) | Backup automático no shutdown do container |
| Docker Desktop não iniciar automaticamente | Baixa | 🟢 Baixo | Configurar auto-start nas preferências |
| Atualização do código fora de sincronia | Média | 🟡 Médio | Sempre fazer `git pull` + `docker compose up --build` |
| Sem internet = sem acesso ao R2 | Baixa | 🟡 Médio | O container rodará com o último banco local disponível |

---

## 8. Estimativa Total de Esforço

| Fase | Descrição | Tempo |
| :---: | :--- | :--- |
| 1 | Perfil Inspetor (backend + frontend) | ~2 horas |
| 2 | Docker Compose para MacBook | ~30 minutos |
| 3 | Sincronização R2 (backup no shutdown) | ~1 hora |
| 4 | Documentação operacional | ~30 minutos |
| — | **Total** | **~4 horas** |

---

## 9. Considerações Futuras

- **Migração para PostgreSQL centralizado:** Eliminaria completamente o problema de
  sincronização via arquivo. Tanto o MacBook quanto o Railway apontariam para o mesmo
  banco na nuvem (ex: Neon, Supabase, ou Cloudflare D1).
- **VPN / Tailscale:** Permitiria acessar o MacBook remotamente como se fosse local,
  eliminando a necessidade do Railway para a maioria dos cenários.
- **Perfil Inspetor expandido:** No futuro, o Inspetor poderia ter acesso a relatórios
  e dashboards exclusivos para supervisão de manutenção.

---

*Documento criado em 18 de abril de 2026 como plano de implementação para deploy local do SAA29.*
