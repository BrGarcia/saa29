# Referencia da API - SAA29

Documento sincronizado com o codigo-fonte em 22/04/2026.
Base para os endpoints: `app/modules/*/router.py` e `app/bootstrap/main.py`.

## 1. Visao Geral

- Base URL local: `http://localhost:8000`
- Documentacao interativa: `http://localhost:8000/docs`
- Autenticacao principal: `Authorization: Bearer <JWT>`
- Autenticacao para web: cookie HttpOnly `saa29_token`

O `get_token_from_request()` tenta primeiro o header `Authorization` e depois o cookie `saa29_token`, entao a mesma API funciona bem para Swagger e para a interface web.

## 2. Autenticacao e RBAC

### Perfis

- `ADMINISTRADOR`
- `ENCARREGADO`
- `MANTENEDOR`

### Regras gerais

- Endpoints protegidos exigem JWT valido.
- Logout invalida o token atual via blacklist.
- Login retorna access token e refresh token.
- O refresh token e rotacionado quando usado.

### Códigos de resposta comuns

| Codigo | Significado |
|---|---|
| `200` | OK |
| `201` | Criado |
| `204` | Sem conteudo |
| `401` | Nao autenticado ou token invalido |
| `403` | Sem permissao |
| `404` | Nao encontrado |
| `409` | Conflito de regra de negocio |
| `422` | Validacao Pydantic |

---

## 3. Auth

Base: `/auth`

### `POST /auth/login`

Autentica o usuario e retorna:

- `access_token`
- `refresh_token`
- `usuario`

Request: `application/x-www-form-urlencoded`

```text
username=joao.silva
password=senha123
```

