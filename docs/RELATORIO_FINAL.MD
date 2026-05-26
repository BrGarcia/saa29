# Relatório de Auditoria Técnica Sênior — Sistema SAA29

Este documento apresenta a análise de auditoria técnica geral, minuciosa e estruturada do sistema **SAA29 (Sistema de Gestão de Panes – Eletrônica A-29)**. A análise foi realizada com foco em arquitetura, qualidade de código, segurança, persistência, regras de negócio e viabilidade para evolução futura como Web App/PWA.

---

## 1. Resumo Executivo

### Visão Geral do Estado do Sistema
O SAA29 é um sistema backend baseado em FastAPI com uma arquitetura modular orientada a domínios (DDD modular). Apresenta uma separação clara de responsabilidades entre rotas, regras de negócio (camada de serviço), repositórios (acesso ao banco via ORM SQLAlchemy assíncrono), schemas (Pydantic v2) e interface web com templates Jinja2 e Vanilla JS. A saúde básica do projeto é excelente, evidenciada por uma suíte de testes automatizados com **174 testes unitários e de integração passing (100% de sucesso)**.

### Principais Riscos Detectados
1. **Riscos de Concorrência e Persistência no SQLite:** O SQLite no modo padrão não lida bem com múltiplos acessos de escrita simultâneos. Embora o projeto utilize o modo WAL (`journal_mode=wal`), a escala e concorrência no ambiente produtivo demandam cautela, especialmente em movimentações de inventário e logs de auditoria.
2. **Dependência Crítica de Infraestrutura de Nuvem (Cloudflare R2):** A rotina de backup/sincronização na inicialização é um ponto de falha crítico. Se o R2 estiver indisponível, o sistema impede a inicialização para evitar sobrescrever dados locais. Isso introduz um forte acoplamento operacional a serviços externos.
3. **Mecanismo de Sessões por Cookies no Frontend:** A autenticação e o CSRF dependem da leitura correta de cookies HttpOnly no navegador. Inconsistências na propagação ou na validade do par de tokens (Access/Refresh) podem travar a interface do usuário.

### Nível de Maturidade Técnica
O sistema apresenta nível de maturidade técnica **alto** para um monolito modular baseado em Python. O uso de tipagem forte com Pydantic, isolamento de exceções, auditoria com persistência de trigramas nas tabelas críticas (inspeções e inventário) e conformidade estrita com políticas de CSP (sem inline scripts no HTML) demonstram excelente aderência a boas práticas.

### Conclusão Objetiva
O sistema está **estável, seguro e operacionalmente apto**. A arquitetura modular implementada facilita manutenções e o desacoplamento de novas features. Recomenda-se a migração definitiva para PostgreSQL em ambiente de produção real para mitigar os limites de concorrência do SQLite.

---

## 2. Escopo da Análise

### O que foi analisado
* **Módulos de Domínio:** `auth` (usuários, perfis e autenticação), `aeronaves` (gestão de células), `efetivo` (disponibilidade de pessoal), `equipamentos` (PNs, slots e SNs), `vencimentos` (inteligência temporal e prorrogações), `panes` (discrepâncias aviônicas), `inspecoes` (revisões programadas), `calendario` (planejamento) e `dashboard` (métricas).
* **Camada de Infraestrutura:** Ciclo de vida da aplicação (`bootstrap/events.py`), persistência e sessão do banco de dados, migrações do Alembic, middlewares globais (CSRF, headers de segurança, CORS) e serviço de storage (local e Cloudflare R2).
* **Segurança e Defesas:** Políticas de CSP hardened, sanitização de uploads, validações de MIME types reais com `python-magic`, hashing de senhas com bcrypt (contornando o limite de 72 bytes via SHA-256), proteção de token replay (refresh token rotation) e rate limiting.
* **Cobertura de Testes:** Suíte de testes em `tests/` com validações de arquitetura, segurança (CSRF/Refresh) e performance (auditoria de queries N+1).

### O que não pôde ser analisado
* **Infraestrutura Real do Cloudflare R2 em Produção:** As validações foram restritas à lógica de código do `R2StorageService` e mockadas na suíte de testes. Não foram validadas latências, limites reais de requisições por segundo e permissões finas no painel do Cloudflare.
* **Desempenho com Bancos de Dados PostgreSQL:** Embora o ORM e as migrações suportem drivers PostgreSQL (`asyncpg`), a auditoria local utilizou SQLite assíncrono (`aiosqlite`). Comportamentos de concorrência real sob alta concorrência no PostgreSQL não puderam ser verificados em runtime real.

