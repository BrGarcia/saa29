# INICIO.md

## 1. CONTEXTO DO PROJETO
Sistema backend baseado em FastAPI para [DESCREVA EM 1 LINHA].
Arquitetura orientada a serviços modulares com persistência relacional.

Stack:
- FastAPI (API layer)
- SQLAlchemy (ORM)
- Pydantic (schemas/validation)
- Alembic (migrations)
- Jinja2 (templates)
- Docker (containerization)
- SlowAPI (rate limit)
- Python-Magic (file validation)

---

## 2. PRINCÍPIOS OBRIGATÓRIOS
- NÃO duplicar lógica
- SEMPRE tipar com Pydantic
- ACESSO a banco apenas via camada de serviço/repositorio
- ROTAS devem ser finas (thin controllers)
- TODA regra de negócio deve estar desacoplada
- MIGRAÇÕES via Alembic (nunca manual)
- VALIDAÇÃO sempre explícita (nunca implícita)

---

## 3. ARQUITETURA (RESUMO)
[DESCREVER EM 5-10 LINHAS]

Exemplo:
- `routes/` → entrada HTTP
- `services/` → regras de negócio
- `repositories/` → acesso ao banco
- `models/` → SQLAlchemy
- `schemas/` → Pydantic
- `core/` → configs, segurança, utils

---

## 4. FLUXO PADRÃO (REQUEST LIFECYCLE)
1. Request → FastAPI route
2. Validação → Pydantic schema
3. Processamento → Service layer
4. Persistência → Repository (SQLAlchemy)
5. Response → Schema de saída

---

## 5. PONTOS CRÍTICOS
- Segurança: ver `seguranca.md`
- Arquitetura detalhada: ver `arquitetura.md`
- Convenções: ver `conventions.md`
- Glossário: ver `glossario.md`

---

## 6. REGRAS DE MODIFICAÇÃO
Antes de alterar código:
1. Verificar impacto em services e schemas
2. Garantir compatibilidade com migrations
3. Validar contratos de API
4. Evitar breaking changes sem documentação

---

## 7. PADRÕES DE IMPLEMENTAÇÃO

### Criar endpoint:
- Criar schema (entrada/saída)
- Criar service
- Criar repository (se necessário)
- Criar rota
- Adicionar validação e rate limit

### Banco:
- Alterar model
- Gerar migration (Alembic)
- Revisar downgrade

---

## 8. ANTI-PADRÕES (PROIBIDOS)
- Lógica dentro de routes
- SQL direto fora de repository
- Uso de dict ao invés de schema
- Falta de tipagem
- Código não determinístico

---

## 9. ESTADO ATUAL DO PROJETO
[Descrever rapidamente o que já está implementado e o que falta]

---

## 10. TAREFAS PRIORITÁRIAS
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

---

## 11. COMO A IA DEVE OPERAR
- Sempre consultar este arquivo primeiro
- Navegar para arquivos específicos conforme seção 5
- Nunca assumir comportamento não documentado
- Em caso de dúvida: inferir baseado nos princípios (seção 2)

---

## 12. RESUMO ULTRA-COMPACTO (PARA CONTEXTO RÁPIDO)
Backend FastAPI modular com separação strict de camadas (route/service/repository), validação via Pydantic, persistência SQLAlchemy, migrations Alembic, foco em segurança, tipagem forte e baixo acoplamento.