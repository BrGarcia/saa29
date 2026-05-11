# Plano de Correção: Relatório de Auditoria Claude


Este documento detalha o plano de ação para corrigir as vulnerabilidades e bugs identificados no relatório de auditoria `docs/relatorio/claude.md`. Todas as correções propostas respeitam estritamente as diretrizes de segurança (Zero Inline Scripts / CSP) e o contexto arquitetural do SAA29 (DDD, SQLAlchemy async).

ATENCAO: Após realizar as correceos atualize o arquivo `docs/relatorio/claude.md` com os problemas corrigidos

## Visão Geral das Correções


A primeira auditoria (05/05/2026) identificou 5 itens críticos, sendo 2 de segurança, 2 bugs na regra de negócios de inspeções e 1 problema arquitetural de gerenciamento de sessão de banco de dados.
A segunda auditoria (06/05/2026) identificou 5 novos achados: 1 de segurança (CSRF), 3 bugs (inventário e processamento de anexos) e 1 problema arquitetural (commit prematuro em efetivo).

---


## 1. Módulo de Autenticação e Segurança (Auth)


### 1.1 Correção: Revogação do Refresh Token no Logout (Hash: `e3a1f7`)
*   **Problema:** O endpoint `/auth/logout` revoga o Access Token mas deixa o `saa29_refresh_token` intacto e não atualiza o registro no banco, permitindo que a sessão seja renovada.
*   **Plano de Ação (`app/modules/auth/router.py`):**
    1.  No endpoint de logout, interceptar o cookie `saa29_refresh_token` do request.
    2.  Decodificar o JWT do refresh token para extrair o campo `jti`.
    3.  Buscar em `TokenRefresh` com esse `jti`.
    4.  Atualizar a coluna `revogado_em = func.now()`.
    5.  No objeto `response`, invocar `response.delete_cookie(key="saa29_refresh_token", path="/auth/refresh")`.


### 1.2 Correção: Verificação de Usuário Ativo no Middleware (Hash: `b2c9d4`)
*   **Problema:** A função `get_current_user` não barra usuários logicamente desativados.
*   **Plano de Ação (`app/bootstrap/dependencies.py`):**
    1.  Logo após a busca do usuário no banco de dados (`if usuario is None:`), adicionar:
        ```python
        if not usuario.ativo:
            raise credentials_exception
        ```
*   **Alinhamento CTX:** Garante a "revogação instantânea de acesso".


### 1.3 Arquitetura: Delegar Commit em `autenticar_usuario` (Hash: `a9f2b1`)
*   **Problema:** `autenticar_usuario` executa `await db.commit()` diretamente, encerrando prematuramente a transação.
*   **Plano de Ação (`app/modules/auth/service.py` e `router.py`):**
    1.  Substituir as chamadas de `await db.commit()` por `await db.flush()` em `autenticar_usuario`.
    2.  Refatorar `POST /auth/login` em `router.py` para capturar falhas de autenticação (`raise HTTPException`) apenas *depois* de fazer um commit manual ou forçar a execução isolada para manter o log de tentativas.


---


## 2. Módulo de Inspeções (Regras de Negócio)


### 2.1 Bug: Status da Aeronave na Conclusão/Cancelamento (Hash: `f1a3e8`)
*   **Problema:** Cancelar ou concluir joga a aeronave para `DISPONIVEL` ignorando inspeções paralelas.
*   **Plano de Ação (`app/modules/inspecoes/service.py`):**
    1.  Antes de alterar o status da aeronave em `cancelar_inspecao` e `concluir_inspecao`.
    2.  Verificar `inspecoes_ativas_paralelas = SELECT COUNT(*) ...`.
    3.  Apenas se o resultado for 0, definir `DISPONIVEL`.


### 2.2 Bug: Deduplicação de Tarefas Ignorando "Obrigatória" (Hash: `d7b5c2`)
*   **Problema:** Um cartão opcional sendo inserido antes de um obrigatório pode fazer a tarefa virar opcional.
*   **Plano de Ação (`app/modules/inspecoes/service.py`):**
    1.  Em `abrir_inspecao`, durante a deduplicação, fundir a restrição: `vistos[titulo]['obrigatoria'] = vistos[titulo]['obrigatoria'] or template.obrigatoria`.


---


## 3. Core e Segurança (2026-05-06)


