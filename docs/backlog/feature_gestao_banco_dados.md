# Especificação de Funcionalidade: Painel de Gestão e Backup do Banco de Dados

> **Status:** Proposto / Backlog  
> **Módulo:** Configurações / Administração do Sistema  
> **Público-Alvo:** Perfil `ADMINISTRADOR`  

---

## 1. Contexto e Objetivo

Atualmente, os backups para o Cloudflare R2 e a manutenção/limpeza do banco de dados SQLite ocorrem via rotinas automáticas de *cron* ou execução manual por linha de comando (SSH na VPS).

Esta funcionalidade visa adicionar um painel visual na página de **Configurações** (`/configuracoes`), permitindo que administradores acompanhem a telemetria do banco de dados, executem backups manuais sob demanda e realizem ações de manutenção diretamente pela interface web com total segurança.

---

## 2. Requisitos Funcionais

### Fase 1 — Operações Seguras (Telemetria & Backup)

1. **Telemetria e Status em Tempo Real:**
   - Tamanho atual do arquivo do banco de dados SQLite em disco (ex: `14.2 MB`).
   - Data e hora do último backup realizado no Cloudflare R2.
   - Status da integração com o Cloudflare R2 (Conectado / Desconectado / Não Configurado).

2. **Backup Manual Sob Demanda:**
   - Botão `[ ☁️ Executar Backup no R2 Agora ]`.
   - Aciona o processo de backup atômico (checkpoint WAL + upload para o R2) sem interromper a operação dos usuários.

3. **Download de Cópia Local:**
   - Botão `[ 📥 Baixar Cópia Local (.db) ]`.
   - Permite que o administrador baixe uma cópia binária consistente do banco de dados para salvaguarda local na sua própria máquina.

---

### Fase 2 — Operações de Alto Risco (Zona de Perigo)

4. **Restaurar Banco do Cloudflare R2:**
   - Botão `[ 🔄 Restaurar Banco do R2 ]`.
   - Baixa a versão mais recente salva no R2 e substitui o banco local de forma atômica.
   - **Trava de Segurança:** Exige confirmação em modal, digitação do texto `RESTAURAR-BANCO` e validação da senha do administrador logado.

5. **Limpeza de Dados de Teste / Mock:**
   - Botão `[ 🧹 Purgar Dados de Teste ]`.
   - Executa a rotina de purga (remoção de inspeções e panes de teste, mantendo frota e catálogo de equipamentos intocados).
   - **Trava de Segurança:** Modal de confirmação exigindo confirmação explícita e senha de administrador.

---

## 3. Arquitetura Técnica Proposta

### Backend (Endpoints FastAPI)

- `GET /api/v1/configuracoes/banco/status`
  - Retorna tamanho do `.db`, timestamp do último backup no R2 e status de conectividade.
- `POST /api/v1/configuracoes/banco/backup`
  - Dispara o `r2_manager.py backup` de forma assíncrona.
- `GET /api/v1/configuracoes/banco/download`
  - Retorna o arquivo `.db` via `FileResponse` de forma segura.
- `POST /api/v1/configuracoes/banco/restaurar` *(Fase 2)*
  - Valida a senha do admin e substitui o banco com reinicialização limpa.
- `POST /api/v1/configuracoes/banco/limpar-dados` *(Fase 2)*
  - Executa o expurgo controlado de produção.

### Requisitos de Segurança (RBAC & CSRF)

- **Permissão Exclusiva:** Todas as rotas devem exigir a dependência `InspetorOuAdmin` / `ADMINISTRADOR`.
- **Proteção CSRF:** Validação obrigatória do token CSRF em todas as rotas POST.
- **Rate Limiting:** Teto de requisições rígido (ex: máximo 3 backups manuais por hora) para evitar consumo excessivo da API do R2.

---

## 4. Layout e Interface do Usuário (Mockup)

```text
+-----------------------------------------------------------------------+
| 💾 Gestão e Backup do Banco de Dados                                  |
+-----------------------------------------------------------------------+
| Tamanho do Banco Local: 12.4 MB (SQLite WAL)                          |
| Último Backup R2: 10/08/2026 11:44:50 (Status: ✅ Sincronizado)         |
| Bucket R2: saa29-storage                                              |
|                                                                       |
| [ ☁️ Executar Backup no R2 Agora ]  [ 📥 Baixar Cópia Local (.db) ]    |
|                                                                       |
| ⚠️ Zona de Perigo (Ações Críticas):                                    |
| [ 🔄 Restaurar Banco do R2 ]  [ 🧹 Limpar Dados de Teste/Mock ]       |
+-----------------------------------------------------------------------+
```

---

## 5. Critérios de Aceite

- [ ] Apenas usuários com a função `ADMINISTRADOR` conseguem visualizar e acionar os botões de gestão do banco.
- [ ] O backup sob demanda para o R2 é executado sem bloquear requisições de outros usuários.
- [ ] O download do arquivo `.db` entrega uma cópia íntegra e não corrompida.
- [ ] Ações na Zona de Perigo (Restore/Purga) exigem validação de senha do admin e texto de confirmação.
