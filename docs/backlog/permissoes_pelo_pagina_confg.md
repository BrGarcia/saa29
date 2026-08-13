desenvolve futuramente a ideia
de definir as permisoes RBAC de maneira individual atraves de checkbox 
em cada usuario na pagina de configuracoes. 
pagina Administração de Efetivo Militar
um botao "definir permissoes" que abre um modal e lista todos as permissoes e roles em formato de checkbox

---
> Avaliado em 2026-08-13 (análise em `docs/backlog/melhorias_pagina_configuracoes.md`,
> histórico do repo). Decisão: **não desenvolver**. O RBAC atual é por papel fixo
> (~126 pontos de checagem espalhados pelo backend); uma versão honesta desta ideia
> exigiria mudanças de backend, não só um checkbox na UI, e a quantidade de usuários
> do sistema não justifica esse esforço/risco em código de autorização. Mantido como
> registro histórico da ideia, sem plano de implementação.