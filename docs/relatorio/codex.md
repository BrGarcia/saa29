# Relatório Técnico Principal - Codex

Data da análise: 2026-05-08  
Escopo: análise estática do repositório, leitura dos documentos `docs/ia/README.md` e `docs/methodology/CSP.md`, inspeção de código, configuração, migrações, Docker e testes.  
Comandos executados:
- `venv/bin/python -m alembic heads`
- `venv/bin/python -m alembic current`
- `venv/bin/python -m pip list --format=freeze`
- `venv/bin/python -m pytest`
- `venv/bin/python -m pytest --ignore=tests/unit/shared/services/image`

Observação de segurança: segredos e tokens foram identificados no repositório, mas não são reproduzidos neste relatório.

## Diagnóstico Geral

O projeto é um monólito modular FastAPI/Jinja/SQLAlchemy async com intenção clara de separação por módulos de domínio (`app/modules/*`), infraestrutura (`app/bootstrap`), componentes compartilhados (`app/shared`) e frontend (`app/web`). Essa direção é adequada para o tamanho atual, mas a implementação ainda mistura responsabilidades em alguns routers e services, mantém documentos e arquivos legados com dados sensíveis, e possui inconsistências relevantes entre documentação, configuração, validação de upload e ambiente de testes.

O estado atual não deve ser considerado pronto para produção antes de resolver os itens críticos de segurança. O principal problema é vazamento de credenciais/tokens em arquivos versionados ou presentes no workspace, incluindo `.env.backup`, `cookies.txt` e documentos em `docs/legacy`. A segunda frente urgente é confiabilidade operacional: o ambiente virtual local não reflete `requirements.txt`, a suíte completa falha na coleta por ausência de `PIL`, e o fluxo de upload de imagem quebra em background quando a dependência não existe. Há também fragilidade no deploy: `scripts/start.sh` instala dependências em runtime, executa restore/backup automático de banco SQLite via R2, roda migrações e seed no boot, e depois inicia Gunicorn. Isso torna o startup lento, menos previsível e mais arriscado.

As camadas existem, mas ainda há acoplamento: `app/modules/auth/router.py`, `app/modules/panes/router.py`, `app/modules/equipamentos/router.py` e services grandes concentram orchestration, regras de negócio, tratamento de erro e detalhes de persistência. O frontend está parcialmente alinhado à CSP de zero inline script, mas ainda há muitos estilos inline, uso extenso de `innerHTML` e um template legado fora de `app/web/templates` com `onclick`/`onsubmit`, contrariando o padrão documentado.

## Limitações

- Não foi executada auditoria online de vulnerabilidades de dependências porque o ambiente está sem acesso de rede. É obrigatório rodar `pip-audit`/`safety` em CI com rede.
- Não foi validado o comportamento visual no navegador. A análise de frontend foi estática.
- Não foram alterados arquivos de aplicação; este relatório apenas diagnostica e prioriza.
- A suíte completa não pôde ser validada porque o `venv` atual não tem `PIL/Pillow`, apesar de `requirements.txt` declarar `Pillow==11.0.0`.

## Problemas Críticos

### C1. Segredos, tokens e credenciais expostos em arquivos versionados ou no workspace

- O que está errado: `.env.backup` está versionado e contém variáveis sensíveis como `APP_SECRET_KEY`, `DEFAULT_ADMIN_PASSWORD`, `R2_ACCESS_KEY_ID` e `R2_SECRET_ACCESS_KEY` (`.env.backup:14`, `.env.backup:16`, `.env.backup:31`, `.env.backup:37`, `.env.backup:38`). `cookies.txt` está versionado e contém cookies HttpOnly/JWT/refresh token (`cookies.txt:5`, `cookies.txt:6`, `cookies.txt:7`). Documentos legados também registram credenciais reais ou senhas históricas (`docs/legacy/IMPLEMENTATION_PLAN.md:36`, `docs/legacy/IMPLEMENTATION_PLAN.md:38`, `docs/legacy/RELATORIO_COMPLETO.MD:41`, `docs/legacy/relatorio_completo_implementacao.md:126`).
- Risco: comprometimento de backups R2, forja de JWT, reutilização de refresh token, acesso administrativo e exposição de dados operacionais.
- Impacto: crítico. Basta acesso ao repositório ou a artefatos gerados para comprometer o ambiente.
- Correção recomendada: revogar imediatamente tokens/cookies e rotacionar todas as credenciais citadas; remover `.env.backup`, `cookies.txt` e segredos em `docs/legacy` do repositório; limpar histórico Git com ferramenta apropriada; adicionar regras de secret scanning no CI; bloquear commits com `detect-secrets`, `gitleaks` ou equivalente.
- Ordem sugerida: 1.

