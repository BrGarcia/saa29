# Plano de Implementação: Carregamento de Inventário via XLSX

## Objetivo

Criar um módulo na página **Configurações → Equipamentos e PNs** que permita carregar arquivos `.xlsx` contendo o inventário total de uma aeronave. O sistema lê o nome do arquivo (ex: `5906.xlsx`) para identificar a aeronave (MATRICULA.XLSX), cruza os Part Numbers (coluna B) com o catálogo cadastrado no banco de dados, usa a coluna E (Posição) para desambiguar o slot correto, e atribui o Serial Number real (coluna F) ao slot correspondente.

---

## Pré-requisitos

- Arquivos XLSX seguem a nomenclatura `MATRICULA.xlsx` (ex: `5906.xlsx`, `5914.xlsx`)
- Dependência Python: `openpyxl` (leitura de arquivos `.xlsx`)
- Os PNs do XLSX são comparados com a tabela `modelos_equipamento` (campo `part_number`)

### Estrutura Real do XLSX (9 colunas)

| Coluna | Letra | Campo | Uso no sistema |
|--------|-------|-------|----------------|
| 1 | A | Seq | Ignorado |
| 2 | B | **PN Principal** | Cruzamento com `modelos_equipamento.part_number` |
| 3 | C | CODEMP Principal | Ignorado |
| 4 | D | Nomenclatura Principal | Ignorado |
| 5 | E | **Posição** | Desambiguação de slot (ex: MF1, MF2) |
| 6 | F | **SN Real** | Serial Number a ser atribuído |
| 7 | G | PN Real | Ignorado |
| 8 | H | Tipo | Ignorado |
| 9 | I | Data Instalação | Ignorado |

---

## Arquitetura do Projeto (Referência)

```
app/
├── modules/
│   └── equipamentos/
│       ├── models.py      # ModeloEquipamento, SlotInventario, ItemEquipamento, Instalacao
│       ├── schemas.py     # AjusteInventarioCreate, AjusteInventarioResponse
│       ├── service.py     # ajustar_inventario_item(), _obter_ou_criar_item_por_pn()
│       └── router.py      # POST /equipamentos/inventario/ajuste (endpoint existente)
├── web/
│   └── templates/
│       └── configuracoes.html  # Card "Equipamentos e PNs" (linhas 46-79)
│   └── static/
│       └── js/
│           └── configuracoes.js
└── bootstrap/
    └── dependencies.py    # EncarregadoOuAdmin, CurrentUser, etc.
```

### Modelos Relevantes (models.py)

| Modelo | Tabela | Campos-chave |
|--------|--------|--------------|
| `ModeloEquipamento` | `modelos_equipamento` | `id`, `part_number` (único), `nome_generico` |
| `SlotInventario` | `slots_inventario` | `id`, `nome_posicao`, `sistema`, `modelo_id` (FK), **`posicao_xlsx`** (NOVO) |
| `ItemEquipamento` | `itens_equipamento` | `id`, `modelo_id` (FK), `numero_serie`, `status` |
| `Instalacao` | `instalacoes` | `id`, `item_id`, `aeronave_id`, `slot_id`, `data_instalacao`, `data_remocao` |

### Fluxo Existente de Ajuste de Inventário

O sistema já possui o endpoint `POST /equipamentos/inventario/ajuste` que recebe um `AjusteInventarioCreate`:

```python
class AjusteInventarioCreate(BaseModel):
    aeronave_id: uuid.UUID
    slot_id: uuid.UUID | None = None
    numero_serie_real: str
    forcar_transferencia: bool = False
    usuario_id: uuid.UUID | None = None
```

A função `ajustar_inventario_item()` em `service.py` já faz:
1. Busca o slot e seu modelo (PN)
2. Verifica se já existe um item com esse SN para o PN
3. Se não existe, cria o `ItemEquipamento` automaticamente
4. Resolve conflitos de transferência entre aeronaves
5. Efetiva a troca no slot

**Este fluxo será reutilizado pelo módulo XLSX.**

---

## Fases de Implementação

### Fase 1: Dependência Python e Modelo

#### 1.1 Dependência

**Arquivo:** `requirements.txt`

Adicionar a biblioteca `openpyxl`:

```
openpyxl>=3.1.0
```

#### 1.2 Nova coluna `posicao_xlsx` no modelo `SlotInventario`

**Arquivo:** `app/modules/equipamentos/models.py`

Adicionar o campo `posicao_xlsx` à classe `SlotInventario` (após `sistema`):

```python
posicao_xlsx: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
```

Essa coluna armazena o código de posição usado na planilha XLSX gerada pelo sistema interno. Exemplos de correspondência:

