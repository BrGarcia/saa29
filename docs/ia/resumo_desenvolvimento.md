# Resumo de Desenvolvimento

dev_env:
- python 3.12+
- sqlite no local
- postgres possivel em producao

run:
- criar venv
- instalar requirements.txt
- copiar .env.example para .env
- rodar alembic upgrade head
- iniciar uvicorn app.main:app --reload

rules:
- manter rotas finas e regras de negocio em service
- escrever testes ao alterar comportamento
- nao misturar logica de dominio com templates/js
- nao versionar artefatos locais, logs e bancos gerados

common_tasks:
- seeds e init_db para preparar ambiente
- migrations em migrations/versions
- scripts auxiliares em scripts/

verification:
- pytest
- testes de seguranca e regressao quando mexer em auth, csrf, uploads ou db

