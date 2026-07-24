# Plano de Implementação: Geração de PDF da Ordem de Inspeção (OS)

**Módulo:** Inspeções & Inventário  
**Status:** Planejado (Backlog)  
**Arquivo de Especificação:** `docs/backlog/imprimir_os_inspecao.md`

---

## 🎯 1. Objetivo e Escopo

Adicionar a funcionalidade de emissão e download automático de relatórios em formato **PDF (Formato A4 Retrato)** para Ordens de Inspeção. O relatório consolida em um único documento impresso todas as informações atualizadas da inspeção (checklist com tarefas, responsabilidades por trigrama e observações) e a matriz de inventário controlado da aeronave vinculada.

---

## 🏗️ 2. Arquitetura da Solução

### 2.1 Backend (FastAPI + ReportLab)
- **Biblioteca Backend:** Adição do pacote `reportlab` no `requirements.txt` para geração dinâmica e streaming de PDFs em memória (`io.BytesIO`).
- **Camada de Serviço (`app/modules/inspecoes/pdf_service.py`):**
  - Função `gerar_pdf_ordem_inspecao(db: AsyncSession, inspecao_id: UUID) -> bytes`
  - Utilização de `SimpleDocTemplate` do ReportLab com suporte a layout A4 retrato, margens padronizadas (1.5 cm) e controle de quebra de páginas (`PageBreak`).
  - Consulta assíncrona desacoplada que reúne:
    1. Dados cadastrais e status da inspeção.
    2. Checklist completo das tarefas com status, trigrama do responsável, data/hora da última alteração e observações.
    3. Itens do inventário instalado na aeronave que possuem controle de vencimento ativo (filtrando apenas itens monitorados).
- **Endpoint na API (`app/modules/inspecoes/router.py`):**
  - `GET /api/v1/inspecoes/{inspecao_id}/pdf`
  - Retorna `Response(content=pdf_bytes, media_type="application/pdf")` com header de download: `Content-Disposition: attachment; filename="OS_Inspecao_{matricula}_{data}.pdf"`.
  - Exige autenticação (`CurrentUser` / Cookie ou Bearer JWT).

### 2.2 Frontend (Jinja2 + Vanilla JS)
- **Página de Detalhes (`app/web/templates/inspecoes/inspecao_detalhe.html`):**
  - Adição do botão **"Imprimir PDF"** (com ícone de impressora/documento) na barra de ações/cabeçalho da inspeção.
- **Script de Interação (`app/web/static/js/inspecao_detalhe.js`):**
  - Event listener no botão de impressão para chamar a rota de PDF via `fetch` autenticado ou abrindo a URL com o token de autorização.
  - Início automático do download do arquivo sem recarregar a página ou alterar o estado da inspeção na tela.

---

## 📄 3. Estrutura e Layout do Documento PDF