| `nome_posicao` (SAA29) | `posicao_xlsx` (Planilha) |
|------------------------|---------------------------|
| CMFD1 | MF1 |
| CMFD2 | MF2 |
| CMFD3 | MF3 |
| CMFD4 | MF4 |
| MDP1 | MD1 |
| MDP2 | MD2 |
| VUHF1 | V1 |
| VUHF2 | V2 |

> **Nota:** Os valores exatos de correspondência devem ser levantados comparando a planilha XLSX com os slots cadastrados no seed.

#### 1.3 Migração Alembic

Criar uma nova migração para adicionar a coluna:

```bash
alembic revision --autogenerate -m "add_posicao_xlsx_to_slots_inventario"
alembic upgrade head
```

#### 1.4 Atualizar Seed de Equipamentos

**Arquivo:** `scripts/seed/seed_equipamentos.py`

Adicionar o campo `pos` ao dicionário `EQUIPAMENTOS_FICHA`:

```python
# Exemplo de como ficaria:
{"slot": "CMFD1", "equipamento": "CMFD", "pn": "MB387B-01", "loc": "1P", "pos": "MF1"},
{"slot": "CMFD2", "equipamento": "CMFD", "pn": "MB387B-01", "loc": "1P", "pos": "MF2"},
{"slot": "CMFD3", "equipamento": "CMFD", "pn": "MB387B-01", "loc": "2P", "pos": "MF3"},
{"slot": "CMFD4", "equipamento": "CMFD", "pn": "MB387B-01", "loc": "2P", "pos": "MF4"},
```

E na função `run()`, ao criar o `SlotInventario`, passar `posicao_xlsx=data.get("pos")`.

---

### Fase 2: Serviço de Processamento XLSX

**Arquivo:** `app/modules/equipamentos/xlsx_service.py` (NOVO)

Criar um serviço isolado que:

1. Recebe o conteúdo do arquivo XLSX (bytes) e o nome do arquivo
2. Extrai a matrícula do nome do arquivo
3. Busca a aeronave correspondente no banco
4. Lê todas as linhas do XLSX, extraindo coluna B (PN), coluna E (Posição) e coluna F (SN)
5. Para cada linha com PN válido, busca o `ModeloEquipamento` correspondente
6. Se encontrar, busca o `SlotInventario` usando `posicao_xlsx` para desambiguar
7. Chama `ajustar_inventario_item()` para cada par (slot, SN)
8. Retorna um relatório com: total de linhas, PNs encontrados, PNs ignorados, erros