### C2. Cadeia de upload de imagem inconsistente e quebrada em execução real

- O que está errado: `validate_file_upload` permite apenas jpg/jpeg/png/pdf (`app/shared/core/file_validators.py:9`), `panes.service` declara heic/heif também (`app/modules/panes/service.py:46`, `app/modules/panes/service.py:49`), e `LocalStorageService`/`R2StorageService` permitem `.doc`/`.docx`, mas não `.webp` (`app/shared/core/storage.py:51`, `app/shared/core/storage.py:107`). Ao processar imagem, o serviço gera `.webp` (`app/modules/panes/service.py:565`) e tenta armazenar por uma camada que rejeita `.webp`. Além disso, o ambiente testado não tem `PIL`, então a importação de `app/shared/services/image/pipeline.py` quebra no background (`app/modules/panes/service.py:553`).
- Risco: uploads válidos falham, anexos ficam em estado `processando`/`ERRO`, perda de evidência operacional e exceções não controladas durante resposta.
- Impacto: crítico para confiabilidade de panes e anexos.
- Correção recomendada: definir uma única matriz de extensões/MIME suportadas; incluir `image/webp` se o pipeline converte para WebP; remover `.doc/.docx` se não forem realmente aceitos; mover validação para um único módulo; garantir dependências de imagem instaladas no ambiente; tratar erro de background sem quebrar a request.
- Ordem sugerida: 2.

### C3. Ambiente de dependências inconsistente com `requirements.txt`

- O que está errado: `requirements.txt` declara `Pillow==11.0.0` e `pillow-heif==0.21.0`, mas `venv/bin/python -m pytest` falha na coleta por `ModuleNotFoundError: No module named 'PIL'`. O mesmo arquivo contém dependências duplicadas ou sem pinagem (`aiosqlite` duplicado, `python-dotenv` duplicado, `boto3` sem versão, `slowapi` sem versão).
- Risco: CI e produção podem ter comportamentos diferentes; deploy pode passar sem dependências essenciais; falhas só aparecem em runtime.
- Impacto: crítico para confiabilidade de release.
- Correção recomendada: recriar lock reprodutível (`requirements.txt` totalmente pinado, `pip-tools`, Poetry ou uv); instalar do zero em CI; adicionar teste de import das dependências críticas; remover duplicidades e dependências não usadas.
- Ordem sugerida: 3.

## Problemas Altos

### A1. Startup de produção instala dependências e executa operações destrutivas/sensíveis

- O que está errado: `scripts/start.sh` executa `pip install --no-cache-dir -r requirements.txt` em runtime (`scripts/start.sh:14`), restaura banco do R2 antes das migrações (`scripts/start.sh:19`), roda Alembic (`scripts/start.sh:25`), executa bootstrap/seed (`scripts/start.sh:29`) e faz backup R2 no boot (`scripts/start.sh:41`).
- Risco: startup lento, falhas por rede, drift de dependências, sobrescrita de banco local, backup de estado parcialmente migrado e dificuldade de rollback.
- Impacto: alto em produção e homologação.
- Correção recomendada: mover instalação para build da imagem; separar comandos de migração/seed/backup do entrypoint principal; exigir confirmação/flag explícita para restore; usar job de migração controlado; criar healthcheck.
- Ordem sugerida: 4.

