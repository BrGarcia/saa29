# Implementação de Interface Mobile Simplificada (SAA29) — Modo Execução na Linha de Voo

Este documento especifica a versão mobile simplificada do SAA29 (`/m/`), focada estritamente na **execução direta e conclusão rápida de tarefas** por mantenedores na linha de voo e hangar.

---

## 🎯 1. Conceito Operacional (Foco em Execução)

O fluxo de trabalho foi desenhado para **simplicidade absoluta e zero burocracia**:

1. **Encarregados & Gestores (Desktop):** Cadastram previamente as panes, ordens de trabalho e pacotes de inspeção no sistema.
2. **Inspetores (Desktop/Tablet):** Geram e abrem as inspeções e checklists de delineamento.
3. **Mantenedores / Mecânicos (Mobile na Pista):** Apenas abrem o aplicativo no smartphone, visualizam as tarefas pendentes da aeronave atribuída, executam a ação e **marcam como concluído em 1 toque**.

---

## ⚡ 2. Princípios da Interface Mobile (Mantenedor)

1. **Sem Formulários de Cadastro Complexos:** O mecânico não precisa cadastrar panes nem criar checklists no celular; ele consome o que já foi lançado pelo encarregado/inspetor.
2. **Conclusão em 1 Toque:** Cada tarefa ou pane possui um botão de alta visibilidade `[ EXECUTADO / CONCLUIR ]`.
3. **Anexo Opcional de Evidência:** Opção simples de tirar 1 foto (ex: componente trocado ou manômetro) ao concluir a tarefa.
4. **Assinatura por Trigrama da Sessão:** O sistema preenche automaticamente o militar logado como executor da tarefa (`executado_por`).
5. **Zero Confirmações Redundantes:** Clicou em concluir -> Tarefa salva instantaneamente. Toast com botão "Desfazer" de 3 segundos para enganos.
6. **Interface Luva & Sol-Friendly:** Botões grandes (`>= 56px`), fontes de alto contraste e navegação simplificada.

---

## 📱 3. Fluxo de Uso na Linha de Voo (Passo a Passo)

```
┌──────────────────────────────────────────────────────────┐
┌ 1. TELA INICIAL: SELEÇÃO DE ANV                          ┐
│  [ FAB 5701 - 2 tarefas pendentes ]  ──► (1 Toque)      │
│  [ FAB 5702 - 0 tarefas pendentes ]                      │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
┌ 2. LISTA DE TRABALHO DA ANV (FAB 5701)                   ┐
│                                                          │
│  • PANE ATA 24: Falha no CMFD 1                          │
│    [ 🟢 CONCLUIR PANE ]    [ 📷 FOTO ]                    │
│                                                          │
│  • INSPEÇÃO 100H: Item 15 (Check EGIR/STHD)              │
│    [ 🟢 VISTO / OK ]       [ 🟡 PNE ]                      │
└──────────────────────────────────────────────────────────┘
```

### Passo 1: Seleção da Aeronave (1 Toque)
Ao acessar `/m/`, o mantenedor vê os cards das aeronaves ativas na pista. Cada card destaca quantas tarefas/panes estão pendentes naquela ANV.

### Passo 2: Lista de Execução da ANV
Ao clicar na aeronave (ex: `FAB 5701`), o app exibe uma lista limpa contendo:
- **Panes Abertas** que aguardam manutenção.
- **Tarefas de Checklist** pendentes de execução.

### Passo 3: Conclusão Instantânea
- **Para Panes:** O mecânico clica em `[ CONCLUIR PANE ]`. Opcionalmente tira uma foto do componente ajustado/trocado e confirma. A pane muda o status para `RESOLVIDA` e vincula o trigrama do mantenedor.
- **Para Checklists:** O mecânico clica em `[ VISTO / OK ]`. O item é marcado como concluído e desaparece da lista pendente.

---

## 🛠️ 4. Escopo Técnico da Versão Mobile (v1)

### Incluído na V1:
- [x] Rota mobile `/m/` otimizada para smartphones (Jinja2 + CSS ultra-leve).
- [x] PWA (Progressive Web App) para adicionar à tela inicial do celular.
- [x] Card de Frota com contador de pendências por ANV.
- [x] Lista unificada de Panes & Checklists pendentes por aeronave.
- [x] Ação de conclusão em 1 toque com captura direta de foto pela câmera.
- [x] Auditoria automática registrando o trigrama e timestamp do executor.

### Excluído da V1 (Mantendo a Simplicidade):
- ❌ Reconhecimento / ditado por voz.
- ❌ Formulários extensos de cadastro de panes no celular.
- ❌ Modais e diálogos de confirmação múltiplos.

---

## 📊 5. Cronograma de Implementação Simplificado

| Fase | Entrega | Foco |
| :--- | :--- | :--- |
| **Fase 1** | Layout Base `/m/` & Dashboard de Frota com Pendências | Acesso e seleção em 1 toque |
| **Fase 2** | Lista de Execução de Panes & Conclusão com Foto | Encerramento rápido de panes |
| **Fase 3** | Lista de Execução de Checklists & Vistos em 1 Toque | Baixa rápida de inspeções |