```python
"""
app/modules/equipamentos/xlsx_service.py
Serviço de processamento de inventário via arquivo XLSX.
"""
import os
import uuid
from io import BytesIO
from dataclasses import dataclass, field

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos.models import ModeloEquipamento, SlotInventario
from app.modules.equipamentos.schemas import AjusteInventarioCreate
from app.modules.equipamentos import service as equip_service


@dataclass
class XlsxResultado:
    """Relatório de processamento do XLSX."""
    matricula: str = ""
    total_linhas: int = 0
    pns_encontrados: int = 0
    pns_ignorados: int = 0
    itens_atualizados: int = 0
    erros: list[str] = field(default_factory=list)
    detalhes: list[str] = field(default_factory=list)


async def processar_xlsx_inventario(
    db: AsyncSession,
    file_content: bytes,
    filename: str,
    usuario_id: uuid.UUID,
) -> XlsxResultado:
    """
    Processa um arquivo XLSX de inventário e atualiza os seriais da aeronave.
    
    Parâmetros:
        db: Sessão assíncrona do banco de dados
        file_content: Conteúdo binário do arquivo XLSX
        filename: Nome do arquivo (ex: "5906.xlsx")
        usuario_id: ID do usuário que está realizando a operação
    """
    resultado = XlsxResultado()

    # 1. Extrair matrícula do nome do arquivo
    nome_base = os.path.splitext(filename)[0].strip()
    resultado.matricula = nome_base

    # 2. Buscar aeronave pelo campo matrícula
    res_acft = await db.execute(
        select(Aeronave).where(Aeronave.matricula == nome_base)
    )
    aeronave = res_acft.scalar_one_or_none()
    if not aeronave:
        resultado.erros.append(
            f"Aeronave com matrícula '{nome_base}' não encontrada no sistema."
        )
        return resultado

    # 3. Carregar catálogo de PNs do banco (mapa PN → modelo)
    res_modelos = await db.execute(select(ModeloEquipamento))
    modelos_map: dict[str, ModeloEquipamento] = {
        m.part_number.upper(): m for m in res_modelos.scalars().all()
    }

    # 4. Carregar slots e indexar por modelo_id E por posicao_xlsx
    res_slots = await db.execute(select(SlotInventario))
    slots_por_modelo: dict[uuid.UUID, list[SlotInventario]] = {}
    slots_por_posicao: dict[str, SlotInventario] = {}  # posicao_xlsx → slot
    for slot in res_slots.scalars().all():
        slots_por_modelo.setdefault(slot.modelo_id, []).append(slot)
        if slot.posicao_xlsx:
            slots_por_posicao[slot.posicao_xlsx.upper()] = slot

    # 5. Ler o XLSX
    wb = load_workbook(filename=BytesIO(file_content), read_only=True)
    ws = wb.active  # Usa a primeira aba

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        resultado.total_linhas += 1

        # Col B (idx 1) = PN, Col E (idx 4) = Posição, Col F (idx 5) = SN Real
        pn_raw = str(row[1]).strip().upper() if row[1] else None
        pos_raw = str(row[4]).strip().upper() if row[4] else None
        sn_raw = str(row[5]).strip() if row[5] else None

        if not pn_raw or not sn_raw or sn_raw.lower() in ("none", "", "-"):
            continue

        # 6. Buscar modelo pelo PN
        modelo = modelos_map.get(pn_raw)
        if not modelo:
            resultado.pns_ignorados += 1
            continue

        resultado.pns_encontrados += 1

        # 7. Desambiguar slot usando posicao_xlsx (coluna E)
        slot_alvo = None
        if pos_raw and pos_raw in slots_por_posicao:
            # Match direto pela posição da planilha
            slot_alvo = slots_por_posicao[pos_raw]
        else:
            # Fallback: se o PN tem um único slot, usar direto
            slots_do_pn = slots_por_modelo.get(modelo.id, [])
            if len(slots_do_pn) == 1:
                slot_alvo = slots_do_pn[0]
            elif len(slots_do_pn) == 0:
                resultado.erros.append(
                    f"Linha {row_idx}: PN '{pn_raw}' sem slot configurado."
                )
                continue
            else:
                resultado.erros.append(
                    f"Linha {row_idx}: PN '{pn_raw}' possui {len(slots_do_pn)} slots, "
                    f"mas posição '{pos_raw}' não tem correspondência em posicao_xlsx."
                )
                continue

        # 8. Ajustar inventário no slot identificado
        try:
            dados = AjusteInventarioCreate(
                aeronave_id=aeronave.id,
                slot_id=slot_alvo.id,
                numero_serie_real=sn_raw,
                forcar_transferencia=False,
                usuario_id=usuario_id,
            )
            resp = await equip_service.ajustar_inventario_item(db, dados)
            if resp.sucesso:
                resultado.itens_atualizados += 1
                resultado.detalhes.append(
                    f"✅ {slot_alvo.nome_posicao} ({pn_raw}) → SN: {sn_raw}"
                )
            else:
                resultado.detalhes.append(
                    f"⚠️ {slot_alvo.nome_posicao}: {resp.mensagem}"
                )
        except Exception as e:
            resultado.erros.append(
                f"Linha {row_idx}, Slot {slot_alvo.nome_posicao}: {str(e)}"
            )

    wb.close()
    return resultado
```

**Pontos de atenção para o implementador:**
- A coluna de cabeçalho é ignorada (`min_row=2`).
- O serviço usa **duas estratégias** de localização de slot: primeiro tenta `posicao_xlsx` (match direto), e se não encontrar, faz fallback para slots com PN único.

---

### Fase 3: Endpoint da API

**Arquivo:** `app/modules/equipamentos/router.py`

Adicionar um novo endpoint que recebe o upload do arquivo:

```python
from fastapi import UploadFile, File

@router.post(
    "/inventario/upload-xlsx",
    summary="Carregar inventário via XLSX",
)
async def upload_inventario_xlsx(
    file: UploadFile = File(...),
    db: DBSession,
    current_user: EncarregadoOuAdmin,
):
    """
    Recebe um arquivo XLSX nomeado como MATRICULA.xlsx,
    cruza os PNs com o catálogo e atualiza os seriais da aeronave.
    """
    # Validar extensão
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo deve ser do tipo .xlsx"
        )

    # Validar tamanho (máximo 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo excede o tamanho máximo de 5MB."
        )

    from app.modules.equipamentos.xlsx_service import processar_xlsx_inventario
    resultado = await processar_xlsx_inventario(
        db, content, file.filename, current_user.id
    )

    return {
        "sucesso": len(resultado.erros) == 0,
        "matricula": resultado.matricula,
        "total_linhas": resultado.total_linhas,
        "pns_encontrados": resultado.pns_encontrados,
        "pns_ignorados": resultado.pns_ignorados,
        "itens_atualizados": resultado.itens_atualizados,
        "erros": resultado.erros,
        "detalhes": resultado.detalhes,
    }
```

