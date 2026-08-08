# Backlog — Envio Web de Edições do Acervo de Publicações (M4.Web)

> Documento de planejamento e backlog técnico para a funcionalidade de envio e atualização do acervo de manuais pela interface Web no SAA29, conforme especificado em [docs/guides/sugestao_envio.md](../../guides/sugestao_envio.md).

---

## 1. Visão Geral e Motivação

Atualmente, o acervo de manuais (M4) do SAA29 só pode ser atualizado via script de linha de comando (`scripts/publicacoes/publicar.py`) e transferência via SSH (`rsync`). A interface Web em `/configuracoes` possui exclusivamente a capacidade de **ativar** ou **reverter** edições já preparadas no servidor.

Esta funcionalidade adiciona o fluxo de **envio autônomo pela interface Web**, permitindo que usuários com a função **`INSPETOR`** ou **`ADMINISTRADOR`** enviem arquivos `.zip` contendo o acervo completo (ou atualizado) de manuais diretamente pelo navegador, mantendo o processo de **ativação** restrito ao **`ADMINISTRADOR`**.

---

## 2. Decisões de Arquitetura

1. **Upload via Presigned Multipart no Cloudflare R2**:
   - Evita OOM (*Out of Memory*) e timeout HTTP de 30s no FastAPI/Gunicorn ao lidar com arquivos de 3 GB.
   - Divisão em partes de 100 MB com retry individual e leitor do header `ETag` (configurado via CORS no bucket R2).
   - Suporte a fallback de desenvolvimento local (`LocalStorageService`) gravando chunks em `var/publicacoes/staging/chunks/<job_id>/`.

2. **Isolamento de Processamento via Subprocesso**:
   - O inventário, extração de texto em PDF (pypdfium2), indexação FTS5 (SQLite `catalog.<rotulo>.db`) e geração de diffs rodam como um **subprocesso isolado** (`python -m scripts.publicacoes.publicar --de-upload <key>`).
   - O worker web não sofre picos de RAM/CPU e não compromete o event loop principal.

3. **Trava de Voo Único (Single-Flight Lock)**:
   - Índice único parcial em `publicacoes_upload_jobs` onde `status IN ('ENVIANDO', 'PROCESSANDO')`.
   - Impede requisições simultâneas de processamento ou concorrência na VPS.

4. **Separação de Papéis (RBAC)**:
   - `InspetorOuAdmin` (`INSPETOR` ou `ADMINISTRADOR`): pode iniciar upload, enviar partes, concluir envio e monitorar o progresso.
   - `AdminRequired` (`ADMINISTRADOR` apenas): permanece responsável pela ativação da edição (`POST /api/edicoes/{id}/ativar`).

---

## 3. Pré-requisitos Obrigatórios (Refatoração de Segurança & Estabilidade)

Antes de abrir o endpoint de upload web, os seguintes achados prioritários de [docs/backlog/modulo_publicacoes/dividas/ACHADOS.md](dividas/ACHADOS.md) devem ser corrigidos:

1. **[ALTO] `_resolver_pdf` (router.py)**: Aplicar checagem de contenção (`is_relative_to`) também no fallback de fixtures `tests/fixtures/fim`, restringindo-o ao ambiente de testes.
2. **[ALTO] `obter_ou_criar_edicao` (service.py)**: Distinguir a constraint de unicidade violada em `IntegrityError` (rótulo vs edição vigente) e alterar o default para `status=StatusEdicao.AGUARDANDO_ATIVACAO`.

---

## 4. Fases de Execução

### Fase 1: Pré-requisitos & Extensão do `StorageService`
- [x] Corrigir `_resolver_pdf` em `app/modules/publicacoes/router.py`.
- [x] Ajustar `obter_ou_criar_edicao` em `app/modules/publicacoes/service.py`.
- [x] Estender `StorageService` (`app/shared/core/storage.py`) com métodos de multipart (`iniciar_multipart`, `presign_parte`, `concluir_multipart`, `abortar_multipart`).
- [x] Implementar suporte local no `LocalStorageService` com staging em `var/publicacoes/staging/chunks/<job_id>/`.

### Fase 2: Modelo de Dados & Migração Alembic
- [x] Criar model `PublicacoesUploadJob` em `app/modules/publicacoes/models.py`.
- [x] Adicionar enum de status de upload (`ENVIANDO`, `PROCESSANDO`, `CONCLUIDO`, `FALHOU`, `CANCELADO`).
- [x] Adicionar índice único parcial `uq_publicacoes_upload_jobs_ativo_unico`.
- [x] Gerar e aplicar migração Alembic.

### Fase 3: Endpoints da API (Router)
- [x] `POST /publicacoes/api/edicoes/uploads` (iniciar upload).
- [x] `POST /publicacoes/api/edicoes/uploads/{id}/partes` (obter presigned URL por parte).
- [x] `POST /publicacoes/api/edicoes/uploads/{id}/concluir` (concluir multipart e disparar worker).
- [x] `POST /publicacoes/api/edicoes/uploads/{id}/cancelar` (abortar upload).
- [x] `GET /publicacoes/api/edicoes/uploads/{id}` e `GET /publicacoes/api/edicoes/uploads` (polling de progresso).

### Fase 4: Adaptação do Script `publicar.py` & Validador ZIP
- [x] Implementar pipeline de validação de ZIP em `scripts/publicacoes/publicar.py` (Zip-Slip, Zip Bomb, Allowlist de extensões).
- [x] Adicionar suporte ao parâmetro `--de-upload <file_key>` para download via streaming para staging.
- [x] Adicionar atualização de progresso (`progresso_pct`, `etapa`) no banco principal via `get_session_factory()`.
- [x] Garantir exclusão da chave temporária de upload no R2 (`publicacoes/uploads/<job_id>/edicao.zip`) ao finalizar.

### Fase 5: Interface Web (Front-end Vanilla JS)
- [x] Criar `configuracoes_publicacoes.js` (drag and drop, faturamento do arquivo em partes, envio paralelo, retry e polling).
- [x] Atualizar o Card de Publicações na página `/configuracoes` com a área de envio e barra de progresso.

### Fase 6: Testes & Documentação
- [x] Testes unitários para o validador de ZIP (Zip-Slip, Zip Bomb, allowlist).
- [x] Testes de integração dos endpoints de upload e máquina de estados do job.
- [x] Atualizar a documentação operacional e os apontamentos em `docs/guides/sugestao_envio.md`.

---

## 5. Rastreabilidade & Referências

- [sugestao_envio.md](../../guides/sugestao_envio.md) — Guia consolidado da proposta de envio web.
- [opcoes_upload_inspetor.md](../../guides/opcoes_upload_inspetor.md) — Comparativo original das opções de arquitetura.
- [envio_publicacoes_zip.md](../../guides/envio_publicacoes_zip.md) — Documentação histórica das restrições de upload HTTP.
- [ACHADOS.md](dividas/ACHADOS.md) — Relatório de dívidas e achados de revisão do módulo.