```
┌──────────────────────────────────────────────────────────┐
│ CABEÇALHO OFICIAL FAB / SAA29                            │
│ Sistema de Gestão de Panes e Manutenção - Eletrônica A-29│
├──────────────────────────────────────────────────────────┤
│ BLOCO 1: IDENTIFICAÇÃO DA INSPEÇÃO                       │
│ • Aeronave: A-29 (FAB 5712)   • Status: EM_ANDAMENTO     │
│ • Tipo(s): 100 HORAS / ANUAL                             │
│ • Início: 20/07/2026          • DPE: 05/08/2026          │
│ • Responsável:                • Gerado em: 24/07/2026    │
├──────────────────────────────────────────────────────────┤
│ CHECKLIST DE TAREFAS                                     │
│ ┌─────┬────────────────┬──────────┬────────┬───────────┐ │
│ │ Item│ Tarefa         │ Status   │ Resp.  │ Atualiz.  │ │
│ ├─────┼────────────────┼──────────┼────────┼───────────┤ │
│ │ 01  │ Teste VHF-1    │ CONCLUIDO│ GRC    │ 21/07 14h │ │
│ │ 02  │ Inspeção HUD   │ PENDENTE │ ---    │ ---       │ │
│ └─────┴────────────────┴──────────┴────────┴───────────┘ │
│ (Continuação em páginas adicionais se necessário)        │
│ ──────────────────────────────────────────────────────── │
│ PAGE BREAK OBRIGATÓRIO PARA INVENTÁRIO                   │
├──────────────────────────────────────────────────────────┤
│ BLOCO 2: INVENTÁRIO CONTROLADO DA AERONAVE               │
│ ┌──────────┬──────┬─────────────┬─────┬─────┬──────────┐ │
│ │ Posição  │ Slot │ Equipamento │ PN  │ SN  │ Validade │ │
│ ├──────────┼──────┼─────────────┼─────┼─────┼──────────┤ │
│ │ PAINEL L │ MDP1 │ Computador  │ PN1 │ SN1 │ OK (28d) │ │
│ └──────────┴──────┴─────────────┴─────┴─────┴──────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## 🔒 4. Regras de Negócio e Restrições

1. **Somente-Leitura (Read-Only):** A geração do PDF é 100% passiva. Não altera o banco de dados, não modifica o status da inspeção e não grava logs de mutação.
2. **Qualquer Estado:** O PDF pode ser emitido em qualquer fase da inspeção (`ABERTA`, `EM_ANDAMENTO`, `CONCLUIDA`, `CANCELADA`).
3. **Filtro de Inventário Controlado:** No Bloco 2, incluir **exclusivamente** os equipamentos da aeronave que possuem regras de vencimento/calibração associadas (ocultando itens sem controle temporal).
4. **Resolução de Trigrama:** Exibir o trigrama do militar responsável pela conclusão ou execução de cada tarefa do checklist.
5. **Formatos e Margens:** Folha A4 em modo Retrato (Portrait), margens de 15mm, cores institucionais (Azul FAB `#1F497D`, Cinza `#F3F4F6`, Verde `#2ECC71`, Amarelo `#F1C40F`, Vermelho `#E74C3C`).

---

## 📋 5. Componentes a Modificar / Criar

### [NEW] `requirements.txt`
- Incluir dependência `reportlab>=4.0.0`.

### [NEW] `app/modules/inspecoes/pdf_service.py`
- Lógica de compilação de dados da inspeção + inventário controlado.
- Construção do documento PDF via ReportLab Platypus (`SimpleDocTemplate`, `Table`, `Paragraph`, `Spacer`, `PageBreak`).

### [MODIFY] `app/modules/inspecoes/router.py`
- Adicionar o endpoint `GET /{inspecao_id}/pdf` antes das rotas dinâmicas.

### [MODIFY] `app/web/templates/inspecoes/inspecao_detalhe.html`
- Adicionar botão visual `<button id="btn-imprimir-pdf" class="btn btn-secondary"> Imprimir (PDF)</button>`.

### [MODIFY] `app/web/static/js/inspecao_detalhe.js`
- Adicionar handler para o botão de impressão disparando o download síncrono/assíncrono da rota `/pdf`.

### [NEW] `tests/unit/test_inspecao_pdf.py`
- Testes unitários para validar geração de bytes do PDF e resposta do endpoint de API.

---

## ✅ 6. Critérios de Aceite

- [ ] Botão "Imprimir (PDF)" visível e acessível na tela de detalhes da inspeção.
- [ ] O clique dispara o download imediato de um arquivo `.pdf` sem recarregar a página.
- [ ] O arquivo PDF gerado abre corretamente em leitores de PDF standard sem erros de sintaxe.
- [ ] O layout A4 exibe o checklist de tarefas na primeira parte e quebra página para o inventário controlado.
- [ ] Exibe corretamente os trigramas dos executores e o status atualizado dos componentes.
- [ ] Todos os testes automatizados da suíte passam sem regressões.