**Import necessário no topo do `router.py`:**
```python
from fastapi import UploadFile, File
```

---

### Fase 4: Frontend — Botão e Modal

**Arquivo:** `app/web/templates/configuracoes.html`

#### 4.1 Adicionar botão no card "Equipamentos e PNs"

Localizar o card (linha ~62, dentro do `<div>` com `display: flex; gap: 0.5rem`) e adicionar após o botão "Gerenciar Catálogo":

```html
<button class="btn btn-equipamento" id="btn-upload-xlsx" style="width: 100%;">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        style="vertical-align: middle; margin-right: 5px;">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
    Carregamento Inventário (XLSX)
</button>
```

#### 4.2 Adicionar modal de upload

Inserir antes do `{% endblock %}` de content (antes da linha 895):

```html
<!-- Modal Upload XLSX Inventário -->
<div id="modal-upload-xlsx"
    style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6);
           backdrop-filter: blur(4px); z-index: 1000; align-items: center;
           justify-content: center;">
    <div class="card glass-panel" style="width: 100%; max-width: 550px; margin: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: center;
                    border-bottom: 1px solid var(--border-color); padding-bottom: 1rem;
                    margin-bottom: 1.5rem;">
            <h3 style="margin: 0; font-size: 1.25rem;">Carregamento de Inventário (XLSX)</h3>
            <button class="btn-icon" type="button" id="btn-close-modal-xlsx">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2">
                    <path d="M18 6L6 18M6 6l12 12" />
                </svg>
            </button>
        </div>

        <p style="color: var(--text-secondary); font-size: 0.9rem; margin: 0 0 1.5rem 0;">
            Selecione um arquivo <strong>MATRICULA.xlsx</strong> (ex: 5906.xlsx).
            O sistema identificará a aeronave pelo nome e atualizará os seriais (S/N)
            dos equipamentos compatíveis com o catálogo cadastrado.
        </p>

        <form id="formUploadXlsx">
            <div class="form-group">
                <label class="form-label">Arquivo XLSX *</label>
                <input type="file" id="xlsxFileInput" class="form-input"
                       accept=".xlsx" required>
            </div>

            <!-- Área de resultado (oculta até o processamento) -->
            <div id="xlsx-resultado" style="display: none; margin-top: 1rem;
                 padding: 1rem; border-radius: var(--radius-md);
                 border: 1px solid var(--border-color); max-height: 300px;
                 overflow-y: auto; font-size: 0.85rem;">
            </div>

            <div style="display: flex; gap: 1rem; justify-content: flex-end;
                        margin-top: 2rem;">
                <button type="button" class="btn btn-outline"
                        id="btn-cancel-modal-xlsx">Cancelar</button>
                <button type="submit" class="btn btn-equipamento"
                        id="btnEnviarXlsx">Enviar e Processar</button>
            </div>
        </form>
    </div>
</div>
```

---

### Fase 5: Frontend — JavaScript

**Arquivo:** `app/web/static/js/configuracoes.js`

Adicionar ao final do arquivo a lógica do modal e do upload:

```javascript
// ============================================================
// Upload XLSX Inventário
// ============================================================
(function () {
    const btnUpload = document.getElementById('btn-upload-xlsx');
    const modal = document.getElementById('modal-upload-xlsx');
    const btnClose = document.getElementById('btn-close-modal-xlsx');
    const btnCancel = document.getElementById('btn-cancel-modal-xlsx');
    const form = document.getElementById('formUploadXlsx');
    const fileInput = document.getElementById('xlsxFileInput');
    const resultadoDiv = document.getElementById('xlsx-resultado');
    const btnEnviar = document.getElementById('btnEnviarXlsx');

    if (!btnUpload || !modal) return;

    function abrirModal() {
        modal.style.display = 'flex';
        form.reset();
        resultadoDiv.style.display = 'none';
        resultadoDiv.innerHTML = '';
        btnEnviar.disabled = false;
        btnEnviar.textContent = 'Enviar e Processar';
    }

    function fecharModal() {
        modal.style.display = 'none';
    }

    btnUpload.addEventListener('click', abrirModal);
    btnClose.addEventListener('click', fecharModal);
    btnCancel.addEventListener('click', fecharModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) fecharModal();
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const file = fileInput.files[0];
        if (!file) return;

        // Validar extensão
        if (!file.name.toLowerCase().endsWith('.xlsx')) {
            alert('Selecione um arquivo .xlsx válido.');
            return;
        }

        btnEnviar.disabled = true;
        btnEnviar.textContent = 'Processando...';
        resultadoDiv.style.display = 'block';
        resultadoDiv.innerHTML = '<p>⏳ Enviando e processando arquivo...</p>';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const token = localStorage.getItem('access_token');
            const resp = await fetch('/equipamentos/inventario/upload-xlsx', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData,
            });

            const data = await resp.json();

            if (!resp.ok) {
                resultadoDiv.innerHTML =
                    `<p style="color: var(--status-danger);">
                        ❌ Erro: ${data.detail || 'Falha no processamento.'}
                    </p>`;
                return;
            }

            // Montar relatório visual
            let html = `
                <h4 style="margin: 0 0 0.75rem;">Relatório — Aeronave ${data.matricula}</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 1rem;">
                    <div><strong>Linhas lidas:</strong> ${data.total_linhas}</div>
                    <div><strong>PNs encontrados:</strong> ${data.pns_encontrados}</div>
                    <div><strong>PNs ignorados:</strong> ${data.pns_ignorados}</div>
                    <div><strong>Itens atualizados:</strong> ${data.itens_atualizados}</div>
                </div>
            `;

            if (data.erros && data.erros.length > 0) {
                html += `<div style="color: var(--status-danger); margin-bottom: 0.5rem;">
                    <strong>Erros:</strong><br>
                    ${data.erros.map(e => `• ${e}`).join('<br>')}
                </div>`;
            }

            if (data.detalhes && data.detalhes.length > 0) {
                html += `<div style="margin-top: 0.5rem;">
                    <strong>Detalhes:</strong><br>
                    ${data.detalhes.map(d => `${d}`).join('<br>')}
                </div>`;
            }

            resultadoDiv.innerHTML = html;

        } catch (err) {
            resultadoDiv.innerHTML =
                `<p style="color: var(--status-danger);">
                    ❌ Erro de conexão: ${err.message}
                </p>`;
        } finally {
            btnEnviar.disabled = false;
            btnEnviar.textContent = 'Enviar e Processar';
        }
    });
})();
```

---

## Resumo de Arquivos

| Ação | Arquivo | Descrição |
|------|---------|-----------|
| ✏️ Editar | `requirements.txt` | Adicionar `openpyxl>=3.1.0` |
| ✏️ Editar | `app/modules/equipamentos/models.py` | Nova coluna `posicao_xlsx` em `SlotInventario` |
| 🆕 Criar | `migrations/versions/...add_posicao_xlsx...` | Migração Alembic |
| ✏️ Editar | `scripts/seed/seed_equipamentos.py` | Adicionar campo `pos` e popular `posicao_xlsx` |
| 🆕 Criar | `app/modules/equipamentos/xlsx_service.py` | Serviço de leitura e processamento do XLSX |
| ✏️ Editar | `app/modules/equipamentos/router.py` | Novo endpoint `POST /inventario/upload-xlsx` |
| ✏️ Editar | `app/web/templates/configuracoes.html` | Botão + Modal de upload |
| ✏️ Editar | `app/web/static/js/configuracoes.js` | Lógica JS do modal e fetch |

---

## Pontos de Atenção

1. **Desambiguação de Slots via `posicao_xlsx`**: A coluna E (Posição) do XLSX é usada para identificar qual slot específico recebe o SN quando um PN possui múltiplos slots (ex: CMFD → MF1, MF2, MF3, MF4). A nova coluna `posicao_xlsx` na tabela `slots_inventario` armazena essa correspondência. Se a posição do XLSX não bater com nenhum `posicao_xlsx` cadastrado, o serviço tenta fallback por `modelo_id` (slot único para o PN).

2. **Levantamento de Correspondências**: É necessário mapear todas as posições da planilha (ex: MF1, MD1, V1, FT, CAT) para os `nome_posicao` do SAA29 (ex: CMFD1, MDP1, VUHF1). Isso pode ser feito comparando os arquivos da pasta `docs/inventario/` com os slots cadastrados em `seed_equipamentos.py`.

3. **Permissão**: O endpoint usa `EncarregadoOuAdmin`, compatível com o padrão do módulo de ajuste de inventário.

4. **Backup R2**: O sistema já possui backup automático orientado a eventos (`after_commit`). As alterações feitas pelo upload serão automaticamente persistidas no R2.

5. **Testes**: Criar testes em `tests/test_xlsx_upload.py` usando arquivos de exemplo da pasta `docs/inventario/`.