Response `200`:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "usuario": {
    "id": "uuid",
    "nome": "Ten Joao Silva",
    "posto": "Ten",
    "especialidade": null,
    "funcao": "ENCARREGADO",
    "ramal": null,
    "trigrama": "JOS",
    "username": "joao.silva",
    "ativo": true,
    "created_at": "2026-04-22T05:00:00Z"
  }
}
```

Observacoes:

- O access token tambem e gravado no cookie `saa29_token`.
- O refresh token tem validade de 7 dias.
- Contas com falhas repetidas podem ser bloqueadas temporariamente.

### `POST /auth/refresh`

Gera novo access token a partir de um refresh token valido.

Request body (`RefreshTokenRequest`):

```json
{
  "refresh_token": "eyJ..."
}
```

Response `200`: mesmo formato do login.

### `POST /auth/logout`

Invalida a sessao atual.

- remove o cookie `saa29_token`;
- registra o `jti` do token em `token_blacklist`.

Response `204`.

### `GET /auth/me`

Retorna os dados do usuario autenticado.

Response `200`:

- `UsuarioOut`

### `POST /auth/usuarios`

Cria um novo usuario.

Permissao: `ADMINISTRADOR`

Request body (`UsuarioCreate`):

```json
{
  "nome": "Ten Joao Silva",
  "posto": "Ten",
  "especialidade": "Eletronica",
  "funcao": "ENCARREGADO",
  "ramal": "1234",
  "trigrama": "JOS",
  "username": "joao.silva",
  "password": "senha123"
}
```

Response `201`: `UsuarioOut`

### `GET /auth/usuarios`

Lista usuarios.

Permissao: usuario autenticado.

Query params:

- `inativos` (`bool`, default `false`)

Response `200`: `list[UsuarioOut]`

### `PUT /auth/usuarios/senha`

Altera a senha do usuario autenticado.

Request body (`SenhaUpdate`):

```json
{
  "senha_atual": "senha123",
  "nova_senha": "nova_senha123"
}
```

Response `204`.

### `PUT /auth/usuarios/{usuario_id}`

Atualiza dados cadastrais de um usuario.

Permissao: `ADMINISTRADOR`

Request body (`UsuarioUpdate`):

```json
{
  "nome": "Ten Joao Silva",
  "posto": "Cap",
  "especialidade": "Eletronica",
  "funcao": "ENCARREGADO",
  "ramal": "1234",
  "trigrama": "JOS"
}
```

Response `200`: `UsuarioOut`

### `DELETE /auth/usuarios/{usuario_id}`

Desativa um usuario do efetivo.

Permissao: `ADMINISTRADOR`

Response `204`.

### `POST /auth/usuarios/{usuario_id}/restaurar`

Reativa um usuario desativado.

Permissao: `ADMINISTRADOR`

Response `200`: `UsuarioOut`

---

## 4. Aeronaves

Base: `/aeronaves`

### `GET /aeronaves/`

Lista aeronaves.

Permissao: usuario autenticado.

Query params:

- `skip` (`int`, default `0`)
- `limit` (`int`, default `100`)
- `incluir_inativas` (`bool`, default `false`)

Response `200`: `list[AeronaveListItem]`

### `POST /aeronaves/`

Cadastra uma aeronave.

Permissao: `ADMINISTRADOR`

Request body (`AeronaveCreate`):

```json
{
  "part_number": "A-29",
  "serial_number": "SN-0001",
  "matricula": "5916",
  "modelo": "A-29",
  "status": "OPERACIONAL"
}
```

Response `201`: `AeronaveOut`

### `GET /aeronaves/{aeronave_id}`

Detalha uma aeronave.

Permissao: usuario autenticado.

Response `200`: `AeronaveOut`

### `PUT /aeronaves/{aeronave_id}`

Atualiza dados da aeronave.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Request body (`AeronaveUpdate`):

```json
{
  "part_number": "A-29",
  "serial_number": "SN-0001",
  "matricula": "5916",
  "modelo": "A-29",
  "status": "INDISPONIVEL"
}
```

Response `200`: `AeronaveOut`

### `POST /aeronaves/{aeronave_id}/toggle-status`

Alterna o status operacional da aeronave.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Response `200`: `AeronaveOut`

---

## 5. Panes

Base: `/panes`

### `POST /panes/`

Registra uma nova pane.

Permissao: usuario autenticado.

Request body (`PaneCreate`):

```json
{
  "aeronave_id": "uuid-da-aeronave",
  "sistema_subsistema": "COMUNICACAO / VUHF",
  "descricao": "Radio nao transmite",
  "mantenedor_responsavel_id": "uuid-opcional"
}
```

Observacao:

- o status inicial e sempre `ABERTA`, definido no service.

Response `201`: `PaneOut`

### `GET /panes/`

Lista panes com filtros.

Permissao: usuario autenticado.

Query params:

- `texto` (`str`, opcional)
- `status` (`StatusPane`, opcional)
- `aeronave_id` (`UUID`, opcional)
- `data_inicio` (`datetime`, opcional)
- `data_fim` (`datetime`, opcional)
- `excluidas` (`bool`, default `false`)
- `skip` (`int`, default `0`)
- `limit` (`int`, default `100`)

Response `200`: `list[PaneListItem]`

### `GET /panes/{pane_id}`

Detalha uma pane com anexos e responsaveis.

Permissao: usuario autenticado.

Response `200`: `PaneOut`

### `PUT /panes/{pane_id}`

Edita uma pane.

Permissao:

- para `descricao` e `sistema_subsistema`: `ENCARREGADO` ou `ADMINISTRADOR`
- para campos gerais: usuario autenticado, sujeito as regras do service

Request body (`PaneUpdate`):

```json
{
  "sistema_subsistema": "COMUNICACAO / VUHF",
  "descricao": "Nova descricao",
  "comentarios": "Observacao interna",
  "status": "RESOLVIDA"
}
```

Response `200`: `PaneOut`

### `POST /panes/{pane_id}/concluir`

Conclui a pane e preenche `data_conclusao`.

Permissao: usuario autenticado.

Request body (`PaneConcluir`):

```json
{
  "observacao_conclusao": "Pane corrigida em teste operacional"
}
```

Response `200`: `PaneOut`

### `POST /panes/{pane_id}/anexos`

Upload de anexo.

Permissao: usuario autenticado.

Request: `multipart/form-data`

- campo `arquivo` (`UploadFile`)

Tipos aceitos:

- imagem
- documento

Response `201`: `AnexoOut`

### `GET /panes/{pane_id}/anexos`

Lista anexos da pane.

Permissao: usuario autenticado.

Response `200`: `list[AnexoOut]`

### `DELETE /panes/{pane_id}/anexos/{anexo_id}`

Remove um anexo da pane.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Response `204`.

### `GET /panes/{pane_id}/anexos/{anexo_id}/download`

Baixa ou redireciona para o arquivo do anexo.

Permissao: usuario autenticado.

Resposta:

- `FileResponse` para arquivo local
- `RedirectResponse` para URL remota

### `POST /panes/{pane_id}/responsaveis`

Adiciona responsavel a pane.

Regra de acesso:

- `ENCARREGADO` e `ADMINISTRADOR` podem atribuir qualquer usuario;
- `MANTENEDOR` so pode assumir a propria responsabilidade.

Request body (`AdicionarResponsavel`):

```json
{
  "usuario_id": "uuid",
  "papel": "MANTENEDOR"
}
```

Response `201`: `ResponsavelOut`

### `DELETE /panes/{pane_id}`

Soft delete da pane.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Response `204`.

### `POST /panes/{pane_id}/restaurar`

Restaura uma pane removida logicamente.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Response `200`: `PaneOut`

---

## 6. Equipamentos

Base: `/equipamentos`

### `GET /equipamentos/tipos-controle`

Lista tipos de controle.

Permissao: usuario autenticado.

Response `200`: `list[TipoControleOut]`

### `POST /equipamentos/tipos-controle`

Cria um tipo de controle.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Request body (`TipoControleCreate`):

```json
{
  "nome": "TBV",
  "descricao": "Teste basico de vencimento",
  "periodicidade_meses": 6
}
```

Response `201`: `TipoControleOut`

### `GET /equipamentos/`

Lista modelos de equipamento.

Permissao: usuario autenticado.

Response `200`: `list[ModeloEquipamentoOut]`

### `POST /equipamentos/`

Cria um modelo de equipamento.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Request body (`ModeloEquipamentoCreate`):

```json
{
  "part_number": "MA902B-02",
  "nome_generico": "MDP",
  "descricao": "Modulo de piloto"
}
```

Response `201`: `ModeloEquipamentoOut`

### `GET /equipamentos/{equipamento_id}`

Detalha um modelo de equipamento.

Permissao: usuario autenticado.

Response `200`: `ModeloEquipamentoOut`

### `POST /equipamentos/{equipamento_id}/controles/{tipo_controle_id}`

Associa um tipo de controle ao modelo e propaga o controle para os itens existentes.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Response `201`.

### `GET /equipamentos/slots/`

Lista slots configurados.

Permissao: usuario autenticado.

Response `200`: `list[SlotInventarioOut]`

### `POST /equipamentos/slots/`

Cria um slot de inventario.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Request body (`SlotInventarioCreate`):

```json
{
  "nome_posicao": "MDP1",
  "sistema": "CEI",
  "modelo_id": "uuid"
}
```

Response `201`: `SlotInventarioOut`

### `GET /equipamentos/itens/`

Lista itens de equipamento.

Permissao: usuario autenticado.

Query params:

- `equipamento_id` (`UUID`, opcional)

Response `200`: `list[ItemEquipamentoOut]`

### `POST /equipamentos/itens/`

Cria um item fisico.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Request body (`ItemEquipamentoCreate`):

```json
{
  "modelo_id": "uuid",
  "numero_serie": "SN-123456",
  "status": "ATIVO"
}
```

Response `201`: `ItemEquipamentoOut`

### `GET /equipamentos/itens/{item_id}/controles`

Lista os controles de vencimento de um item.

Permissao: usuario autenticado.

Response `200`: `list[ControleVencimentoOut]`

### `POST /equipamentos/itens/{item_id}/instalar`

Instala um item em uma aeronave.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Request body (`InstalacaoCreate`):

```json
{
  "aeronave_id": "uuid",
  "data_instalacao": "2026-04-22"
}
```

Response `201`: `InstalacaoOut`

### `PATCH /equipamentos/instalacoes/{instalacao_id}/remover`

Registra a remocao de um item.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Request body (`InstalacaoRemocao`):

```json
{
  "data_remocao": "2026-04-22"
}
```

Response `200`: `InstalacaoOut`

### `PATCH /equipamentos/vencimentos/{vencimento_id}/executar`

Registra a execucao de um controle de vencimento.

Permissao: `ENCARREGADO` ou `ADMINISTRADOR`

Request body (`ControleVencimentoUpdate`):

```json
{
  "data_ultima_exec": "2026-04-22",
  "observacao": "Executado em inspeção de rotina"
}
```

Observacao:

- o schema aceita `observacao`, mas o service atual usa apenas `data_ultima_exec`.

Response `200`: `ControleVencimentoOut`

### `GET /equipamentos/inventario/historico`

Lista as movimentacoes recentes de inventario.

Permissao: usuario autenticado.

Query params:

- `limit` (`int`, default `15`)
- `offset` (`int`, default `0`)

Response `200`: `list[InventarioHistoricoOut]`

### `GET /equipamentos/inventario/{aeronave_id}`

Lista o inventario atual de uma aeronave.

Permissao: usuario autenticado.

Query params:

- `nome` (`str`, opcional)

Response `200`: `list[InventarioItemOut]`

### `POST /equipamentos/inventario/ajuste`

Sincroniza o numero de serie real de um slot.

Permissao: usuario autenticado.

Request body (`AjusteInventarioCreate`):

```json
{
  "aeronave_id": "uuid",
  "slot_id": "uuid-opcional",
  "equipamento_id": "uuid-opcional",
  "numero_serie_real": "SN-ABC-001",
  "forcar_transferencia": false,
  "usuario_id": "uuid-opcional"
}
```

Response `200`: `AjusteInventarioResponse`

---

## 7. Enums Principais

- `StatusPane`: `ABERTA`, `RESOLVIDA`
- `StatusAeronave`: `OPERACIONAL`, `INDISPONIVEL`, `INATIVA`
- `StatusItem`: `ATIVO`, `ESTOQUE`, `REMOVIDO`
- `StatusVencimento`: `OK`, `VENCENDO`, `VENCIDO`
- `OrigemControle`: `PADRAO`, `ESPECIFICO`
- `TipoPapel`: `MANTENEDOR`, `ENCARREGADO`, `ADMINISTRADOR`
- `TipoAnexo`: `IMAGEM`, `DOCUMENTO`

## 8. Observacao Final

Esta pagina documenta a API real do projeto atual. Se houver mudanca em rotas, schemas ou permissao por papel, a referencia deve ser atualizada junto do codigo de `app/modules/*`.

Nota: o modulo `app/modules/inspecoes` possui router isolado em desenvolvimento, mas ainda nao esta registrado no bootstrap principal. Seus endpoints nao fazem parte da API ativa ate que a ativacao seja feita explicitamente.