### A2. Docker inseguro e pouco previsível para produção

- O que está errado: `Dockerfile` roda como root por padrão (`Dockerfile:1` a `Dockerfile:22`), copia o repositório inteiro (`Dockerfile:15`), não tem healthcheck, não fixa digest da imagem base e depende do start script para instalar dependências. `docker-compose.yml` monta o diretório inteiro da aplicação sobre `/app` (`docker-compose.yml:8`), o que invalida parte da imagem e mistura dev/prod.
- Risco: aumento da superfície de ataque, comportamento divergente entre imagem e container em execução, permissões excessivas e deploy não reprodutível.
- Impacto: alto.
- Correção recomendada: criar usuário não-root; instalar dependências no build; copiar apenas artefatos necessários; usar `.dockerignore` estrito; separar compose de desenvolvimento e produção; adicionar `HEALTHCHECK`; limitar capabilities e filesystem quando possível.
- Ordem sugerida: 5.

### A3. Política CSP documentada como zero inline, mas implementação exige `style-src 'unsafe-inline'`

- O que está errado: a documentação afirma que a arquitetura alcançou conformidade CSP e zero inline scripts (`docs/methodology/CSP.md`), mas o middleware permite `style-src 'unsafe-inline'` (`app/shared/middleware/security.py:35`) e os templates usam muitos `style="..."`, inclusive `base.html:23`, `base.html:31`, `app/web/templates/configuracoes.html` em larga escala e `app/web/templates/inventario.html`. Há ainda template legado com `<style>`, `onclick` e `onsubmit` (`templates/panes/lista.html:6`, `templates/panes/lista.html:30`, `templates/panes/lista.html:46`, `templates/panes/lista.html:95`).
- Risco: falsa sensação de hardening. Um relaxamento de estilo inline reduz a força da CSP e o template legado pode ser reativado por engano.
- Impacto: alto para segurança frontend e manutenção.
- Correção recomendada: mover estilos inline para CSS; excluir ou arquivar fora do pacote os templates legados; adicionar teste estático para bloquear `onclick`, `onsubmit`, `<script>` executável inline e `style=` em templates ativos; revisar `style-src`.
- Ordem sugerida: 6.

### A4. Validação de paths de anexos não impõe contenção no diretório de upload

- O que está errado: `LocalStorageService.get_url` retorna `Path(file_path).resolve()` sem verificar se o arquivo está dentro de `upload_dir` (`app/shared/core/storage.py:64`). `delete` também opera sobre qualquer path recebido (`app/shared/core/storage.py:68`). O router entrega `FileResponse` com esse path (`app/modules/panes/router.py:299`, `app/modules/panes/router.py:306`).
- Risco: se `caminho_arquivo` for corrompido no banco ou por bug, o sistema pode servir ou deletar arquivo local fora do diretório esperado.
- Impacto: alto por defesa em profundidade.
- Correção recomendada: armazenar paths relativos ou chaves opacas; resolver sempre contra `upload_dir`; rejeitar qualquer path cujo `resolve()` não esteja sob `upload_dir`; nunca aceitar path absoluto vindo do banco.
- Ordem sugerida: 7.

### A5. Banco SQLite e backup R2 como estratégia de persistência têm teto baixo de escalabilidade

- O que está errado: `database_url` padrão é SQLite (`app/bootstrap/config/__init__.py:48`), o Docker força SQLite em volume (`docker-compose.yml:12`), Gunicorn usa 2 workers por padrão (`gunicorn_conf.py:7`) e há backup/restore do arquivo `.db` para R2 (`scripts/maintenance/r2_manager.py:55`, `scripts/maintenance/r2_manager.py:76`).
- Risco: contenção de escrita, locks, inconsistência de backup durante escrita, restauração indevida e dificuldade de escalar horizontalmente.
- Impacto: alto quando houver múltiplos usuários, anexos e operações simultâneas.
- Correção recomendada: migrar produção para PostgreSQL com `asyncpg`; usar backups nativos/transacionais; manter SQLite apenas para desenvolvimento/monousuário; documentar limite explícito se SQLite permanecer.
- Ordem sugerida: 8.

