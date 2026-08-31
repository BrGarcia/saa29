# Especificação de Funcionalidade: Agrupamento de Ícones da Barra Superior por Perfil (Role)

> **Status:** 🟢 Especificado / Pronto para Implementação  
> **Data:** 31/08/2026  
> **Módulo:** Interface Global / Top Header (`app/web/templates/base.html`, `index.css`)  
> **Público-Alvo:** Todos os perfis operacionais (`MECÂNICO / MANTENEDOR`, `ENCARREGADO`, `INSPETOR`, `ADMINISTRADOR`)  
> **Protótipo Interativo:** [`docs/BACKLOG/mockups/mockup_barra_superior_roles.html`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/docs/BACKLOG/mockups/mockup_barra_superior_roles.html) e [`docs/BACKLOG/mockups/index.html`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/docs/BACKLOG/mockups/index.html)

---

## 1. Motivação e Usabilidade

Atualmente, a barra superior de navegação (`#admin-nav` em `base.html`) renderiza uma sequência plana contínua de até 10 ícones sem distinção visual entre as diferentes responsabilidades e rotinas do esquadrão.

Com o crescimento do sistema (incorporação de Pedidos, Publicações, Calendário e Dashboard), a varredura visual tornou-se dispersa. Organizar os atalhos agrupando-os pela **rotina operacional de cada Perfil (Role)** cria uma hierarquia mental intuitiva, acelera o acesso às telas do dia a dia e reduz erros de navegação.

---

## 2. Matriz de Agrupamento por Perfil (Role)

A ordem visual na barra superior, da **esquerda para a direita** (ponto de vista do usuário), é dividida em 4 grupos lógicos:

```
[ LOGO SAA29 | Título da Página ] ──── [ GRUPO 1: MECÂNICO ] [ GRUPO 2: ENCARREGADO ] [ GRUPO 3: INSPETOR ] [ GRUPO 4: CONFIGURAÇÕES ]
```

| Grupo | Perfil Foco | Módulos & Destinos (Ordem E→D) | Ícones SVG & URLs | Finalidade Operacional |
|---|---|---|---|---|
| **1** | **Mecânico / Mantenedor** | 1. **Panes**<br>2. **Inspeções**<br>3. **Inventário** | • `/panes` (Alerta/Triângulo)<br>• `/inspecoes` (Avião/Prancheta)<br>• `/inventario` (Lista/Checklist) | Ações diretas de chão de fábrica e linha de voo (registro de discrepâncias, execução de inspeções e verificação de peças/slots). |
| **2** | **Encarregado** | 1. **Dashboard**<br>2. **Ciência de Alterações**<br>3. **Central de Pedidos**<br>4. **Calendário** | • `/dashboard` (Grid 4-quadrantes)<br>• `/encarregado` (Escudo/Check)<br>• `/pedidos` (Caixa 3D)<br>• `/calendario` (Calendário/Datas) | Gestão tática do esquadrão, acompanhamento de disponibilidade, despacho de pedidos e planejamento da escala/efetivo. |
| **3** | **Inspetor** | 1. **Vencimentos**<br>2. **Frota**<br>3. **Publicações** | • `/vencimentos` (Relógio/Tempo)<br>• `/frota` (Hangar/Frota)<br>• `/publicacoes` (Livro Aberto) | Auditoria técnica, controle de calibrações/TBO, liberação de aeronaves e consulta aos manuais técnicos oficiais. |
| **4** | **Configurações & Sistema** | 1. **Alternar Tema**<br>2. **Configurações**<br>3. **Sair (Logoff)** | • `#theme-toggle` (Sol/Lua)<br>• `/configuracoes` (Engrenagem)<br>• `#logout-btn` (Porta/Saída) | Preferências da interface, parametrizações globais do sistema (exclusivo Admin) e encerramento de sessão. |

---

## 3. Especificação Visual e CSS