### 3.1 Segurança: Bypass de CSRF em ambientes não-produção (Hash: `c8e4a2`)
*   **Problema:** O header `X-Skip-CSRF: true` desativa a validação em qualquer ambiente exceto `production`, permitindo bypass em staging/homologação.
*   **Plano de Ação (`app/shared/middleware/csrf.py`):**
    1.  Modificar a validação para que a exceção só ocorra quando `settings.app_env == "testing"`.
    2.  Remover ou limitar rigorosamente o uso do header `X-Skip-CSRF`.


---


## 4. Módulo de Equipamentos / Inventário (2026-05-06)


### 4.1 Bug: Ajuste de inventário não herda controles de vencimento (Hash: `4d9c1b`)
*   **Problema:** A criação de um novo `ItemEquipamento` via ajuste de inventário ignora a matriz de vencimentos daquele modelo de equipamento.
*   **Plano de Ação (`app/modules/equipamentos/service.py`):**
    1.  Em `_obter_ou_criar_item_por_pn`, logo após o `db.add(item)` e `db.flush()`, adicionar a lógica de herança.
    2.  Consultar `EquipamentoControle` associado ao `modelo_id`.
    3.  Inserir os registros correspondentes em `ControleVencimento` para o novo item.
    4.  *(Opcional/Recomendado)* Extrair a lógica de herança de `criar_item_com_heranca` para um helper reutilizável.


---


## 5. Módulo de Panes / Anexos (2026-05-06)


### 5.1 Bug: Ordem de exclusão de anexo gera arquivos órfãos (Hash: `7e2f50`)
*   **Problema:** A função deleta o registro do banco antes de tentar apagar do storage (R2). Se o storage falhar, o banco sofre rollback, mas o arquivo fica órfão.
*   **Plano de Ação (`app/modules/panes/service.py`):**
    1.  Em `excluir_anexo`, capturar o `caminho_arquivo`.
    2.  Tentar remover primeiro do storage com `await storage_svc.delete(caminho)`.
    3.  Apenas após o sucesso no storage, deletar o registro do banco `await db.delete(anexo)` e `await db.flush()`.
    4.  Tratar exceções do storage apropriadamente.


### 5.2 Bug: Imagens de background travadas em "processando" (Hash: `b6a8d3`)
*   **Problema:** Falhas no processamento em background deixam o anexo eternamente com `caminho_arquivo="processando"`, quebrando a UI.
*   **Plano de Ação (`app/modules/panes/service.py`):**
    1.  Em `processar_imagem_background`, no bloco de fallback genérico (`except Exception`), atualizar o registro no banco para um estado de erro.
    2.  Abrir uma nova sessão (pois a anterior já pode ter falhado) e alterar o `caminho_arquivo` para algo como `"ERRO"` ou apagar o registro.


---


## 6. Módulo de Efetivo (2026-05-06)


### 6.1 Arquitetura: Commit prematuro no registro de indisponibilidade (Hash: `f3b7e9`)
*   **Problema:** Funções `registrar_indisponibilidade` e `remover_indisponibilidade` chamam `await db.commit()` diretamente no service, quebrando o padrão de transação por request.
*   **Plano de Ação (`app/modules/efetivo/service.py`):**
    1.  Substituir os `await db.commit()` por `await db.flush()`.
    2.  Remover chamadas desnecessárias de `await db.refresh(...)` após deleção se for o caso.


---


## 7. Conformidade com CSP e Padrões (Docs)


Nenhuma das implementações exige alterações no frontend. Tratam-se de refatorações no backend (Python), logo a **Conformidade com a CSP** (`docs/methodology/CSP.md`) permanece intacta (Zero Inline Scripts). O banco de dados não sofrerá migrações (DDL), mantendo o `CTX.md`.


## 8. Correções da Auditoria de 2026-05-07

### 8.1 Bug/Segurança: `R2StorageService.delete()` falha silenciosamente (Hash: `c1a8b9`)
*   **Problema:** O método de deleção do `R2StorageService` captura qualquer exceção e retorna `False` em vez de propagá-la. Em produção, se houver falha de remoção no bucket, a aplicação apaga do banco de dados ignorando que a remoção do S3 falhou, deixando arquivos órfãos.
*   **Plano de Ação (`app/shared/core/storage.py` e `app/modules/panes/service.py`):**
    1.  Em `app/shared/core/storage.py` (`R2StorageService.delete`), não engolir exceções. Deixar a exceção propagar para relatar que a exclusão falhou, ou tratar unicamente o erro de chave inexistente (404/`NoSuchKey`) para tratar como sucesso idempotente.
    2.  Em `app/modules/panes/service.py` (`excluir_anexo`), tratar explicitamente o retorno falso: `if not await storage_svc.delete(...): raise ValueError("Falha ao remover do storage")`.