### A6. Refresh token sem vínculo relacional e sem metadados mínimos de sessão

- O que está errado: `TokenRefresh.usuario_id` não tem `ForeignKey` no model (`app/modules/auth/models.py:197`) e a migração cria tabela sem FK para `usuarios`. Não há metadados como user agent/IP, família de token ou rotação encadeada.
- Risco: tokens órfãos, dificuldade de auditoria e revogação granular.
- Impacto: alto para segurança de sessão.
- Correção recomendada: adicionar FK para `usuarios.id` com política clara de delete; adicionar `family_id`, `created_ip`, `user_agent`, `rotated_from_jti`; revisar fluxo de revogação em família.
- Ordem sugerida: 9.

### A7. Permissões e regras de papel estão espalhadas

- O que está errado: há atalhos em `dependencies.py`, chamadas manuais de `ensure_role` em routers e lógica de visibilidade no frontend (`app/bootstrap/dependencies.py:122`, `app/modules/panes/router.py:128`, `app/modules/panes/router.py:164`, `app/web/static/js/auth_check.js:69`). Isso facilita divergência entre UI e API.
- Risco: endpoints com regra incorreta ou UI mostrando comandos que a API rejeita; revisões de segurança ficam manuais.
- Impacto: alto.
- Correção recomendada: consolidar uma matriz RBAC executável por recurso/ação; testar endpoint por papel; manter frontend apenas como conveniência visual, nunca como fonte de autorização.
- Ordem sugerida: 10.

## Problemas Médios

### M1. Services grandes e responsabilidades misturadas

- O que está errado: `app/modules/panes/service.py` tem 723 linhas, `app/modules/inspecoes/service.py` 621, `app/modules/equipamentos/service.py` 515 e `app/modules/vencimentos/service.py` 433. Eles misturam validação, consulta, regra de negócio, serialização indireta, storage e side effects.
- Risco: regressões em alterações pequenas, baixa testabilidade granular e revisão difícil.
- Impacto: médio/alto.
- Correção recomendada: dividir por casos de uso (`commands`, `queries`, `attachments`, `workflow`), criar repositórios ou funções query dedicadas apenas onde reduzirem duplicação, e manter transação no boundary do request.
- Ordem sugerida: fase 2.

### M2. Routers ainda acessam banco diretamente

- O que está errado: `app/modules/equipamentos/router.py` consulta `ModeloEquipamento` diretamente (`app/modules/equipamentos/router.py:48`, `app/modules/equipamentos/router.py:50`) e `SlotInventario` diretamente (`app/modules/equipamentos/router.py:102`, `app/modules/equipamentos/router.py:104`), contrariando a documentação que diz que router não acessa o banco.
- Risco: regra de negócio duplicada ou bypassada.
- Impacto: médio.
- Correção recomendada: mover consultas para service/query functions e deixar routers como validação HTTP, auth e mapeamento de erro.
- Ordem sugerida: fase 2.

### M3. Migrações com revisões vazias e diffs arriscados

- O que está errado: há migrações vazias (`migrations/versions/20260429_1740_bb4d91c20293_add_inspecoes_module.py:26`, `migrations/versions/20260429_2108_4cdf397899f3_inspecoes_tables.py:26`). Algumas migrações adicionam colunas `nullable=False` sem defaults de dados claros, por exemplo `periodicidade_meses` em `equipamento_controles` (`migrations/versions/20260424_2056_802c031ae579_add_periodicidade_meses_to_equipamento_.py:28`). Também há downgrade que recria colunas obrigatórias sem valores (`migrations/versions/20260430_1259_728522300c7e_desacoplamento_tarefas.py:61`).
- Risco: upgrade/downgrade falhar em bancos reais com dados; histórico confuso.
- Impacto: médio/alto.
- Correção recomendada: manter migrações vazias apenas com justificativa explícita; testar upgrade de banco real anonimizado; adicionar check de `alembic upgrade head` em banco limpo e em snapshot; evitar downgrades irreais ou marcá-los como não suportados.
- Ordem sugerida: fase 1/2.

