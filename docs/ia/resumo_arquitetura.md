# Resumo de Arquitetura

sys: SAA29
type: web_mng
stack: fastapi, vanilla_js, sqlalchemy, pydantic, alembic, jinja2, sqlite, docker

arch:
- backend em FastAPI
- frontend com templates Jinja2 + JS/HTML/CSS
- persistencia via SQLAlchemy + migrations Alembic
- estrutura em camadas: router -> service -> models/schemas
- modulos por dominio: auth, aeronaves, equipamentos, panes, pages, core, middleware

focus:
- separacao de responsabilidades
- validacao de entrada
- seguranca de autenticacao e CSRF
- compatibilidade com banco local e producao

main_dirs:
- app/main.py: entrada da aplicacao
- app/core/: utilitarios, storage, limites, validadores
- app/auth/: autenticacao e seguranca
- app/panes/: fluxo principal do sistema
- app/aeronaves/: cadastro e operacoes de aeronaves
- app/equipamentos/: cadastro e operacoes de equipamentos

