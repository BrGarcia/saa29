# Revisão de Código

Foco: corretude, segurança e arquitetura, considerando `docs/requirements/00_SRS.md` e `docs/requirements/01_SPECS.md`.

## 1. Anexos ficam públicos fora do fluxo autenticado
- Severidade: Alta
- Evidência:
  - `app/main.py:102-104` monta `settings.upload_dir` diretamente em `/uploads` com `StaticFiles`.
  - `templates/panes/detalhe.html:342-355` gera links diretos para `/uploads/<arquivo>`.
- Problema:
  - O requisito de autenticação e proteção de upload é bypassado. Basta conhecer ou descobrir o nome do arquivo para baixar o anexo sem token e sem checagem de autorização.
  - Isso expõe evidências operacionais fora do domínio autenticado do sistema.
- Fix:
  - Remover a montagem pública de `/uploads`.
  - Servir anexos por endpoint autenticado, validando `CurrentUser` e a existência da pane antes de retornar `FileResponse` ou streaming.
  - Se precisar de links temporários, gerar URLs assinadas com expiração curta.

## 2. Controle de permissão de panes está só no frontend
- Severidade: Alta
- Evidência:
  - `templates/panes/lista.html:141-156` decide no navegador quem pode `EDIT` e `DELETE` usando `localStorage`.
  - `templates/panes/detalhe.html:173-195` decide no navegador quem pode delegar.
  - `app/panes/router.py:89-215` aceita editar, concluir, adicionar responsáveis e deletar usando apenas `CurrentUser`, sem RBAC de servidor.
- Problema:
  - Qualquer usuário autenticado consegue chamar a API diretamente e executar operações que a UI tenta esconder.
  - Isso é um bypass clássico de autorização por confiar na interface, não na API.
- Fix:
  - Aplicar dependências de RBAC no router de panes, por ação.
  - Exemplo mínimo:
    - editar/concluir: `EncarregadoOuAdmin` ou regra explícita por papel.
    - deletar: `AdminRequired` ou `EncarregadoOuAdmin`.
    - delegar responsável: `EncarregadoOuAdmin`.
  - Manter a lógica de ocultar botões no frontend apenas como conveniência visual, nunca como proteção real.

## 3. Regra de negócio RN-03 não está implementada
- Severidade: Alta
- Evidência:
  - `docs/requirements/00_SRS.md` define: "Apenas panes abertas podem ser editadas".
  - `app/panes/service.py:202-223` e `app/panes/router.py:95` permitem edição de qualquer pane que não esteja `RESOLVIDA`.
- Problema:
  - O sistema aceita editar panes em `EM_PESQUISA`, contrariando a regra declarada.
  - Isso gera comportamento inconsistente entre documentação, operação e testes de negócio.
- Fix:
  - Em `service.editar_pane`, rejeitar edição quando `status_atual != StatusPane.ABERTA`.
  - Se `EM_PESQUISA` precisa permitir só transições de status, separar isso em endpoint/regra específica, sem reaproveitar o endpoint genérico de edição.

## 4. A tela de listagem consome campos que a API não retorna
- Severidade: Alta
- Evidência:
  - `app/panes/schemas.py:104-117` define `PaneListItem` sem `criado_por_id`.
  - `templates/panes/lista.html:153` faz `pane.criado_por_id.substring(0,4)`.
- Problema:
  - Na resposta de `GET /panes/`, `criado_por_id` não existe. No navegador, `undefined.substring(...)` quebra a renderização da tabela.
  - Isso afeta o fluxo principal do sistema: a lista/dashboard de panes.
- Fix:
  - Escolher um contrato único e consistente:
    - ou incluir `criado_por_id` em `PaneListItem`;
    - ou alterar a template para usar um campo realmente retornado, por exemplo `responsaveis` ou um nome formatado vindo da API.
  - Adicionar teste de contrato API-frontend para a listagem.

## 5. Filtros prometidos pela especificação não chegam à API
- Severidade: Média
- Evidência:
  - `docs/requirements/00_SRS.md` e `docs/requirements/01_SPECS.md` pedem filtros por texto, aeronave, status e data.
  - `app/panes/schemas.py:19-28` já prevê `data_inicio`, `data_fim` e `excluidas`.
  - `app/panes/router.py:43-59` só recebe `texto`, `status`, `aeronave_id`, `skip`, `limit`.
  - `templates/panes/lista.html:101-103` envia `excluidas=true`, mas o router ignora esse parâmetro.
- Problema:
  - O filtro de excluídas nunca funciona.
  - Os filtros por data, previstos no schema e na especificação, não podem ser usados externamente.
  - Há desalinhamento entre schema, router e frontend.
- Fix:
  - Expor no endpoint os parâmetros `data_inicio`, `data_fim` e `excluidas`.
  - Cobrir os cenários com testes de integração para garantir que a query realmente altera o resultado.

## Resumo
- Altas: 4
- Médias: 1

## Prioridade de correção
1. Fechar acesso público a anexos.
2. Aplicar RBAC no backend das rotas de panes.
3. Corrigir a violação da RN-03.
4. Alinhar contrato da listagem (`PaneListItem` vs template).
5. Completar os filtros faltantes no router.
