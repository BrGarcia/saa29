# NEXT.md – Guia do Desenvolvedor: Próximos Passos

**Projeto:** SAA29 – Sistema de Gestão de Panes – Eletrônica A-29  
**Atualizado em:** 2026-03-31  
**Branch atual:** `main`  
**Versão atual:** `0.7.0` (Auditada e Segura)

---

## 📊 Onde Estamos

| Fase | Status | Dia |
|------|--------|-----|
| ✅ Fase 1 – Fundação | Concluída | Dia 2 |
| ✅ Fase 2 – Testes | Concluída | Dia 3 |
| ✅ Fase 3 – Codificação | Concluída | Dia 4 |
| ✅ Fase 3.5 – Migração e Seed | Concluída | Dia 5 |
| ✅ Fase 4 – Otimização | Concluída | Dia 5 |
| ✅ Fase 5 – Interface | Concluída | Dia 6 |
| ✅ **Extra – Auditoria e Hardening** | **Concluída** | **Dia 6.5** |
| 🔲 Fase 6 – Deploy/CI | Pendente | Dia 7 |

> **Resumo Atual:** Versão **0.7.0** estabilizada com todas as 22 correções de segurança da auditoria implementadas (XSS, RBAC, JWT Hardening). UI de Panes otimizada para edição rápida.
> Faltam: **Deploy (CI/CD)** e **Módulo de Equipamentos (UI)**.

---

## 🚀 Ao Abrir o Projeto: Checklist Inicial

### 1. Ambiente Local (Novo!)
Agora temos scripts para rodar o projeto rapidamente com SQLite:

```bash
# 1. Instalar dependências (incluindo python-magic-bin para Windows)
pip install -r requirements.txt

# 2. Inicializar banco SQLite local e sementes
python scripts/init_local.py

# 3. Rodar a aplicação
python scripts/run_app.py
```
Acesse: **http://127.0.0.1:8000** (admin/admin123)

### 2. Validar o Estado Atual (70 Testes)
```bash
pytest tests/ -v
```
> ✅ **Todos os 70 testes estão passando.**

---

## 🔲 Próximos Passos Imediatos (Dia 7)

### 1. Deploy e CI/CD (Alta Prioridade)
| # | Tarefa | Detalhes |
|---|--------|---------|
| 1 | **GitHub Actions** | Consolidar `.github/workflows/ci.yml` para rodar os 70 testes em cada push. |
| 2 | **Ambiente de Produção** | Configurar `APP_ENV=production` e garantir que `APP_SECRET_KEY` não seja default. |
| 3 | **Dockerização Final** | Testar o `docker-compose.yml` com a nova estrutura de segurança. |

### 2. Módulo de Equipamentos (UI)
As APIs de equipamentos estão 100% funcionais e protegidas por RBAC, mas faltam as telas:
- [ ] Listagem de Equipamentos e Itens (S/N).
- [ ] Tela de Vencimentos (Controle de Calendário/Horas).
- [ ] Interface para instalação/remoção de itens em aeronaves.

---

## ✅ Conquistas Recentes (Build 0.7.0)
- [x] **Segurança Centralizada:** `escapeHtml` global no `app.js` prevenindo XSS em todas as tabelas.
- [x] **JWT Hardening:** Implementada Blacklist de tokens (JTI) no logout e expiração reduzida para 2h.
- [x] **RBAC Estrito:** Endpoints de Aeronaves e Equipamentos agora exigem `EncarregadoOuAdmin`.
- [x] **Edição Ágil:** Modal de edição de panes direto na lista (UX melhorada).
- [x] **Proteção de Admin:** Impedida a auto-exclusão e a exclusão do último administrador.

---

## 📋 Resumo Executivo: O Que Fazer

```
┌─────────────────────────────────────────────────────────────┐
│                    ORDEM DE EXECUÇÃO                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  CONCLUÍDO → Auditoria de Segurança (0.7.0)                │
│                                                             │
│  AGORA     → Fase 6: Deploy + CI/CD                        │
│             (Configurar GitHub Actions e VPS)               │
│                                                             │
│  FUTURO    → Frontend para Gestão de Equipamentos          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---
> **Nota de Segurança:** Nunca altere `APP_ENV` para `production` sem definir uma `APP_SECRET_KEY` forte no `.env`. O sistema agora bloqueia a inicialização se detectar chaves inseguras em produção.
