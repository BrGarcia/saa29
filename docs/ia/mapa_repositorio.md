# Mapa do Repositorio

root:
- app/: codigo principal
- docs/: documentacao
- migrations/: schema e historico do banco
- scripts/: manutencao, seeds e utilitarios
- static/: CSS e JS
- templates/: paginas Jinja2
- tests/: testes automatizados
- uploads/: arquivos enviados em runtime

app:
- main.py: bootstrap da app
- config.py: configuracao
- database.py: conexao e sessao
- dependencies.py: dependencias reutilizaveis
- core/: regras comuns
- middleware/: filtros transversais
- auth/, panes/, aeronaves/, equipamentos/: dominios
- pages/: rotas de paginas

docs:
- architecture/: desenho tecnico
- development/: guia de uso e testes
- security/: politica e orientacoes de seguranca
- requirements/: requisitos e specs
- archives/: material historico
- fim/: PDFs de referencia pesada

ignore_candidates:
- .pytest_cache/
- .mypy_cache/
- .ruff_cache/
- __pycache__/
- .venv/
- logs gerados
- banco local gerado