### M4. Testes usam bypass global de CSRF por header em quase toda a suíte

- O que está errado: o client de teste injeta `X-Skip-CSRF: true` por padrão (`tests/conftest.py:93`, `tests/conftest.py:96`). O middleware só aceita isso em `APP_ENV=testing`, o que reduz risco em produção, mas cria baixa cobertura de CSRF nos testes de fluxo real.
- Risco: endpoints novos podem depender do bypass e não serem testados com token real.
- Impacto: médio.
- Correção recomendada: manter bypass apenas em fixtures específicas; criar fixture `client_com_csrf_real`; exigir testes reais para toda nova mutação crítica.
- Ordem sugerida: fase 1.

### M5. Frontend usa muito `innerHTML`

- O que está errado: há uso extenso de `innerHTML` em `app/web/static/js/configuracoes.js`, `inventario.js`, `app.js` e outros. Há função `escapeHtml` (`app/web/static/js/app.js:128`), mas a segurança depende de disciplina manual em cada interpolação.
- Risco: XSS persistente se algum campo novo entrar sem escape.
- Impacto: médio/alto.
- Correção recomendada: criar helpers DOM seguros (`createElement`, `textContent`, render de tabela com API declarativa); adicionar lint/test estático para detectar interpolação não escapada.
- Ordem sugerida: fase 2.

### M6. Documentação de estado está otimista e divergente de fatos do código

- O que está errado: `docs/ia/CTX.md` declara testes passando e conflitos de rota resolvidos, mas a suíte completa falha por ausência de `PIL`; `docs/methodology/CSP.md` declara conformidade CSP, mas há inline styles e template legado com eventos inline.
- Risco: novos mantenedores e IAs tomam decisões com base em premissas falsas.
- Impacto: médio.
- Correção recomendada: atualizar `docs/ia/*` após correções; criar checklist de docs sincronizadas; tratar `docs/ia` como índice, não como verdade se divergir do código.
- Ordem sugerida: fase 1.

### M7. Scripts operacionais duplicados e inconsistentes

- O que está errado: `scripts/maintenance/r2_manager.py` usa `R2_ENDPOINT` (`scripts/maintenance/r2_manager.py:18`), enquanto `scripts/backup_r2.py` usa `R2_ENDPOINT_URL` (`scripts/backup_r2.py:11`). Ambos fazem backup/restore R2 com chaves e nomes de objeto diferentes (`scripts/maintenance/r2_manager.py:55`, `scripts/backup_r2.py:24`).
- Risco: operador executa script errado e restaura/envia backup para key incorreta.
- Impacto: médio.
- Correção recomendada: manter um único script de backup com contrato documentado; remover/depreciar duplicado; adicionar dry-run e logs estruturados sem segredos.
- Ordem sugerida: fase 1/2.

### M8. Dados runtime e arquivos legados poluem o repositório

- O que está errado: há `templates/panes/lista.html` fora da árvore ativa, `scratch/*` versionado, `fim.json` e `cookies.txt` versionados. Existem diretórios runtime locais (`uploads`, `LOG`) no workspace, ainda que ignorados.
- Risco: confusão de fonte de verdade, reintrodução de código inseguro e vazamento acidental.
- Impacto: médio.
- Correção recomendada: remover do versionamento o que é runtime; mover scratch para `tools/` ou apagar; criar `docs/legacy/README.md` com política de arquivo histórico; excluir templates legados inseguros.
- Ordem sugerida: fase 2.

### M9. Logging e prints não estão padronizados

