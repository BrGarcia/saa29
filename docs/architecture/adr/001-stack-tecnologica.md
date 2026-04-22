# ADR-001: Escolha da Stack Tecnologica

**Data:** 2026-03-27  
**Status:** Aceito  
**Decisores:** Equipe de desenvolvimento SAA29

---

## Contexto

O SAA29 precisa entregar uma aplicacao web unica, com API JSON e paginas HTML, mantendo regras de negocio em uma camada de servico desacoplada do transporte HTTP.

Os requisitos principais sao:

- desempenho previsivel;
- rastreabilidade de dados;
- autenticacao e autorizacao;
- simplicidade operacional;
- baixo atrito para testes e manutencao.

## Decisao

Adotar **FastAPI + SQLAlchemy 2.x async + Pydantic v2** como stack principal, com **SQLite async por padrao** e configuracao de banco via `DATABASE_URL`.

| Camada | Escolha |
|--------|---------|
| Framework Web | FastAPI |
| ORM | SQLAlchemy 2.x async |
| Validacao | Pydantic v2 |
| Configuracao | pydantic-settings |
| Banco padrao | SQLite + aiosqlite |
| Migrações | Alembic |
| Templates HTML | Jinja2 |
| Auth | python-jose + passlib |
| Limite de taxa | slowapi |

## Alternativas Consideradas

| Alternativa | Pro | Contra |
|-------------|-----|--------|
| Django + DRF | Ecossistema maduro | Mais opinativo para o formato atual do projeto |
| Flask + extensoes | Leve | Exige mais montagem manual |
| FastAPI + Tortoise | Async nativo | Menos aderencia ao conjunto atual de tipos e ORM |
| FastAPI + SQLAlchemy 2.x | Tipagem, async e maturidade | Exige disciplina na separacao de camadas |

## Consequencias

**Positivas:**

- rotas documentadas automaticamente;
- validacao de entrada e saida com Pydantic;
- camada de servico facil de testar;
- modelo relacional com migrações versionadas;
- suporte a UI server-side e API no mesmo codigo-base;
- boa compatibilidade com testes usando banco isolado.

**Negativas / Trade-offs:**

- a pilha async exige cuidado em toda a camada de persistencia;
- o bootstrap precisa importar modelos explicitamente para registrar mapeamentos;
- SQLite continua mais sensivel a concorrencia de escrita do que um banco relacional dedicado;
- a manutencao de middleware e dependencias centralizadas exige disciplina de arquitetura.

## Referencias

- [`docs/architecture/overview.md`](../overview.md)
- [`app/bootstrap/main.py`](../../../app/bootstrap/main.py)
- [`app/bootstrap/database.py`](../../../app/bootstrap/database.py)
- [`app/bootstrap/config.py`](../../../app/bootstrap/config.py)
- [00_SRS.md](../../requirements/00_SRS.md)
