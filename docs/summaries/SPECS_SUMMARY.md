# SPECS_SUMMARY
- Backend: FastAPI, SQLAlchemy (Async), Pydantic v2, Alembic.
- Banco: SQLite (Dev/Docker) / PostgreSQL (Optional/Prod).
- Frontend: Jinja2, CSS (Design System Vanilla), JS (Modules, CSP compliant).
- Auth: JWT HS256, Refresh Token Rotation, Blacklist (persisted).
- Inspeções: Catálogo desacoplado, snapshot de tarefas na abertura, cálculo automático de DPE.
- Imagens: Pipeline de processamento (WebP, Resizing, Optimization) via shared services.
