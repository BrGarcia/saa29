# ALTERACOES.md

## Etapa: PANES como página principal

### Objetivo
Desativar a dashboard para uso corrente, sem remover sua lógica, e consolidar a página `PANES` como fluxo principal do sistema.

### O que foi alterado
- A rota raiz `/` passou a redirecionar para `/panes`
- A dashboard foi preservada em `/dashboard`, porém sem link ativo no menu lateral
- O menu lateral passou a exibir `PANES` como primeira página operacional
- O fluxo de login e pós-login passou a direcionar o usuário para `/panes`

### Arquivos alterados
- `app/pages/router.py`
- `templates/base.html`
- `templates/login.html`
- `README.md`
- `docs/requirements/00_SRS.md`
- `docs/requirements/01_SPECS.md`
- `ROADMAP.md`

### Decisão adotada
A dashboard não foi removida do sistema. Ela foi apenas desacoplada da navegação principal para permitir reativação futura com baixo custo.

### Impacto funcional
- Usuários autenticados entram diretamente na tela de panes
- O menu lateral não expõe mais a dashboard
- Links operacionais passam a assumir `PANES` como tela inicial do sistema

### Impacto arquitetural
- Não houve remoção de template, lógica de frontend ou rota funcional da dashboard
- A mudança foi restrita à navegação, roteamento e documentação

### Observações para revisão
- A dashboard continua acessível tecnicamente pela rota `/dashboard`
- A alteração foi intencionalmente não destrutiva
- O objetivo foi simplificar a operação diária sem perder a possibilidade de restauração futura
