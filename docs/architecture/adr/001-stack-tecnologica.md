# ADR-001: Escolha da Stack Tecnológica

**Data:** 2026-03-27  
**Status:** Aceito  
**Decisores:** Equipe de desenvolvimento SAA29

---

## Contexto

O SAA29 é um sistema web para gerenciamento de panes de manutenção aeronáutica do A-29, operado em ambiente militar. Os requisitos principais são: desempenho (resposta < 2s), segurança (autenticação), simplicidade operacional e banco de dados relacional com rastreabilidade.

A equipe possui familiaridade com Python. O sistema precisa ser mantido por diferentes equipes ao longo do tempo.

## Decisão

Adotar **FastAPI + SQLAlchemy 2.x + PostgreSQL 16 + Pydantic v2** como stack principal.

| Camada | Escolha | Versão |
|--------|---------|--------|
| Framework Web | FastAPI | 0.115.x |
| ORM | SQLAlchemy (async) | 2.0.x |
| Banco de Dados | PostgreSQL | 16 |
| Migrações | Alembic | 1.14.x |
| Validação | Pydantic | v2 |
| Auth | python-jose + passlib | latest |
| Config | pydantic-settings | 2.x |

## Alternativas Consideradas

| Alternativa | Prós | Contras |
|-------------|------|---------|
| Django + DRF | Maduro, admin embutido | Muito opinado, lento para APIs simples |
| Flask + SQLAlchemy | Leve, flexível | Menos convenções, mais configuração manual |
| FastAPI + Tortoise ORM | Async nativo | Menos maduro, comunidade menor |
| FastAPI + SQLAlchemy (escolhido) | Async, tipagem, documentação automática | Curva de aprendizado ORM async |

## Consequências

**Positivas:**
- Documentação automática (Swagger/ReDoc) sem esforço
- Validação de entrada com erros detalhados via Pydantic
- Queries assíncronas para melhor throughput
- Migrações versionadas com Alembic
- Tipagem estrita facilita manutenção a longo prazo

**Negativas / Trade-offs:**
- Curva de aprendizado maior para devs acostumados com Django síncrono
- `async/await` em toda a camada de dados requer atenção
- PostgreSQL requer infraestrutura dedicada (não embarcado como SQLite)

## Referências
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [00_SRS.md §4 – Requisitos Não Funcionais](../../../00_SRS.md)