- O que está errado: scripts e services usam `print` para eventos operacionais, inclusive criação/correção de admin (`app/modules/auth/service.py:244`, `app/modules/auth/service.py:264`, `scripts/db/init_db.py:58`). Logs de erro de upload incluem nome original de arquivo (`app/modules/panes/service.py:577`, `app/modules/panes/service.py:591`).
- Risco: logs difíceis de correlacionar e possível exposição de nomes de arquivos sensíveis.
- Impacto: médio.
- Correção recomendada: usar logging estruturado com níveis; mascarar dados sensíveis; adicionar request ID/correlation ID.
- Ordem sugerida: fase 2.

## Problemas Baixos

### B1. Comentários e docstrings prometem mais do que o código garante

- O que está errado: vários arquivos têm comentários de auditoria e status de segurança como se fossem garantias concluídas, mas alguns controles são parciais.
- Risco: revisão menos crítica.
- Impacto: baixo/médio.
- Correção recomendada: trocar comentários triunfalistas por contratos verificáveis e testes.
- Ordem sugerida: fase 3.

### B2. Nomenclatura e idioma misturam português, inglês técnico e nomes antigos

- O que está errado: `app/bootstrap/config/__init__.py` representa settings, scripts têm nomes históricos e há pastas antigas (`app/aeronaves`, `app/auth`) contendo apenas cache.
- Risco: onboarding mais lento.
- Impacto: baixo.
- Correção recomendada: limpar caches e legados, padronizar nomes de scripts e documentar convenções.
- Ordem sugerida: fase 3.

### B3. Ausência de ferramentas formais de qualidade no repositório

- O que está errado: não há configuração visível de Ruff, mypy/pyright, coverage, pip-audit ou pre-commit.
- Risco: problemas de estilo, tipo e segurança entram sem barreira automatizada.
- Impacto: baixo/médio.
- Correção recomendada: adicionar `pyproject.toml` com Ruff, mypy/pyright gradual, coverage mínimo e pre-commit.
- Ordem sugerida: fase 3.

## Correções Urgentes vs. Melhorias Evolutivas

Urgente:
- Rotacionar e remover segredos/tokens versionados.
- Corrigir ambiente de dependências e falha de `PIL`.
- Corrigir upload de imagem e matriz única de MIME/extensões.
- Remover instalação de dependências no startup.
- Proteger paths de anexos contra acesso fora de `upload_dir`.
- Atualizar documentação de segurança que hoje está divergente.

Evolutivo:
- Refatorar services grandes em casos de uso.
- Consolidar RBAC em política executável.
- Reduzir `innerHTML` e estilos inline.
- Migrar produção para PostgreSQL.
- Padronizar logging, scripts e estrutura de pastas.
- Adicionar ferramentas de qualidade e auditoria em CI.

## Plano de Ação em Fases

### Fase 1: Estabilização e Segurança

1. Revogar/rotacionar R2, admin password, JWT secret e tokens/cookies.
2. Remover `.env.backup`, `cookies.txt` e segredos em `docs/legacy` do versionamento e do histórico.
3. Recriar o ambiente a partir de dependências pinadas; fazer a suíte completa passar.
4. Corrigir upload: matriz única de tipos, suporte real a WebP ou desativação da conversão, erro de background isolado.
5. Fortalecer `LocalStorageService` com path containment.
6. Separar startup: build instala dependências; deploy executa app; migração/restore/backup viram jobs explícitos.
7. Atualizar `docs/ia/*` e `docs/methodology/CSP.md` para refletir o estado real.

### Fase 2: Refatoração Estrutural

1. Quebrar `panes.service`, `inspecoes.service`, `equipamentos.service` e `vencimentos.service` em casos de uso.
2. Remover acesso direto ao banco dos routers.
3. Consolidar RBAC em uma política testável por ação.
4. Unificar scripts R2 e remover duplicados.
5. Revisar migrações com teste contra snapshot do banco ativo antes de qualquer mudança de schema.
6. Mover estilos inline para CSS e arquivar templates legados fora do caminho de execução.

### Fase 3: Otimização e Acabamento

