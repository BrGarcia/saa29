# NEXT.md – Status e Próximos Passos

**Versão Atual:** `1.0.0` (Produção)

---

## 📊 Progresso

| Fase | Status | Descrição |
|------|--------|-----------|
| ✅ Fundação e Backend | 100% | Core, Auth, Panes, Aeronaves, Equipamentos (API) |
| ✅ Interface (UI/UX) | 90% | Login, Panes, Efetivo, Frota concluídos |
| ✅ Segurança | 100% | Auditoria resolvida (AUD-01 a AUD-22) |
| ✅ Portabilidade | 100% | Suporte nativo a SQLite e PostgreSQL |
| 🔲 Equipamentos (UI) | Pendente | Interface para gestão de controles e vencimentos |
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

---

*Última atualização: 2026-04-09*
