# Plano de Implementação Técnica — SAA29 Mobile (`/m/`)

**Módulo:** Interface Mobile para Linha de Voo  
**Status:** Planejamento  
**Documento Relacionado:** `docs/backlog/Melhorias Futuras/IMPLEMENTACAO_MOBILE.MD`  
**Conformidade:** Metodologia CSP (`docs/methodology/CSP.md`), Arquitetura FastAPI + Jinja2 + Vanilla JS  

---

## 🎯 1. Objetivo e Diretrizes Principais

Implementar uma interface mobile otimizada para smartphones (`/m/`), focada na **linha de voo e hangar**, permitindo que o mantenedor visualize e conclua tarefas de manutenção/checklists pré-lançados com **zero fricção e em 1 toque**.

### Diretrizes Inegociáveis:
1. **Conformidade Absoluta com a CSP (`docs/methodology/CSP.md`)**: Proibição total de scripts ou eventos inline (`onclick`, `onchange`, `<script>` com código no HTML). Todos os eventos são vinculados em arquivos `.js` externos.
2. **Arquitetura Leve (Zero Frameworks Pesados)**: Reaproveitamento das APIs FastAPI existentes com Jinja2 + Vanilla JS + CSS Tokens.
3. **PWA Instalável**: Suporte a *Progressive Web App* para instalação na tela inicial do dispositivo.
4. **Respeito às Permissões RBAC**: Mantenedor conclui tarefas/panes; Encarregado e Inspetor gerenciam a abertura de inspecões e panes.

---

## 🏗️ 2. Arquitetura da Solução Mobile

```
app/
├── web/
│   ├── pages/
│   │   └── mobile_router.py         # Rotas HTML da interface mobile (/m/, /m/aeronave/{id})
│   ├── templates/
│   │   └── mobile/
│   │       ├── base_mobile.html     # Layout base mobile (CSP compliant, PWA meta tags)
│   │       ├── frota.html           # Tela 1: Cards das aeronaves com pendências
│   │       └── tarefas_aeronave.html # Tela 2: Lista de tarefas/panes com botão [CONCLUIR]
│   └── static/
│       ├── css/
│       │   └── mobile.css           # Design system mobile (Touch targets >= 56px, Dark Mode High Contrast)
│       ├── js/
│       │   └── mobile/
│       │       ├── app_mobile.js    # Lógica global mobile e registro do Service Worker
│       │       └── tarefas_mobile.js # Lógica de conclusão de tarefas em 1 toque e foto
│       ├── manifest.json            # PWA Web App Manifest
│       └── sw.js                    # Service Worker básico para PWA e cache de ativos estáticos
```

---

## 🔒 3. Conformidade Estrita com Content Security Policy (CSP)

A implementação mobile deve respeitar rigorosamente a política `script-src 'self'`:

### Regra 1: Zero Eventos Inline no HTML
Nenhum template mobile conterá `onclick`, `onchange`, `onsubmit` ou `<script>` inline.

**❌ Errado:**
```html
<button onclick="concluirTarefa('{{ tarefa.id }}')">Concluir</button>
```

**✅ Correto (Padrão SAA29):**
```html
<button class="btn-concluir-tarefa" data-tarefa-id="{{ tarefa.id }}" data-tipo="PANE">
    🟢 CONCLUIR PANE
</button>
```
```javascript
// app/web/static/js/mobile/tarefas_mobile.js
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.btn-concluir-tarefa').forEach(btn => {
        btn.addEventListener('click', handleConcluirTarefa);
    });
});
```

### Regra 2: Passagem de Dados via Atributos `data-*` e JSON Escapado
Se houver contexto complexo da aeronave ou do usuário a ser lido no JavaScript, usar atributos `data-*` ou bloco JSON seguro:

```html
<div id="mobile-context"
     data-aeronave-id="{{ aeronave.id }}"
     data-usuario-trigrama="{{ current_user.trigrama }}"
     style="display: none;">
</div>
```

---

## 📅 4. Detalhamento Focado por Fases de Desenvolvimento

### Fase 1: Infraestrutura Mobile & PWA
- [ ] Criar `app/web/pages/mobile_router.py` e registrar no `app/bootstrap/create_app.py`.
- [ ] Criar `app/web/templates/mobile/base_mobile.html` com suporte a viewport mobile e meta tags PWA.
- [ ] Criar `app/web/static/css/mobile.css` com variáveis de cores do SAA29, dark mode de alto contraste e touch targets de `56px`.
- [ ] Criar `app/web/static/manifest.json` e `app/web/static/sw.js` para suporte a PWA.

### Fase 2: Tela 1 — Dashboard de Frota Mobile (`/m/`)
- [ ] Implementar rota `GET /m/` que busca as aeronaves ativas e calcula a quantidade de panes abertas e tarefas de inspeção pendentes por ANV.
- [ ] Renderizar `app/web/templates/mobile/frota.html` com cards de visualização direta e indicação de pendências.
- [ ] Adicionar navegação em 1 toque para abrir as tarefas da aeronave (`/m/aeronave/{id}`).

### Fase 3: Tela 2 — Lista de Tarefas da ANV & Conclusão (`/m/aeronave/{id}`)
- [ ] Implementar rota `GET /m/aeronave/{id}` listando as **Panes Abertas** (da tabela `panes`) e as **Tarefas de Inspeção Pendentes** (da tabela `inspecao_tarefas`).
- [ ] Renderizar `app/web/templates/mobile/tarefas_aeronave.html` com botões grandes `[ CONCLUIR PANE ]` e `[ VISTO / OK ]`.
- [ ] Implementar `app/web/static/js/mobile/tarefas_mobile.js`:
  - Envio de requisição `PATCH /panes/{id}/concluir` ou `PATCH /inspecoes/tarefas/{id}`.
  - Suporte ao anexo de imagem opcional utilizando `<input type="file" accept="image/*" capture="environment">`.
  - Exibição de Toast flutuante com botão "Desfazer" de 3 segundos.

### Fase 4: Testes Automatizados & Segurança
- [ ] Criar suíte de testes em `tests/unit/test_mobile_router.py` validando rotas mobile, autenticação e retorno 200.
- [ ] Executar suíte de testes CSRF (`pytest tests/security/test_csrf.py`) garantindo conformidade.
- [ ] Auditar templates mobile garantindo zero violação de CSP.

---

## ✅ 5. Critérios de Aceite

1. **Desempenho e Praticidade**:
   - O aplicativo carrega a lista de tarefas da aeronave em menos de 1 segundo.
   - A baixa/conclusão de uma tarefa requer apenas 1 toque na tela.
2. **Compatibilidade Mobile**:
   - PWA instalável no Android (Chrome) e iOS (Safari).
   - Layout responsivo adaptado para telas de 360px a 430px de largura.
3. **Conformidade de Segurança & CSP**:
   - 0% de scripts ou atributos de eventos inline.
   - Rotas protegidas por autenticação via cookie JWT/Session.
   - Passagem de testes de segurança automatizados (`pytest`).
