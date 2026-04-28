# NEXT.md – Status e Próximos Passos

**Versão Atual:** `1.1.0` (Produção)

---

## 📊 Progresso

| Fase | Status | Descrição |
|------|--------|-----------|
| ✅ Fundação e Backend | 100% | Core, Auth, Panes, Aeronaves, Equipamentos (API) |
| ✅ Interface (UI/UX) | 98% | Login, Panes, Efetivo, Frota, Configurações (parcial), Refatoração CSP |
| ✅ Segurança | 100% | Auditoria e Hardening de Frontend (CSP estrito) concluídos |
| ✅ Portabilidade | 100% | Suporte nativo a SQLite e PostgreSQL |
| 🔲 Equipamentos (UI) | Em Andamento | Interface para gestão de controles e vencimentos |
| 🔲 Deploy Automatizado | Pendente | CI/CD completo no GitHub Actions |

---

## 🚀 Como Rodar (Local)

O projeto está otimizado para rodar com **SQLite** sem dependências externas:

```bash
# 1. Setup
pip install -r requirements.txt
cp .env.example .env

# 2. Banco e Dados
alembic upgrade head

# 3. App
uvicorn app.main:app --reload
```

---

## 📋 Próximas Tarefas

1. **Interface de Equipamentos**:
   - Desenvolver telas para listagem de itens e inspeção de vencimentos.
   - Implementar fluxo de instalação/remoção de componentes em aeronaves.

2. **Refinamento de Deploy**:
   - Validar workflow de CI no repositório.
   - Testar estabilidade do container em ambiente de homologação.

3. **Correções Técnicas (Pós-Auditoria)**:
   - [x] Implementar `selectinload` para mitigar N+1 queries em listagens de inventário.
   - [x] Refatorar tratamento de erros para Exceções de Domínio + Global Exception Handler.
   - [x] Configurar PRAGMA WAL no SQLite para performance concorrente.
   - [x] Refatorar Frontend para remover handlers inline (CSP Hardening).
   - [x] Documentar bug de Inativação de Aeronaves (Docs/Relatorio).

---

*Última atualização: 2026-04-28*
