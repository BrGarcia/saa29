# Achado avulso — visualização de anexo PDF em `panes` quebrada pelo `X-Frame-Options`

> Registrado durante a implementação do M1 do módulo `publicacoes`
> (`docs/backlog/modulo_publicacoes/04_plano_de_execucao.md`, M1 tarefa 11), que pedia
> explicitamente para **verificar e registrar como bug separado, sem corrigir aqui** — a correção
> muda o comportamento de um módulo em produção e merece PR própria.
>
> Nenhum arquivo de `panes` foi alterado.

---

### [BUG-01] Anexo do tipo `DOCUMENTO` nunca renderiza no modal — `X-Frame-Options: DENY` bloqueia o próprio iframe

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `app/web/static/js/panes_detalhe.js:593`
- **Eixo:** Contrato / Frontend
- **Problema:** `abrirAnexo()` monta a pré-visualização de anexos não-imagem com um iframe:

  ```javascript
  } else if (tipoAnexo === "DOCUMENTO") {
      anexoContent.innerHTML = `<iframe src="${downloadUrl}" style="width: 100%; height: 80vh; border: none;"></iframe>`;
  }
  ```

  `downloadUrl` é `/panes/{PANE_ID}/anexos/{anexoId}/download`, servido por
  `app/modules/panes/router.py` com `FileResponse`. Só que
  `app/shared/middleware/security.py:27` injeta `X-Frame-Options: DENY` em **todas** as respostas,
  sem exceção de rota — inclusive nessa. `DENY` (diferente de `SAMEORIGIN`) proíbe o
  enquadramento **mesmo pela própria origem**, então o navegador recusa renderizar o documento.

  O caminho é alcançável com dado real: `panes/service.py:653` classifica como
  `TipoAnexo.DOCUMENTO` tudo que não é imagem, e `EXTENSOES_PERMITIDAS`
  (`app/shared/core/file_validators.py`) aceita `.pdf` — ou seja, **todo PDF anexado a uma pane cai
  exatamente neste ramo**.

- **Consequência:** o modal abre, mostra "Carregando arquivo..." e fica em um quadro em branco. Não
  há erro de JavaScript (o `try/catch` não é acionado: o `innerHTML` foi atribuído com sucesso; quem
  recusa é o navegador, com um aviso no console). O usuário não recebe nem a pré-visualização nem a
  alternativa de download, que existe só no ramo `else`. Nenhum teste cobre o caminho — a suíte de
  `panes` testa o endpoint de download, não a renderização.

- **Correção proposta (três opções, em ordem de preferência):**
  1. **Trocar o ramo `DOCUMENTO` por download/nova aba**, igual ao ramo `else`. É a correção de uma
     linha, não mexe em header de segurança e entrega ao usuário algo que funciona hoje.
  2. **Viewer em canvas com PDF.js**, como o módulo `publicacoes` faz no M1 — melhor experiência,
     mas exige vendorizar a biblioteca e ajustar a CSP (`worker-src 'self' blob:`). Faz sentido
     depois que o viewer de `publicacoes` estiver pronto e puder ser reaproveitado.
  3. **Isentar a rota do `X-Frame-Options`** (ou usar `SAMEORIGIN` só nela). Funciona, mas abre
     exceção em um header de segurança global para um caso de uso que a opção 1 resolve sem custo —
     não recomendada.

- **Risco de regressão:** BAIXO na opção 1 (o comportamento atual é "nada aparece"; qualquer coisa é
  melhora). MÉDIO na opção 3, que enfraquece uma proteção global.
- **Precisa de teste antes?** NÃO para a opção 1 (é frontend puro sem cobertura hoje), mas vale um
  teste de que a rota de download continua devolvendo `application/pdf`.
- **Status:** ⏳ ABERTO — registrado, não corrigido. Fora do escopo do M1 de `publicacoes`.

---

## Nota para o módulo `publicacoes`

Este achado é a confirmação empírica da decisão **D-F** do módulo `publicacoes`
(`03_especificacao_tecnica.md` §4.4): o viewer de manuais **nunca** usa iframe, e sim PDF.js
renderizando em `<canvas>`. Não é preferência estética — é o único caminho que funciona com o
`X-Frame-Options: DENY` global, como o ramo `DOCUMENTO` de `panes` demonstra.