### 3.1 Estrutura em Grupos Cromáticos (`.nav-group` sem rótulos de texto)
Em vez de um único contêiner com todos os links em linha, o `#admin-nav` passa a conter contêineres `.nav-group` estilizados de forma puramente cromática/visual (sem labels textuais na barra, preservando a limpeza da interface e espaço horizontal). Cada grupo possui uma sutil tonalidade de borda e background correspondente ao papel, além de divisores verticais entre eles.

```html
<!-- Exemplo da Estrutura Proposta no base.html -->
<nav id="admin-nav" class="top-nav-roles">
    <!-- Grupo 1: Mecânico -->
    <div class="nav-group nav-group-mecanico" data-group="mecanico" title="Rotina do Mecânico">
        <a href="/panes" class="btn-icon" title="Panes (Mecânico)" aria-label="Panes">...</a>
        <a href="/inspecoes" class="btn-icon" title="Inspeções (Mecânico)" aria-label="Inspeções">...</a>
        <a href="/inventario" class="btn-icon" title="Inventário (Mecânico)" aria-label="Inventário">...</a>
    </div>

    <!-- Divisor -->
    <div class="nav-divider"></div>

    <!-- Grupo 2: Encarregado -->
    <div class="nav-group nav-group-encarregado" data-group="encarregado" title="Gestão do Encarregado">
        <a href="/dashboard" class="btn-icon" title="Dashboard (Encarregado)" aria-label="Dashboard">...</a>
        <a href="/encarregado" class="btn-icon" title="Ciência de Alterações (Encarregado)" aria-label="Ciência">...</a>
        <a href="/pedidos" class="btn-icon" title="Central de Pedidos (Encarregado)" aria-label="Pedidos">...</a>
        <a href="/calendario" class="btn-icon" title="Calendário (Encarregado)" aria-label="Calendário">...</a>
    </div>

    <!-- Divisor -->
    <div class="nav-divider"></div>

    <!-- Grupo 3: Inspetor -->
    <div class="nav-group nav-group-inspetor" data-group="inspetor" title="Auditoria do Inspetor">
        <a href="/vencimentos" class="btn-icon" title="Vencimentos (Inspetor)" aria-label="Vencimentos">...</a>
        <a href="/frota" class="btn-icon" title="Frota e Aeronaves (Inspetor)" aria-label="Frota">...</a>
        <a href="/publicacoes" class="btn-icon" title="Publicações Técnicas (Inspetor)" aria-label="Publicações">...</a>
    </div>
</nav>

<!-- Grupo 4: Sistema / Configurações -->
<div class="nav-group nav-group-system">
    <button id="theme-toggle" class="btn-icon" title="Alternar Tema">...</button>
    <a href="/configuracoes" id="settings-nav" class="btn-icon" title="Configurações">...</a>
    <button id="logout-btn" class="btn-icon" title="Sair do Sistema">...</button>
</div>
```

### 3.2 Tokens e Estilos CSS (`index.css`)
- `.top-nav-roles`: `display: flex; align-items: center; gap: 0.5rem;`
- `.nav-group`: `display: inline-flex; align-items: center; gap: 0.25rem; background: var(--bg-secondary); border: 1px solid var(--border-color); padding: 0.2rem 0.35rem; border-radius: var(--radius-md);`
- `.nav-divider`: `width: 1px; height: 20px; background: var(--border-color); margin: 0 0.15rem;`
- Suporte nativo a Tema Claro e Escuro sem quebras de contraste.

---

## 4. Plano de Implementação

1. **HTML:** Atualizar `app/web/templates/base.html` reordenando e envelopando os links em seus respectivos `.nav-group`.
2. **CSS:** Adicionar classes `.top-nav-roles`, `.nav-group` e `.nav-divider` em `app/web/static/css/index.css`.
3. **JS:** Garantir que o script de controle de permissões (`auth_check.js`) e realce de página ativa continuem funcionando sem alterações em seletores.
4. **Validação:** Verificar renderização em 1920px, 1366px, 1024px e telas móveis.
