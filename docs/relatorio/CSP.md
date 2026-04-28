# Guia Definitivo: Content Security Policy (CSP) no Projeto SAA29

## 1. O Que Está Acontecendo?
A Política de Segurança de Conteúdo (CSP) é uma camada de segurança implementada no backend (via cabeçalhos HTTP no FastAPI) que diz ao navegador do usuário **exatamente o que ele tem permissão para executar ou carregar**.

Recentemente, removemos a permissão `'unsafe-inline'` da diretiva `script-src` para proteger o SAA29 contra **Cross-Site Scripting (XSS)**. O XSS ocorre quando um atacante consegue injetar um código malicioso no sistema (por exemplo, no campo de "Descrição de uma Pane") e esse código é executado no navegador dos outros usuários. 

Ao proibir o `'unsafe-inline'`, o navegador **bloqueia sumariamente qualquer script que esteja escrito diretamente dentro do HTML**, aceitando apenas scripts que vêm de arquivos `.js` externos e confiáveis.

### ❌ O que a CSP passou a bloquear:
1. Tags `<script>` com código dentro (ex: `<script> const ID = 123; </script>`).
2. Atributos de evento inline no HTML (ex: `<button onclick="fazerAlgo()">`).
3. Estilos inline abusivos (dependendo da configuração de `style-src`).

---

## 2. Como Evoluir de Forma Segura (O Padrão SAA29)

Como usamos o Jinja2 (Backend HTML) em conjunto com JavaScript Vanilla (Frontend), é muito comum querermos passar variáveis do Python/Jinja para o Javascript.

Para que o projeto evolua sem gerar novos bloqueios de CSP, **toda nova página ou funcionalidade deve seguir estritamente as regras abaixo**:

### Regra 1: Jamais use Eventos Inline
Nunca coloque `onclick`, `onsubmit`, `onchange` diretamente no HTML.

**❌ Errado (Bloqueado pela CSP):**
```html
<!-- no template html -->
<button id="btn-salvar" onclick="salvarDados()">Salvar</button>
```

**✅ Correto (Padrão Seguro):**
```html
<!-- no template html -->
<button id="btn-salvar">Salvar</button>
```
```javascript
// no arquivo .js externo
document.getElementById('btn-salvar').addEventListener('click', salvarDados);
```

### Regra 2: Passagem de Variáveis via Atributos `data-*` (Recomendado)
Quando você precisar passar um ID ou uma variável do Jinja para o Javascript, não crie uma variável global em uma tag `<script>`. Use atributos HTML nativos, geralmente em elementos ocultos ou no próprio contêiner da página.

**❌ Errado (Bloqueado pela CSP):**
```html
<script>
    const PANE_ID = "{{ pane.id }}";
    const USUARIO_ATUAL = "{{ current_user.nome }}";
</script>
```

**✅ Correto (Padrão Seguro):**
```html
<!-- no template html -->
<div id="page-context" 
     data-pane-id="{{ pane.id }}" 
     data-usuario="{{ current_user.nome }}" 
     style="display: none;">
</div>
```
```javascript
// no arquivo .js externo
document.addEventListener("DOMContentLoaded", () => {
    const contextEl = document.getElementById("page-context");
    const paneId = contextEl.getAttribute("data-pane-id");
    const usuarioAtual = contextEl.getAttribute("data-usuario");
});
```

### Regra 3: Passagem de Dados Complexos (Listas/Objetos) via JSON Escapado
Se você precisa passar uma lista ou um objeto inteiro para o frontend, insira como texto (string JSON) no atributo `data-*` ou utilize uma tag `<script type="application/json">` (pois o navegador não tenta *executar* json, logo a CSP não bloqueia).

**✅ Padrão Seguro para Dados Complexos:**
```html
<script type="application/json" id="dados-iniciais">
    {{ meus_dados_em_json | safe }}
</script>
```
```javascript
// no arquivo .js externo
const dados = JSON.parse(document.getElementById('dados-iniciais').textContent);
```

---

## 3. Alternativa Avançada: O Uso de Nonces (Criptografia)
Se houver uma situação incontornável onde um script inline **precisa** ser utilizado (por exemplo, a inicialização de um widget de terceiros que não suporta arquivos externos), a solução é usar um **Nonce**.

Um Nonce é um token aleatório gerado pelo servidor a cada requisição.
1. O backend gera: `nonce="a1b2c3d4"`
2. O backend envia no header CSP: `script-src 'self' 'nonce-a1b2c3d4'`
3. O backend injeta no HTML: `<script nonce="a1b2c3d4"> console.log("Permitido!") </script>`

Como o atacante não tem como prever o nonce aleatório, se ele injetar um script no banco de dados, o script dele não terá o nonce correto e será bloqueado. 
*(Nota: Atualmente o SAA29 não utiliza nonces, pois a Regra 2 resolve 99% dos casos de forma muito mais simples).*

## Conclusão
A adoção estrita das **Regras 1 e 2** acima resolve definitivamente os atritos com a CSP. Toda vez que um novo desenvolvedor (ou uma IA) for criar uma página, ele deve ser lembrado que **"Scripts inline são estritamente proibidos na arquitetura do SAA29"**.

---

## 4. Plano de Implementação e Auditoria (Página por Página)

A pedido, foi realizada uma varredura completa na pasta `app/web` (templates e scripts) para identificar todos os pontos de falha e aplicar a estratégia da **Opção 1 (Atributos `data-*`)** e **Meta Tags**. 

A excelente notícia é que a arquitetura do SAA29 já está muito bem separada (Jinja entregando a "casca" e o JS buscando dados via API `fetch`). 

Abaixo está o resultado da auditoria de CSP em 100% das páginas do sistema:

| Página / Template | Status CSP | Estratégia de Passagem de Dados (Opção 1) |
| :--- | :---: | :--- |
| `base.html` | ✅ Seguro | Utiliza `<meta name="csrf-token" content="...">` para o token de segurança. Sem eventos `onclick`. |
| `panes/detalhe.html` | ✅ Seguro | **(Corrigido)** Substituído script inline por `<div id="pane-data" data-pane-id="{{ pane_id }}"></div>`. O arquivo `panes_detalhe.js` lê esse DOM. |
| `panes/lista.html` | ✅ Seguro | Totalmente assíncrono. O JS busca as panes via `/panes` (GET). Nenhuma injeção Jinja necessária. |
| `aeronaves.html` | ✅ Seguro | Totalmente assíncrono. O JS busca os dados via API. Nenhuma injeção Jinja. |
| `configuracoes.html` | ✅ Seguro | Totalmente assíncrono. Não requer variáveis do backend no carregamento inicial. |
| `efetivo.html` | ✅ Seguro | Totalmente assíncrono. O JS busca usuários via `/auth/usuarios`. |
| `inventario.html` | ✅ Seguro | Totalmente assíncrono. |
| `vencimentos.html` | ✅ Seguro | Totalmente assíncrono. |
| `dashboard.html` | ✅ Seguro | Totalmente assíncrono. |
| `login.html` | ✅ Seguro | Formulário puro. Sem injeção de variáveis necessárias. |

### Conclusão Final da Auditoria
Com a correção aplicada na página `panes/detalhe.html`, **o SAA29 alcançou 100% de conformidade com a CSP**. Não há mais nenhum `<script>` inline injetando código no sistema em lugar algum do projeto. O sistema está estruturalmente blindado e pronto para produção com a regra de "Zero Inline Scripts" devidamente implementada.
