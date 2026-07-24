# Plano de Implementação: Geração de PDF da Ordem de Inspeção (OS)

**Módulo:** Inspeções & Inventário  
**Status:** Implementado  
**Arquivo de Especificação:** `docs/backlog/imprimir_os_inspecao.md`

---

## 🎯 1. Objetivo e Escopo

Adicionar a funcionalidade de emissão e download automático de relatórios em formato **PDF (Formato A4 Retrato)** para Ordens de Inspeção. O relatório consolida em um único documento impresso todas as informações da inspeção (identificação, checklist com tarefas com suporte a preenchimento manual e campo de assinatura/visto), vencimentos/calibrações controladas em fluxo contínuo e a matriz de inventário completo da aeronave em página dedicada.

---

## 🏗️ 2. Arquitetura da Solução

### 2.1 Backend (FastAPI + ReportLab)
- **Biblioteca Backend:** Adição do pacote `reportlab` no `requirements.txt` para geração dinâmica e streaming de PDFs em memória (`io.BytesIO`).
- **Camada de Serviço (`app/modules/inspecoes/pdf_service.py`):**
  - Função `gerar_pdf_ordem_inspecao(db: AsyncSession, inspecao_id: UUID) -> bytes`
  - Utilização de `SimpleDocTemplate` do ReportLab com suporte a layout A4 retrato, margens padronizadas (1.3 cm) e controle de quebra de páginas (`PageBreak`).
  - Blocos estruturados:
    1. **1. IDENTIFICAÇÃO DA INSPEÇÃO** (dados cadastrais, datas, status e responsável).
    2. **2. CHECKLIST DE TAREFAS DA INSPEÇÃO** (tabela com status, trigrama, data de conclusão, observações e coluna para visto/assinatura, formatado para permitir preenchimento impresso a caneta).
    3. **3. VENCIMENTOS E CALIBRAÇÕES CONTROLADAS** (itens monitorados temporalmente, em páginas corridas logo abaixo do checklist).
    4. **4. INVENTÁRIO COMPLETO DA AERONAVE** (matriz geral de aviônicos instalados, antecedida por `PageBreak` obrigatório).
- **Endpoint na API (`app/modules/inspecoes/router.py`):**
  - `GET /inspecoes/{inspecao_id}/pdf`
  - Retorna `Response(content=pdf_bytes, media_type="application/pdf")` com header de download: `Content-Disposition: attachment; filename="OS_Inspecao_{id}.pdf"`.
  - Exige autenticação (`CurrentUser` / Cookie ou Bearer JWT).

### 2.2 Frontend (Jinja2 + Vanilla JS)
- **Página de Detalhes (`app/web/templates/inspecoes/inspecao_detalhe.html`):**
  - Botão **"Imprimir (PDF)"** na barra de ações/cabeçalho da inspeção.
- **Script de Interação (`app/web/static/js/inspecao_detalhe.js`):**
  - Event listener no botão de impressão para efetuar o download direto da rota `/inspecoes/{id}/pdf`.

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
│ BLOCO 2: CHECKLIST DE TAREFAS DA INSPEÇÃO                │
│ ┌───┬──────────────┬──────────┬──────┬──────────┬───────┬──────┐│
│ │Item│Tarefa       │Status    │Resp. │Data Conc.│Obs    │Visto ││
│ ├───┼──────────────┼──────────┼──────┼──────────┼───────┼──────┤│
│ │01 │Teste VHF-1   │CONCLUIDA │ GRC  │21/07 14h │---    │______││
│ │02 │Inspeção HUD  │[ ]OK [ ]ANO│[    ]│__/__/____│_______│______││
│ └───┴──────────────┴──────────┴──────┴──────────┴───────┴──────┘│
├──────────────────────────────────────────────────────────┤
│ BLOCO 3: VENCIMENTOS E CALIBRAÇÕES CONTROLADAS (Páginas corridas)│
│ ┌──────────┬──────┬─────────────┬─────┬─────────────┬──────────┐│
│ │ Posição  │ Slot │ Equipamento │ PN  │ Controle    │ Validade ││
│ ├──────────┼──────┼─────────────┼─────┼─────────────┼──────────┤│
│ │ PAINEL L │ MDP1 │ Computador  │ PN1 │ ANUAL       │ OK (28d) ││
│ └──────────┴──────┴─────────────┴─────┴─────────────┴──────────┘│
│ ──────────────────────────────────────────────────────── │
│ PAGE BREAK OBRIGATÓRIO PARA O INVENTÁRIO COMPLETO        │
├──────────────────────────────────────────────────────────┤
│ BLOCO 4: INVENTÁRIO COMPLETO DA AERONAVE (Em Página Única)│
│ ┌──────────┬──────┬─────────────┬─────┬─────┬────────────┐│
│ │ Posição  │ Slot │ Equipamento │ PN  │ SN  │ Data Inst. ││
│ └──────────┴──────┴─────────────┴─────┴─────┴────────────┘│
└──────────────────────────────────────────────────────────┘
```

---

## 🔒 4. Regras de Negócio e Restrições

1. **Somente-Leitura (Read-Only):** A geração do PDF é 100% passiva. Não altera o banco de dados e não modifica o status da inspeção.
2. **Preenchimento Manual:** Tarefas pendentes no checklist são renderizadas com campos visuais `[  ] OK  [  ] ANO`, datas e linhas guia para o mantenedor anota a caneta no papel.
3. **Páginas Corridas (Blocos 1 a 3):** As 3 primeiras seções possuem fluxo contínuo de páginas.
4. **Inventário em Nova Página (Bloco 4):** O Bloco 4 inicia obrigatoriamente após um `PageBreak`.

---

## ✅ 5. Critérios de Aceite

- [x] Botão "Imprimir (PDF)" visível e funcional na tela de detalhes da inspeção.
- [x] Bloco 3 (Vencimentos e Calibrações) posicionado em fluxo contínuo logo após o Bloco 2 (Checklist).
- [x] Bloco 4 (Inventário Completo) iniciado em página dedicada.
- [x] Checklist de tarefas contém coluna de visto/assinatura e formatação para preenchimento manual de itens pendentes.
- [x] Suíte de testes automatizados passando 100%.