*   **Testes (TDD):**
    1.  Teste unitário validando que se a deleção falha no mock do storage, a chamada a `excluir_anexo` levanta exceção e não faz commit de `db.delete()`.

### 8.2 Bug: `abrir_inspecao` "reativa" aeronave INATIVA (Hash: `b4d7e6`)
*   **Problema:** A função `abrir_inspecao` altera o `status` para `INSPECAO` sem validar se a aeronave está atualmente `INATIVA`, reativando-a incondicionalmente de forma equivocada e invisível no log de reativações.
*   **Plano de Ação (`app/modules/inspecoes/service.py`):**
    1.  Em `abrir_inspecao`, adicionar uma verificação do status logo após a consulta.
    2.  `if aeronave.status == StatusAeronave.INATIVA.value: raise ValueError(...)`.
*   **Testes (TDD):**
    1.  Teste de integração/service verificando que abrir inspeção para aeronave INATIVA lança a devida exceção de negócio.

### 8.3 Segurança: Detecção de reuso de refresh token (Hash: `8a2f31`)
*   **Problema:** O reuso de um refresh token já revogado (situação típica de tokens roubados ou vazados) apenas retorna `401`, não revogando toda a cadeia de tokens do usuário para interromper o comprometimento, como exige o OAuth 2.0 Security BCP.
*   **Plano de Ação (`app/modules/auth/router.py`):**
    1.  Na rota `POST /auth/refresh`, antes de responder com `401`, identificar se o `jti` fornecido existe mas está com a data `revogado_em` preenchida.
    2.  Se for detectado o reuso, rodar `UPDATE token_refresh SET revogado_em = NOW() WHERE usuario_id = :uid AND revogado_em IS NULL` revogando toda a família de tokens ativa daquele usuário.
*   **Testes (TDD):**
    1.  Teste de integração comprovando o cenário de reuso (usar o token que já sofreu rotação antes). O usuário legítimo deve ter todo o seu conjunto de access/refresh tokens revogado e um novo login será exigido.

### 8.4 Segurança: Endpoints de inventário sem validação RBAC (Hash: `e9c0a4`)
*   **Problema:** Rotas de instalação e movimentação de inventário exigem apenas que o solicitante seja o `CurrentUser`, ou seja, que esteja logado, permitindo que qualquer papel altere rastreabilidade sem o devido controle de privilégio.
*   **Plano de Ação (`app/modules/equipamentos/router.py`):**
    1.  Atualizar as injeções de dependência (`Depends`) nos endpoints:
    2.  `instalar_item` e `remover_item` passam a usar `ExecucaoPermitida` (que valida roles como MANTENEDOR, ENCARREGADO, ADMIN).
    3.  `ajustar_inventario` passa a usar `EncarregadoOuAdmin` (pois altera registros de S/N globais).
*   **Testes (TDD):**
    1.  Testes de integração injetando papel de usuário simples (ex.: `INSPETOR` ou não listado) na rota de instalação de item, devendo retornar HTTP 403.

### 8.5 Arquitetura: Instanciação repetida de `R2StorageService` (Hash: `7d52cb`)
*   **Problema:** A fábrica `get_storage_service` instancia um novo `R2StorageService` e, por consequência, um novo cliente `boto3` para cada solicitação injetada, gerando atraso e latência na rede.
*   **Plano de Ação (`app/shared/core/storage.py`):**
    1.  Decorar a função `get_storage_service` com `@functools.lru_cache(maxsize=1)`.
    2.  Como o cliente `boto3` é thread-safe, a utilização do singleton poupa criação redundante da sessão.
*   **Testes (TDD):**
    1.  Teste no escopo unitário que verifica se requisições sucessivas a `get_storage_service` retornam exatamente o mesmo objeto na memória (`is`).


## Próximos Passos
*   [x] Revisar/Implementar o item 1.1 e 1.3 (Sessão de Auth e Refresh Token).
*   [x] Implementar item 1.2 (Soft-delete).
*   [x] Corrigir as funções de Inspeção (2.1 e 2.2).
*   [x] Implementar correção CSRF (3.1).
*   [x] Corrigir bug de herança no inventário (4.1).
*   [x] Corrigir bugs de ordem de exclusão e estado de anexos (5.1 e 5.2).
*   [x] Refatorar commits do módulo de Efetivo (6.1).
*   [x] Corrigir bugs da Rodada 2 (Status Aeronave, Periodicidade, Session Sync).
*   [x] Implementar TDD e correção 8.1 (Storage error masking).
*   [x] Implementar TDD e correção 8.2 (Aeronave INATIVA e Inspeções).
*   [x] Implementar TDD e correção 8.3 (Segurança Refresh Token).
*   [x] Implementar TDD e correção 8.4 (RBAC no Inventário).
*   [x] Implementar TDD e correção 8.5 (Singleton do R2StorageService).