### Premissas Adotadas
* O sistema opera em ambientes críticos de manutenção de defesa (aeronaves militares A-29 Super Tucano), exigindo estrita rastreabilidade (auditoria persistente por trigramas).
* A integridade referencial física e a segurança de acesso baseada em perfis (RBAC) possuem peso crítico absoluto. Qualquer bypass de permissão ou falha de consistência em status de aeronave constitui risco severo à segurança de voo.

---

## 3. Achados Críticos

Os achados críticos identificados foram mitigados em revisões recentes, mas representam pontos cruciais que devem ser continuamente vigiados para evitar regressões:

### 3.1. NameError em Runtime devido a código duplicado no Calendário
* **Severidade:** Crítica
* **Categoria:** Bug / Dívida Técnica
* **Descrição:** A camada de serviço do calendário continha uma cópia residual de funções antigas na metade inferior do arquivo. Estas funções referenciavam variáveis globais removidas (`PRIVILEGED_ROLES`), gerando `NameError` ou revertendo silenciosamente as correções de segurança (remoção de soft-delete, vazamento de privacidade) caso o Python resolvesse a definição inferior.
* **Evidência:** `app/modules/calendario/service.py:330-577` (Versão anterior).
* **Impacto:** Queda completa do microsserviço de calendário em runtime ou regressão silenciosa de vulnerabilidades críticas.
* **Recomendação:** Expurgar completamente trechos residuais duplicados, mantendo apenas as funções consolidadas e tipadas no início do arquivo. *(Resolvido)*

### 3.2. Bypass de Proteção CSRF fora de ambiente de produção
* **Severidade:** Alta
* **Categoria:** Vulnerabilidade
* **Descrição:** O middleware de segurança aceitava a flag `X-Skip-CSRF: true` para desativar a validação CSRF em qualquer ambiente cujo `APP_ENV` não fosse `"production"` (ex: staging, dev, homolog). O header é trivialmente simulável por requisições entre origens distintas.
* **Evidência:** `app/shared/middleware/csrf.py` (Lógica de `skip_csrf`).
* **Impacto:** Ataques de CSRF bem-sucedidos em servidores de teste/homologação contendo cópias de dados sensíveis ou com usuários reais conectados.
* **Recomendação:** Limitar a brecha de bypass exclusivamente ao ambiente `"testing"` acionado pela suíte automatizada de testes, validando de preferência via injeção interna na app e não por cabeçalho público. *(Resolvido)*

### 3.3. Reuso e vazamento de tokens de sessão após Logout
* **Severidade:** Alta
* **Categoria:** Vulnerabilidade
* **Descrição:** O endpoint `/auth/logout` limpava o cookie do Access Token, mas mantinha o refresh token ativo no banco e o cookie do cliente persistido. Um atacante em posse do cookie de refresh conseguia gerar novas sessões válidas.
* **Evidência:** `app/modules/auth/router.py` (Endpoint `POST /auth/logout`).
* **Impacto:** Sessões fantasmas ativas indefinidamente, quebrando o controle de autenticação do sistema aeronáutico.
* **Recomendação:** Garantir que o logout realize a invalidação física do refresh token (`revogado_em = agora`) e a remoção explícita de ambos os cookies na resposta HTTP. *(Resolvido)*

---

## 4. Vulnerabilidades de Segurança

### 4.1. Falha de Detecção no Reuso de Refresh Token (Token Replay Attack)
* **Severidade:** Alta
* **Tipo:** Vulnerabilidade
* **Risco de Exploração:** Médio
* **Superfície de Ataque:** Rota `/auth/refresh`
* **Descrição:** O fluxo anterior apenas verificava se o token enviado estava ativo. Em caso de reuso de um token já revogado (indício de roubo e replay), o sistema retornava 401 mas não revogava a família inteira de tokens do usuário.
* **Mitigação Recomendada:** Implementar a recomendação da RFC 6849 (BCP §10.4). Ao detectar tentativa de reuso de um token já revogado, realizar um expurgo em cascata marcando todas as sessões ativas do respectivo `usuario_id` como revogadas no banco, forçando re-autenticação imediata. *(Mitigado na versão atual)*