1. Migrar produção para PostgreSQL ou documentar formalmente limite de SQLite.
2. Adicionar Ruff, type-checking gradual, coverage e secret scanning no CI.
3. Reduzir `innerHTML` com helpers seguros de renderização.
4. Adicionar logs estruturados, request ID e política de mascaramento.
5. Melhorar Docker com usuário não-root, healthcheck, compose separado e imagem reprodutível.

## Recomendações por Área

Arquitetura:
- Manter monólito modular, mas reforçar boundaries: routers sem queries, services menores e side effects isolados.
- Evitar criar abstrações genéricas demais agora; primeiro separar casos de uso concretos.

Qualidade de código:
- Priorizar upload, auth/RBAC e inventário, pois concentram risco operacional.
- Transformar helpers críticos em APIs únicas: validação de arquivo, política RBAC, storage path handling.

Segurança:
- Tratar secret scanning como bloqueio obrigatório.
- Revisar cookies: usar `Secure` em produção já existe, mas considerar `SameSite=Strict` para refresh se o fluxo permitir.
- Remover documentos com credenciais reais, mesmo que em `legacy`.

Banco e migrações:
- Não resetar banco ativo. Antes de qualquer schema change, seguir a regra de backup dos docs.
- Adicionar teste de migração com banco real anonimizado.
- Adicionar FKs ausentes como `token_refresh.usuario_id`.

Testes e confiabilidade:
- Corrigir o ambiente para `venv/bin/python -m pytest` passar sem ignores.
- Reduzir skips históricos que dizem "Auth ainda não implementada".
- Adicionar testes de upload com WebP, ausência de PIL, erro de storage e path containment.

Docker/deploy:
- Build deve ser determinístico; runtime não deve instalar dependências.
- Restore de banco não deve ocorrer automaticamente no start padrão.
- Adicionar health endpoint e healthcheck no Docker.

Dependências:
- Pinagem completa e lockfile.
- Rodar auditoria de vulnerabilidades no CI.
- Revisar necessidade de `python-jose`; avaliar alternativas mantidas ativamente se auditoria apontar risco.

Performance e escalabilidade:
- SQLite com WAL é aceitável para uso local/monousuário, não como alvo de escala.
- Consultas principais já usam `selectinload` em vários pontos, mas services grandes devem ganhar testes de contagem de queries nos fluxos críticos.
- Backup de arquivo SQLite deve ser transacional ou substituído por PostgreSQL.

UX técnica e documentação:
- Atualizar docs que declaram estados "100%" quando a suíte não passa.
- Criar um `README` operacional curto com comandos reais: setup, teste, migração, seed, backup e restore.

## Resultado dos Testes

- `venv/bin/python -m alembic heads`: uma head (`48d0005f8339`).
- `venv/bin/python -m alembic current`: banco local em `48d0005f8339`.
- `venv/bin/python -m pytest`: falhou na coleta de 5 arquivos de testes de imagem por ausência de `PIL`.
- `venv/bin/python -m pytest --ignore=tests/unit/shared/services/image`: 131 passaram, 2 falharam. As falhas ocorreram em upload/download de anexos porque o background importou o pipeline de imagem e não encontrou `PIL`.

## Ações Imediatas - Top 10

1. Rotacionar R2, `APP_SECRET_KEY`, senha admin e invalidar tokens/cookies expostos.
2. Remover `.env.backup`, `cookies.txt` e segredos em `docs/legacy` do repositório e histórico Git.
3. Recriar dependências com lockfile e garantir `Pillow`/pipeline de imagem instalados.
4. Corrigir validação/storage de upload para uma matriz única de MIME/extensão, incluindo ou removendo WebP de forma explícita.
5. Proteger `LocalStorageService.get_url/delete` contra paths fora de `upload_dir`.
6. Remover `pip install` e restore/backup automático do caminho padrão de startup.
7. Ajustar Docker para usuário não-root, imagem reprodutível e healthcheck.
8. Atualizar `docs/ia/*` e `docs/methodology/CSP.md` para refletirem a realidade.
9. Adicionar secret scanning e auditoria de dependências no CI.
10. Planejar migração de produção para PostgreSQL ou formalizar limite operacional do SQLite.