---

## Verificação de Implementação (2026-05-06)

Auditoria completa realizada lendo os arquivos-fonte. **Todos os 10 itens do plano foram implementados corretamente.** Resumo por seção:

| Hash | Local | Status |
| :--- | :--- | :---: |
| `e3a1f7` | `auth/router.py` – logout revoga refresh token no banco e apaga cookie | ✅ |
| `b2c9d4` | `dependencies.py:99` – `get_current_user` barra `usuario.ativo == False` | ✅ |
| `a9f2b1` | `auth/service.py:56,62` – `autenticar_usuario` usa `flush()`, commit delegado ao router | ✅ |
| `f1a3e8` | `inspecoes/service.py:573-604` – conclusão/cancelamento verifica inspeções paralelas antes de setar DISPONIVEL | ✅ |
| `d7b5c2` | `inspecoes/service.py:414` – deduplicação faz `or` no campo `obrigatoria` | ✅ |
| `c8e4a2` | `csrf.py:32-34` – bypass `X-Skip-CSRF` só aceito quando `app_env == "testing"` | ✅ |
| `4d9c1b` | `equipamentos/service.py:364-379` – `_obter_ou_criar_item_por_pn` herda `ControleVencimento` do modelo | ✅ |
| `7e2f50` | `panes/service.py:651-661` – `excluir_anexo` apaga storage ANTES do banco | ✅ |
| `b6a8d3` | `panes/service.py:593-603` – falha total marca `caminho_arquivo = "ERRO"` | ✅ |
| `f3b7e9` | `efetivo/service.py:35,61` – `registrar/remover_indisponibilidade` usam `flush()` | ✅ |
| `2c9d5f` | `aeronaves/service.py:48-50` – `alternar_status` bloqueia aeronave em INSPECAO | ✅ |
| `8e3b7a` | `vencimentos/service.py:186-191` – `registrar_execucao` levanta erro se regra não existe | ✅ |
| `5f1c4d` | `aeronaves/service.py:92-98` – `atualizar_aeronave` bloqueia `status=INSPECAO` via PUT | ✅ |
| `a2e6c8` | `vencimentos/service.py:74-107` – mudança de periodicidade recalcula `data_vencimento` existentes via ORM | ✅ |
| `9b4f1e` | `vencimentos/service.py:209,398,431` – `db.expire()` sincroniza cache após `__table__.update()` | ✅ |
| `c1a8b9` | `storage.py` e `panes/service.py` – deleção do storage propaga exceções / aborta no banco | ✅ |
| `b4d7e6` | `inspecoes/service.py` – `abrir_inspecao` bloqueia status INATIVA | ✅ |
| `8a2f31` | `auth/router.py` – endpoint `refresh` revoga todos os tokens na detecção de reuso | ✅ |
| `e9c0a4` | `equipamentos/router.py` – rotas de inventário restritas via RBAC correto | ✅ |
| `7d52cb` | `storage.py` – `get_storage_service` decorado com `@functools.lru_cache(maxsize=1)` | ✅ |
| `f5d2a7` | `panes/service.py` – validação de papel real no banco em `adicionar_responsavel` | ✅ |
| `d4b8f1` | `equipamentos` – `instalar_item` agora grava `usuario_id` para rastreabilidade | ✅ |
| `e0c4d3` | `equipamentos` – removido `db.rollback()` do service, tratado no router | ✅ |
| `7b3f9a` | `auth/security.py` – aplicado pré-hash SHA-256 para evitar limite de bytes do bcrypt | ✅ |
| `3a9c8e` | `docs/architecture/RBAC.md` – documentada regra de Segurança de Voo para tarefas avulsas | ✅ |
---

## 9. Correções da Auditoria de 2026-05-07 (Rodada 2)

