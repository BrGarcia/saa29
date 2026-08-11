# Plano de Implementação do JSDoc - SAA29

Este documento detalha o plano de adoção gradual do JSDoc para trazer tipagem estática e autocompletação ao frontend Vanilla JS do projeto SAA29, sem a necessidade de instalar Node.js ou compiladores.

---

## 🎯 Objetivos
1. **Inteligência no Editor:** Habilitar autocompletação do VS Code para propriedades de objetos da API, métodos do DOM e funções globais.
2. **Redução de Erros de Sintaxe:** Identificar preventivamente erros de digitação de propriedades (ex: `user.funcao` vs `user.funçao`) diretamente no editor com a diretiva `// @ts-check`.
3. **Facilidade para IA:** Fornecer um contrato de dados claro para que assistentes de Inteligência Artificial gerem códigos mais precisos e sem alucinações de campos do banco de dados.

---

## 🛠️ Diretrizes e Regras de Sintaxe JSDoc

### 1. Diretiva de Validação
Todo arquivo que iniciar a validação deve começar com o seguinte comentário na linha 1:
```javascript
// @ts-check
```

### 2. Definição de Modelos da API (`@typedef`)
Os payloads retornados pela API devem ser definidos no arquivo principal de utilitários (`app.js`) para serem compartilhados globalmente:
```javascript
/**
 * @typedef {Object} SAAUser
 * @property {number} id
 * @property {string} nome
 * @property {string} funcao
 * @property {string} [token]
 */
```

### 3. Documentação de Elementos DOM (`@type`)
Para evitar avisos de que métodos específicos (ex: `.reset()` em formulários) não existem em elementos genéricos:
```javascript
/** @type {HTMLFormElement | null} */
const form = /** @type {HTMLFormElement} */ (document.getElementById('formId'));
```

### 4. Documentação de Eventos (`@param`)
Funções de escuta de eventos devem ter o evento explicitado:
```javascript
/**
 * @param {SubmitEvent} e
 */
async function handleSubmit(e) {
    e.preventDefault();
}
```

---

## 📅 Cronograma de Implementação Gradual

### Fase 1: Fundação (Crítica) - **[CONCLUÍDA]**
* **Arquivos:** `app.js`
* **Foco:** Documentar as funções utilitárias que servem de base para todo o projeto (`apiFetch`, `showToast`, `escapeHtml`) e definir os tipos globais (`SAAUser`, `Aeronave`, `TipoControle`, `Equipamento`, `RegraVencimento`, `TipoInspecao`).
* **Status:** Todos os tipos declarados e funções utilitárias documentadas com o `@ts-check` ativo.

### Fase 2: Configurações (Crítica) - **[CONCLUÍDA]**
* **Arquivos:** `configuracoes.js`
* **Foco:** Aplicar a tipagem em um arquivo de grande porte (+1400 linhas), mapeando modais, tabelas dinâmicas e formulários críticos de cadastro de aeronaves, regras e PNs.
* **Status:** Todos os módulos internos (Aeronaves, Regras de Vencimento, Catálogo de PNs, Inspeções/Tarefas de Template, Categorias de Calendário e Upload de XLSX de Inventário) foram 100% documentados, com casts do DOM adequados e validados sob o controle estrito da diretiva `@ts-check`.

### Fase 3: Operacional e Visual (Crítica) - **[CONCLUÍDA]**
* **Arquivos:** `calendario.js`, `dashboard.js`, `efetivo.js`, `vencimentos.js`, `inspecoes.js`, `inventario.js`, `panes_detalhe.js`, `panes_lista.js`.
* **Foco:** Aplicar JSDoc ao fazer manutenções corretivas ou evolutivas nestes arquivos.
* **Status:** Todos os arquivos operacionais principais foram atualizados com a diretiva `@ts-check` e anotações completas de tipos.

---

## 📌 Convenções Adotadas
* **Tipos globais:** Devem ser mantidos em `app.js` ou em um arquivo centralizado de declarações se necessário.
* **Checagens de Nulo:** Sempre validar a existência do elemento DOM antes de manipular propriedades (`if (element) { ... }`).
