BUG 01:
Descrição:Content Security Policy blocks inline execution of scripts and stylesheets
The Content Security Policy (CSP) prevents cross-site scripting attacks by blocking inline execution of scripts and style sheets.

To solve this, move all inline scripts (e.g. onclick=[JS code]) and styles into external files.

⚠️ Allowing inline execution comes at the risk of script injection via injection of HTML script elements. If you absolutely must, you can allow inline script and styles by:

adding unsafe-inline as a source to the CSP header
adding the hash or nonce of the inline script to your CSP header.
1 diretiva
Diretiva	Elemento	Local da origem	Status
script-src-attr		configuracoes:254	bloqueado
Saiba mais: Política de Segurança de Conteúdo: código in-line

SOLUÇÃO PROPOSTA:
SOLUÇÃO IMPLEMENTADA:


BUG 02