### 9.1 Segurança: Validação de papel em `adicionar_responsavel` (Hash: `f5d2a7`)
*   **Problema:** O endpoint permite que um usuário envie um `papel` arbitrário no payload (ex: um mantenedor se adicionando como administrador), afetando a rastreabilidade aeronáutica.
*   **Plano de Ação (`app/modules/panes/service.py`):**
    1.  Em `adicionar_responsavel`, buscar o usuário correspondente ao `usuario_id`.
    2.  Forçar o papel do registro `PaneResponsavel` para ser o papel real do banco (`usuario.funcao`), ignorando o payload.
*   **Testes (TDD):**
    1.  Testar requisição onde um MANTENEDOR tenta se associar com papel de ADMINISTRADOR, validando que o sistema o registra como MANTENEDOR (ou rejeita).

### 9.2 Bug: `instalar_item` perdendo rastreabilidade (`usuario_id=NULL`) (Hash: `d4b8f1`)
*   **Problema:** O endpoint descarta o usuário autenticado e a chamada ao service não informa quem realizou a instalação, gravando `usuario_id=NULL`.
*   **Plano de Ação (`app/modules/equipamentos/router.py` e `app/modules/equipamentos/service.py`):**
    1.  No router, usar `current_user: ExecucaoPermitida` e passar `usuario_id=current_user.id` para o service.
    2.  No service, receber `usuario_id` e incluí-lo na instância `Instalacao`.
*   **Testes (TDD):**
    1.  Verificar no banco se o registro de instalação criado via rota da API possui o `usuario_id` preenchido.

### 9.3 Arquitetura: `db.rollback()` direto em `ajustar_inventario_item` (Hash: `e0c4d3`)
*   **Problema:** O service executa rollback diretamente antes do final da requisição, rompendo o padrão de transação do projeto.
*   **Plano de Ação (`app/modules/equipamentos/service.py`):**
    1.  Remover o `try/except + await db.rollback()` no final do `ajustar_inventario_item`.
    2.  Tratar as exceções de banco no router (ou deixar o global error handler/dependency atuar) para gerenciar o rollback corretamente.
*   **Testes (TDD):**
    1.  Validar se erro de chave estrangeira ao ajustar inventário resulta na falha esperada e rollback sem comprometer a arquitetura.

### 9.4 Bug: Truncamento de senha por caracteres (Hash: `7b3f9a`)
*   **Problema:** O truncamento atual `[:72]` é baseado em caracteres. Bcrypt tem limite de 72 bytes. Caracteres multibyte no truncamento em caracteres podem estourar o limite de bytes do bcrypt.
*   **Plano de Ação (`app/modules/auth/security.py`):**
    1.  Alterar `hash_senha` e `verificar_senha` para realizar um pré-hash SHA-256 e converter para Base64 (`base64.b64encode(hashlib.sha256(senha_plana.encode()).digest())`).
*   **Testes (TDD):**
    1.  Testar o fluxo de hash e verificação utilizando senhas com emojis e outros caracteres multibyte longos (ex: "manutenção_aeronáutica🛩️").

### 9.5 Falso Positivo: `adicionar_tarefa_avulsa` (Hash: `3a9c8e`)
*   **Ação:** O comportamento atual (MANTENEDOR poder adicionar tarefa avulsa) é o correto pela regra de segurança de voo. Nenhuma alteração no código. Atualizar o documento `docs/architecture/RBAC.md` explicitando a regra.

---

## Próximos Passos
*   [x] Implementar TDD e correção 9.1 (Validação Papel Pane).
*   [x] Implementar TDD e correção 9.2 (Rastreabilidade Instalação).
*   [x] Implementar TDD e correção 9.3 (Remoção db.rollback).
*   [x] Implementar TDD e correção 9.4 (Fix bcrypt byte limit).
*   [x] Atualizar doc RBAC (9.5).
*   [ ] Implementar TDD e correção 10.1 (Filtro Inspeção).
*   [ ] Implementar TDD e correção 10.2 (Censura Eventos Privados).
*   [ ] Implementar TDD e correção 10.3 (Remover Duplicação RBAC).
*   [ ] Implementar TDD e correção 10.4 (Limite/Range de Data).
*   [ ] Implementar TDD e correção 10.5 (Rastreabilidade Delete).

---

## 10. Correções da Auditoria de 2026-05-11 (Módulo Calendário)

### 10.1 Bug: Filtro de status em `_get_inspection_events` (Hash: `c5a1b9`)
*   **Problema:** Eventos do calendário exibem inspeções já concluídas ou canceladas, prejudicando o planejamento da frota.
*   **Plano de Ação (`app/modules/calendario/service.py`):**
    1.  Importar `StatusInspecao` do módulo de inspeções.
    2.  Em `_get_inspection_events`, adicionar `.where(Inspecao.status.in_([StatusInspecao.ABERTA.value, StatusInspecao.EM_ANDAMENTO.value]))` na query base.