### 4.2. Exposição Indevida de Dados de Privacidade em Eventos Particulares
* **Severidade:** Média
* **Tipo:** Vulnerabilidade
* **Risco de Exploração:** Baixo
* **Superfície de Ataque:** Rota `/api/v1/calendario/eventos`
* **Descrição:** Eventos de natureza particular (privados) tinham o título alterado para `"Particular"` e notas omitidas, mas continuavam exibindo `owner_trigram` e a cor original do tipo (`backgroundColor`). Em cenários restritos (ex: consultas médicas), isso permitia descobrir a ausência e o motivo do afastamento de outros militares.
* **Mitigação Recomendada:** Censurar completamente o trigrama do dono (`owner_trigram=None`) e substituir as cores e ícones originais por um padrão neutro cinza (`#9CA3AF`) para ocultar a natureza da ausência. *(Mitigado na versão atual)*

### 4.3. Ausência de Limites no campo de anotações (`notes`) de eventos
* **Severidade:** Baixa
* **Tipo:** Vulnerabilidade / Dívida Técnica
* **Risco de Exploração:** Baixo
* **Superfície de Ataque:** Rota `POST` / `PUT` `/api/v1/calendario/eventos`
* **Descrição:** O campo `notes` era persistido diretamente no banco sem limites de comprimento no schema Pydantic (`CalendarEventCreate`), expondo o sistema a ataques de saturação de disco ou estouro de memória no parse do JSON.
* **Mitigação Recomendada:** Adicionar constraint de tamanho máximo (`max_length=2000`) nos campos correspondentes do Pydantic para validação na borda da API. *(Mitigado na versão atual)*

---

## 5. Defeitos Funcionais e Inconsistências

### 5.1. Inconsistência de status da Aeronave sob Inspeção
* **Severidade:** Alta
* **Tipo:** Bug
* **Evidência:** `app/modules/aeronaves/service.py` (`alternar_status_aeronave`) e `app/modules/inspecoes/service.py` (`cancelar_inspecao`, `concluir_inspecao`).
* **Descrição:** O toggle de status manual da aeronave forçava `INATIVA` mesmo que a aeronave estivesse fisicamente sob inspeção ativa. De forma oposta, a conclusão de uma inspeção secundária marcava a aeronave como `DISPONIVEL` mesmo que houvesse outra inspeção ativa pendente na mesma célula.
* **Impacto:** Riscos operacionais severos de dupla alocação ou liberação para voo de aeronaves com pendências graves de manutenção.
* **Recomendação:** Adicionar validação de concorrência de inspeções ativas antes de reverter o status para `DISPONIVEL`. Impedir a inativação forçada de aeronaves que possuam ordens de inspeção ativas em andamento. *(Resolvido)*

### 5.2. Omissão de Herança de Vencimentos em Ajustes de Inventário
* **Severidade:** Média
* **Tipo:** Bug
* **Evidência:** `app/modules/equipamentos/service.py` (função `_obter_ou_criar_item_por_pn`).
* **Descrição:** Ao inserir um número de série inexistente via rota de ajuste de inventário, o sistema criava o registro físico do componente, mas não aplicava as regras de vencimento temporal herdadas do Part Number (`EquipamentoControle`). O componente operava na aeronave sem prazo de expiração monitorado.
* **Impacto:** Voos operando com equipamentos sem inspeção/calibração periódica controlada por alertas.
* **Recomendação:** Unificar a criação de itens físicos em um helper comum que herde obrigatoriamente os vencimentos cadastrados para o PN correspondente. *(Resolvido)*

### 5.3. Queda de Rastreabilidade na Instalação de Equipamentos (Usuario Nulo)
* **Severidade:** Média
* **Tipo:** Inconsistência / Bug
* **Evidência:** `app/modules/equipamentos/router.py` (função `instalar_item` descartando dependência de usuário).
* **Descrição:** O endpoint de instalação de componentes em slots aeronáuticos não transmitia o identificador do executor (`usuario_id`) para a camada de serviço, registrando a movimentação histórica com autor nulo (`NULL`).
* **Impacto:** Perda de trilha de auditoria para movimentação de material aviônico sensível.
* **Recomendação:** Passar explicitamente o `current_user.id` do router para o service de inventário e persistir o trigrama correspondente. *(Resolvido)*

