# Referência da API – SAA29

Base URL (desenvolvimento): `http://localhost:8000`  
Documentação interativa: `http://localhost:8000/docs`  
Autenticação: `Authorization: Bearer <JWT>`

---

## Autenticação

### `POST /auth/login`
Autentica o usuário e retorna um JWT.

**Request** (form-data)
```
username=joao.silva
password=senha123
```

**Response 200**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "usuario": {
    "id": "uuid",
    "nome": "Ten João Silva",
    "posto": "Ten",
    "funcao": "INSPETOR",
    "username": "joao.silva"
  }
}
```

**Erros:** `401` – credenciais inválidas

---

### `GET /auth/me`
Retorna os dados do usuário autenticado.

**Response 200** → `UsuarioOut`

---

## Aeronaves

### `GET /aeronaves/`
Lista todas as aeronaves.

**Response 200** → `list[AeronaveListItem]`

---

### `POST /aeronaves/`
Cadastra nova aeronave.

**Request Body**
```json
{
  "serial_number": "SN-0001",
  "matricula": "5900",
  "modelo": "A-29",
  "status": "OPERACIONAL"
}
```

**Response 201** → `AeronaveOut`  
**Erros:** `409` – matrícula ou serial duplicado

---

### `GET /aeronaves/{aeronave_id}`
Detalha uma aeronave.

**Response 200** → `AeronaveOut` | `404`

---

### `PUT /aeronaves/{aeronave_id}`
Atualiza aeronave (campos opcionais).

**Response 200** → `AeronaveOut` | `404`

---

## Panes

### `POST /panes/`
Registra nova pane. `status` inicial sempre `ABERTA` (RN-02).

**Request Body**
```json
{
  "aeronave_id": "uuid-da-aeronave",
  "sistema_subsistema": "COMUNICAÇÃO / VUHF",
  "descricao": "Rádio não transmite em 120.500 MHz"
}
```

**Response 201** → `PaneOut`  
**Erros:** `404` – aeronave não encontrada

---

### `GET /panes/`
Lista panes com filtros opcionais (RF-06).

**Query params:**
| Param | Tipo | Descrição |
|-------|------|-----------|
| `texto` | string | Filtro por texto na descrição |
| `status` | `ABERTA\|EM_PESQUISA\|RESOLVIDA` | Filtro por status |
| `aeronave_id` | UUID | Filtro por aeronave |

**Response 200** → `list[PaneListItem]`

---

### `GET /panes/{pane_id}`
Detalha pane com anexos e responsáveis.

**Response 200** → `PaneOut` | `404`

---

### `PUT /panes/{pane_id}`
Edita pane. Somente panes `ABERTA` ou `EM_PESQUISA` (RN-03).

**Request Body** (campos opcionais)
```json
{
  "descricao": "Nova descrição",
  "status": "EM_PESQUISA"
}
```

**Transições válidas:** `ABERTA→EM_PESQUISA`, `ABERTA→RESOLVIDA`, `EM_PESQUISA→RESOLVIDA`  
**Erros:** `409` – pane já resolvida ou transição inválida

---

### `POST /panes/{pane_id}/concluir`
Conclui a pane. Preenche `data_conclusao` automaticamente (RN-04).

**Response 200** → `PaneOut`  
**Erros:** `409` – pane já resolvida

---

### `POST /panes/{pane_id}/anexos`
Upload de imagem ou documento (multipart/form-data).

**Form field:** `arquivo` (file)  
**Tipos aceitos:** `image/jpeg`, `image/png`, `application/pdf`  
**Tamanho máx:** configurado em `MAX_UPLOAD_SIZE_MB`

**Response 201** → `AnexoOut`

---

## Equipamentos

### `POST /equipamentos/`
Cadastra tipo de equipamento.

```json
{
  "part_number": "AN/ARC-182",
  "nome": "VUHF2",
  "sistema": "COM"
}
```

### `POST /equipamentos/itens`
Cria item físico. **Herda automaticamente** os controles do equipamento (MODEL_DB §5.1).

```json
{
  "equipamento_id": "uuid",
  "numero_serie": "SN-123456"
}
```

### `POST /equipamentos/{equip_id}/controles/{tipo_id}`
Associa tipo de controle ao equipamento e **propaga** para todos os itens existentes (MODEL_DB §5.2).

### `PATCH /equipamentos/vencimentos/{id}/executar`
Registra execução de controle. Recalcula `data_vencimento`.

```json
{ "data_ultima_exec": "2026-01-15" }
```

---

## Códigos de Resposta

| Código | Significado |
|--------|-------------|
| `200` | OK |
| `201` | Criado |
| `204` | Sem conteúdo (delete/logout) |
| `401` | Não autenticado |
| `403` | Sem permissão |
| `404` | Não encontrado |
| `409` | Conflito (duplicata ou regra de negócio) |
| `422` | Dados inválidos (Pydantic) |
| `500` | Erro interno |

---

## Status de Pane (Enum)

```
ABERTA ──────────────────► RESOLVIDA
  │                            ▲
  └──► EM_PESQUISA ────────────┘
```

Tentativas de transição inválida retornam `409 Conflict`.