*   **Testes (TDD):**
    1.  Teste de integração verificando se inspeções com status `CONCLUIDA` ou `CANCELADA` deixam de aparecer em `/calendario/eventos`.

### 10.2 Segurança/Privacidade: Censura ineficaz de eventos privados (Hash: `9d3f2a`)
*   **Problema:** Eventos marcados como "Particulares" vazam o trigrama do dono e a cor associada ao tipo do evento, expondo informações sensíveis para MANTENEDORes.
*   **Plano de Ação (`app/modules/calendario/service.py`):**
    1.  Em `format_event_for_user`, no bloco `if should_censor:`, alterar a resposta para retornar `owner_trigram=None` e uma `backgroundColor` genérica (ex: `"#9CA3AF"`).
*   **Testes (TDD):**
    1.  Verificar que um evento particular consultado por usuário não dono retorna o `owner_trigram` nulo e cor cinza.

### 10.3 Arquitetura: Duplicação de Roles (Hash: `b7e4c1`)
*   **Problema:** O módulo reescreve permissões RBAC de forma manual (com alias `ADMIN` indevido) em vez de usar as dependências centralizadas de `bootstrap/dependencies.py`.
*   **Plano de Ação (`app/modules/calendario/router.py` e `app/modules/calendario/service.py`):**
    1.  Substituir conjuntos de papéis locais (`PRIVILEGED_ROLES`) por verificação de `funcao in {"ENCARREGADO", "ADMINISTRADOR"}`.
    2.  Modificar o router para usar dependências existentes (`AdminRequired` onde for o caso).
*   **Testes (TDD):**
    1.  Testar endpoint injetando usuário com `.funcao = "ADMIN"` (deve ser rejeitado).

### 10.4 Bug/DoS: Range ilimitado em `GET /calendario/eventos` (Hash: `4f8d6e`)
*   **Problema:** A rota permite puxar décadas de eventos de uma vez, arriscando DoS em ambiente de memória restrita.
*   **Plano de Ação (`app/modules/calendario/router.py` e `service.py`):**
    1.  Em `listar_eventos`, levantar `HTTPException(422)` se `(end_date - start_date).days > 366`.
    2.  Em `_get_calendar_events`, `_get_inspection_events` e `_get_task_events`, adicionar `.limit(5000)`.
*   **Testes (TDD):**
    1.  Teste da API enviando range de > 366 dias esperando 422.

### 10.5 Rastreabilidade: Hard-delete de Evento (Hash: `8c2b5d`)
*   **Problema:** A exclusão física via `delete()` impossibilita auditoria de quem apagou licenças, afastamentos, etc.
*   **Plano de Ação (`app/modules/calendario/service.py`):**
    1.  Em `delete_event`, implementar log estruturado `logger.warning(...)` antes da exclusão física, gravando o `event_id`, `deleted_by: current_user.id` e dono do evento. Como alternativa, introduzir uma flag de soft-delete.
*   **Testes (TDD):**
    1.  Validação de auditoria gerada ou flag alterada na deleção.

---

## Itens Pendentes Fora do Escopo Deste Plano

Os itens abaixo foram identificados em `docs/BACKLOG/implamentacao_image_editor.md` mas **não foram incluídos neste plano e permanecem sem correção**:

### ✅ GAP-01 – Download de anexo em processamento retorna 404 em vez de 409
*   **Localização:** `app/modules/panes/router.py` – endpoint `baixar_anexo` (linha ~277)
*   **Problema:** Quando `anexo.caminho_arquivo == "processando"`, o endpoint chama `storage_svc.get_url("processando")` e retorna 404 (arquivo não encontrado). O correto seria retornar 409 Conflict com mensagem "Anexo ainda está sendo processado."
*   **Correção:** (Implementada)

### ✅ GAP-02 – Extensões HEIC/HEIF bloqueadas na camada de validação do service
*   **Localização:** `app/modules/panes/service.py` – linhas 46-49
*   **Problema:** `_EXTENSOES_PERMITIDAS` e `_MIMES_PERMITIDOS` não incluem `.heic`, `.heif` e `image/heic`. O pipeline de imagem (`pipeline.py`) suporta HEIC via `pillow-heif`, mas o upload é rejeitado antes de chegar ao pipeline.
*   **Correção:** (Implementada)