---

## 6. Problemas de Arquitetura e Manutenibilidade

### 6.1. Acoplamento de Transações no Service (`db.commit` e `db.rollback` internos)
* **Severidade:** Média
* **Tipo:** Risco Arquitetural
* **Evidência:** `app/modules/auth/service.py` (commit manual no brute force), `app/modules/efetivo/service.py` (commits nos serviços), `app/modules/equipamentos/service.py` (rollback no ajuste de inventário).
* **Descrição:** A camada de serviço de alguns módulos gerenciava o fluxo transacional do banco diretamente (chando `commit()` ou `rollback()` na sessão). Isso quebra o padrão de "Unidade de Trabalho" (Unit of Work) centralizado no middleware/dependência do FastAPI, além de fragmentar sessões compostas por múltiplas operações.
* **Impacto:** Dificuldade em reutilizar serviços de forma combinada. Rolbacks internos abortam logs de auditoria de operações prévias na mesma requisição.
* **Recomendação:** Limitar a camada de serviço exclusivamente ao uso de `db.flush()`. Deixar o encerramento transacional (commit/rollback) a cargo do gerenciador de dependência global `get_db`. *(Resolvido)*

### 6.2. Instanciação Ineficiente de Conexões no R2StorageService
* **Severidade:** Baixa
* **Tipo:** Performance / Dívida Técnica
* **Evidência:** `app/shared/core/storage.py` (função `get_storage_service` sem cache).
* **Descrição:** A cada chamada do storage, uma nova instância do cliente boto3 era gerada, exigindo resolução de credenciais e alocação de pool HTTP a cada upload de anexo ou download de imagem.
* **Impacto:** Degradação da latência de requests e consumo desnecessário de sockets TCP.
* **Recomendação:** Implementar cache do serviço de storage usando `@functools.lru_cache(maxsize=1)` para reuso do cliente como Singleton thread-safe. *(Resolvido)*

---

## 7. Oportunidades de Otimização e Melhoria

### 7.1. Tratamento de Erros e Estados Incompletos no Pipeline de Imagem
* **Severidade:** Média
* **Tipo:** Melhoria / Robustez
* **Descrição:** Uploads de imagens em background marcam o anexo como `"processando"`. Falhas críticas no pipeline deixavam o registro nesse estado terminal indefinidamente, impossibilitando que a UI mostrasse o erro ou limpasse o registro órfão.
* **Recomendação:** Garantir que o bloco `except` de falha de conversão física grave o status de `"ERRO"` ou limpe o registro no banco para permitir nova tentativa pelo operador. *(Resolvido)*

### 7.2. Risco de DoS em Requisições de Calendário por Ranges Amplos
* **Severidade:** Média
* **Tipo:** Performance / Estabilidade
* **Descrição:** A rota de listagem de eventos permitia intervalos temporais ilimitados sem paginação física ou limites de busca no banco, sobrecarregando a memória do servidor com serializações volumosas de dados.
* **Recomendação:** Aplicar restrição rígida de range máximo permitido na API (ex: 366 dias) e limite físico (`limit 5000`) nas queries de busca do SQLAlchemy. *(Resolvido)*

### 7.3. Falta de Rastreabilidade em Remoções de Eventos (Hard Delete)
* **Severidade:** Média
* **Tipo:** Melhoria / Auditoria
* **Descrição:** A deleção física de eventos no calendário apagava os registros definitivamente do banco, incluindo notas operacionais de escalas e dispensas médicas de mecânicos.
* **Recomendação:** Implementar soft delete (`deleted_at` / `deleted_by_user_id`) no modelo de calendário e emitir log de aviso estruturado antes da marcação. *(Resolvido)*

---

## 8. Plano de Correção Priorizado

Como a maioria das correções críticas e bugs operacionais documentados já se encontra implementada e validada, o plano de prioridade a seguir está focado na **estabilização arquitetural, evolução de performance e mitigação de gargalos operacionais:**

