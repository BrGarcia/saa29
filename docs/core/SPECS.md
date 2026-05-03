# SPECS - SAA29

Documento sincronizado com o codigo-fonte em 22/04/2026.

Este documento descreve o comportamento esperado dos fluxos principais do sistema em formato de especificacao funcional.

## 1. Autenticacao

### 1.1 Login

Entrada:

- username
- password

Fluxo:

1. Receber credenciais.
2. Buscar usuario por username.
3. Validar status ativo e bloqueio temporario.
4. Comparar senha com hash armazenado.
5. Se valido, emitir access token JWT e refresh token.
6. Persistir refresh token para rastreio e revogacao.
7. Gravar o access token no cookie `saa29_token`.

Saida:

- `200` com tokens e dados do usuario.
- `401` para credenciais invalidas.
- `429` se a conta estiver temporariamente bloqueada.

### 1.2 Refresh

Entrada:

- refresh token

Fluxo:

1. Receber refresh token.
2. Validar assinatura e tipo.
3. Confirmar existencia do `jti` no banco.
4. Verificar se o token nao foi revogado.
5. Gerar novo access token.
6. Rotacionar o refresh token.

Saida:

- `200` com novos tokens.
- `401` se token for invalido, expirado ou revogado.

### 1.3 Logout

Fluxo:

1. Obter token atual do header ou cookie.
2. Decodificar JWT.
3. Registrar `jti` em blacklist.
4. Remover cookie `saa29_token`.

Saida:

- `204` sem conteudo.

## 2. Cadastro de Aeronave

Fluxo:

1. Receber dados de aeronave.
2. Validar unicidade de serial e matricula.
3. Salvar aeronave.
4. Retornar aeronave persistida.

Regras:

- `status` padrao deve ser `OPERACIONAL`.
- apenas `ADMINISTRADOR` pode criar.

## 3. Registro de Pane

### 3.1 Criar pane

Fluxo:

1. Receber aeronave, descricao, sistema/subsistema e responsavel opcional.
2. Validar existencia da aeronave.
3. Se descricao estiver vazia, substituir por `AGUARDANDO EDICAO`.
4. Criar pane com status `ABERTA`.
5. Registrar `criado_por_id` e `data_abertura`.
6. Se houver responsavel inicial valido, vincular na tabela de relacionamento.

Saida:

- `201` com pane criada.
- `404` se a aeronave nao existir.

### 3.2 Editar pane

Fluxo:

1. Carregar pane.
2. Verificar se a pane esta ativa e com status `ABERTA`.
3. Permitir alteracao de descricao, sistema/subsistema, comentarios e status conforme regra.
4. Persistir alteracoes.

Saida:

- `200` com pane atualizada.
- `409` se a transicao de status for invalida.
- `404` se a pane nao existir.

### 3.3 Concluir pane

Fluxo:

1. Receber observacao de conclusao.
2. Validar pane ativa.
3. Marcar status como `RESOLVIDA`.
4. Preencher `data_conclusao`.
5. Registrar `concluido_por_id`.

Saida:

- `200` com pane resolvida.
- `409` se a pane ja estiver resolvida.

### 3.4 Anexos

Fluxo:

1. Receber arquivo upload.
2. Validar extensao e tipo MIME.
3. Armazenar arquivo em storage local ou R2.
4. Registrar caminho no banco.

Saida:

- `201` com anexo criado.
- `422` se o arquivo nao for aceito.

### 3.5 Responsaveis

Fluxo:

1. Receber usuario e papel.
2. Validar permissao do usuario logado.
3. Registrar responsavel na pane.

Regra:

- `MANTENEDOR` pode assumir apenas a propria responsabilidade.

## 4. Inventario de Equipamentos

### 4.1 Criar modelo

Fluxo:

1. Receber part number, nome generico e descricao.
2. Validar unicidade do part number.
3. Persistir modelo.

### 4.2 Criar slot

Fluxo:

1. Receber nome da posicao, sistema e modelo vinculado.
2. Validar modelo existente.
3. Persistir slot.

### 4.3 Criar item

Fluxo:

1. Receber modelo e numero de serie.
2. Validar unicidade do SN para o PN.
3. Persistir item.
4. Buscar controles vinculados ao modelo.
5. Criar controles de vencimento herdados para o item.

### 4.4 Associar controle ao modelo

Fluxo:

1. Receber modelo e tipo de controle.
2. Criar associacao.
3. Propagar controle para todos os itens existentes do modelo.

### 4.5 Instalar item

Fluxo:

1. Receber item, aeronave e data de instalacao.
2. Encerrar instalacao ativa anterior do item, se existir.
3. Criar nova instalacao.

### 4.6 Remover item

Fluxo:

1. Receber instalacao e data de remocao.
2. Marcar a instalacao como encerrada.
3. Registrar usuario responsavel, se fornecido.

### 4.7 Inventario atual

Fluxo:

1. Buscar slots da aeronave.
2. Cruzar slot com instalacao ativa.
3. Retornar item, serie, datas e identificacao da aeronave anterior, quando existir.

### 4.8 Ajuste de inventario

Fluxo:

1. Receber aeronave, slot, numero de serie real e opcao de transferencia.
2. Localizar slot e item correspondente.
3. Se o item estiver em outra aeronave, exigir confirmacao para transferencia.
4. Encerrar instalacao anterior e criar nova instalacao no slot alvo.

## 5. Controles de Vencimento

### 5.1 Registrar execucao

Fluxo:

1. Receber id do vencimento e data de execucao.
2. Buscar controle e seu tipo.
3. Atualizar data da ultima execucao.
4. Calcular nova data de vencimento com base na periodicidade do tipo.
5. Atualizar status para `OK`, `VENCENDO` ou `VENCIDO`.

### 5.2 Regras de calculo

- periodicidade em meses vem de `TipoControle`;
- status `VENCENDO` pode ser usado quando faltar pouco tempo para o vencimento;
- o vencimento e persistido, nao calculado apenas em consulta.

## 6. Padroes de API

- Todas as operacoes protegidas exigem JWT valido.
- O sistema deve aceitar header `Authorization` e cookie `saa29_token`.
- A camada HTTP deve converter erros de negocio em `400`, `401`, `403`, `404`, `409` ou `422` conforme o caso.
- Listagens devem suportar filtros e paginação quando aplicavel.

## 7. Validacoes Gerais

- campos obrigatorios nao podem ser omitidos;
- ids devem ser UUID validos;
- strings devem respeitar tamanho maximo definido nos schemas;
- uploads devem rejeitar extensoes nao permitidas;
- status fora do enum devem ser rejeitados pelo schema.

## 8. Observacoes de Implementacao

- O fluxo de frontend ainda usa rotas HTML em `app/web/pages/router.py` e templates Jinja.
- O sistema possui regras de seguranca adicionais como CSRF, Trusted Host e rate limiting.
- O comportamento real das telas deve ser considerado validado pelos testes em `tests/unit` e `tests/security`.
