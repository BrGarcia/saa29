# PDF.js vendorizado

Vendorizado (não via CDN) porque a CSP do projeto é `script-src 'self'` —
`docs/methodology/CSP.md` documenta o motivo e o delta necessário para o
worker.

| | |
|---|---|
| Pacote | `pdfjs-dist` |
| Versão | `6.2.108` |
| Licença | Apache-2.0 (`LICENSE-pdfjs.txt`, verbatim do pacote npm) |
| Origem | `https://registry.npmjs.org/pdfjs-dist/-/pdfjs-dist-6.2.108.tgz`, `package/build/` |
| Arquivos | `pdf.min.mjs` (API principal, ES module) + `pdf.worker.min.mjs` (worker de parsing/renderização, carregado via `GlobalWorkerOptions.workerSrc`) |

Não inclui `cmaps/` nem `standard_fonts/` (usados para CJK e substituição de
fontes não embutidas) — o acervo de manuais é em português/inglês com fontes
Latin embutidas nos PDFs de origem; sem esses diretórios, um PDF que dependa
de uma fonte padrão não embutida pode renderizar com uma fonte de fallback do
navegador em vez da exata. Se isso aparecer na prática, adicionar
`package/web/cmaps/` e `package/build/standard_fonts/` do mesmo tarball.

## Atualizar a versão

1. Baixar `https://registry.npmjs.org/pdfjs-dist/-/pdfjs-dist-<versao>.tgz`.
2. Extrair `package/build/pdf.min.mjs`, `package/build/pdf.worker.min.mjs` e
   `package/LICENSE` (renomeado para `LICENSE-pdfjs.txt`).
3. Atualizar a tabela acima.
4. Testar a abertura de um PDF no viewer antes de commitar — mudança de major
   version do pdfjs-dist já quebrou API pública em versões passadas.