| Prioridade | Tarefa | Justificativa | Esforço | Dependências | Risco Mitigado | Critério de Aceite |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Crítica** | **Migração de DB para PostgreSQL** | O SQLite não escalará com múltiplos operadores gravando inventários e logs de auditoria concorrentemente. | Médio | Configuração de ambiente de staging/homologação | Travamento de banco de dados (database locked) em horários de pico. | Execução de testes de estresse em PostgreSQL local sem deadlock de transação. |
| **2. Alta** | **Tratamento de Exceções de Storage em Transação** | Garantir que erros de exclusão física do arquivo no R2 impeçam o expurgo da referência do banco. | Baixo | R2StorageService | Registros órfãos no banco ou arquivos inacessíveis acumulados. | `excluir_anexo` gera exceção e impede deleção do banco se R2 falhar fisicamente. |
| **3. Média** | **Ajuste fino de fallback do python-magic** | Tratar cenários de falha na dependência libmagic de sistema em deploys Serverless (Docker Alpine). | Baixo | Dockerfile | Erro 500 em uploads de anexos no deploy de nuvem. | Logs limpos e uploads de PNG/JPG/PDF funcionando no container minimalista. |
| **4. Baixa** | **Criação de fila de expurgo assíncrona** | Mover deleções de anexos físicos para uma fila, evitando tempo de espera síncrono no request. | Médio | BackgroundTasks / Celery | Bloqueio do worker HTTP esperando resposta de rede do storage (I/O bloqueante). | Endpoint retorna 204 instantaneamente e tarefa em segundo plano executa o expurgo. |

---

## 9. Plano de Testes Pós-Correção

Para garantir a ausência de regressões durante a aplicação das correções pendentes ou migração de banco de dados:

### 9.1. Testes Unitários e de Integração
* Executar a suíte de testes padrão para verificar se contratos Pydantic e relacionamentos continuam consistentes:
  ```powershell
  .venv\Scripts\pytest -v
  ```
* Validar cenários de concorrência com o SQLite no modo WAL (ou simulação de múltiplos clients no postgres):
  ```powershell
  .venv\Scripts\pytest tests/architecture/test_performance_audit.py -k "wal"
  ```

### 9.2. Testes de Regressão e Segurança
* **Teste de CSRF:** Validar se endpoints de mutação (POST, PUT, DELETE) barram requisições sem o token X-CSRF-Token:
  ```powershell
  .venv\Scripts\pytest tests/security/test_csrf.py -v
  ```
* **Teste de Token Rotation:** Confirmar que a tentativa de reuso de um Refresh Token invalida as sessões ativas do usuário e bloqueia o acesso:
  ```powershell
  .venv\Scripts\pytest tests/security/test_refresh_token.py -v
  ```

### 9.3. Validação de Migrações Alembic
* Ao realizar qualquer alteração estrutural no banco, testar os scripts de upgrade e downgrade antes do merge na master:
  ```powershell
  .venv\Scripts\alembic upgrade head
  .venv\Scripts\alembic downgrade -1
  ```

---

## 10. Conclusão Final

### Status Geral
O sistema **SAA29** encontra-se em um estado maduro, com regras de negócio bem encapsuladas nas camadas de serviço e controllers finos. A ausência de lógicas espalhadas e o alto índice de cobertura de testes automatizados garantem segurança para evoluções.

### Prontidão para Evolução PWA/Web
O projeto está **plenamente coerente para evolução futura como PWA (Progressive Web App)**:
* A API REST está estruturada de forma independente da interface, facilitando o consumo por um frontend moderno em SPA (React/Vue/Svelte) ou PWA.
* Os contratos Pydantic estão bem mapeados, o que simplifica a geração automática de clientes Typescript/OpenAPI.
* As políticas de Content Security Policy (CSP) já eliminam inline scripts, atendendo aos padrões exigidos por lojas de aplicativos móveis ou navegadores rígidos.

### Ações Imediatas Recomendadas
1. **Configurar Postgres em Homologação:** Subir um container docker do PostgreSQL para rodar os testes de integração e homologar o comportamento sob transações simultâneas.
2. **Definir Monitoramento do R2:** Adicionar tratamento de erros refinado nos logs estruturados para disparar alertas quando o Cloudflare R2 retornar códigos 5xx ou falha de timeout.
3. **Auditoria de Desempenho (Query N+1):** Monitorar as rotas de busca de panes e matriz de vencimentos, adicionando `selectinload` ou `joinedload` onde novos relacionamentos forem criados no futuro.
