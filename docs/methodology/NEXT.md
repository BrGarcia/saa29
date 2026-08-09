# NEXT.md – Status e Próximos Passos

**Versão Atual:** `1.2.0` (Produção)

---

## 📊 Progresso

| Fase | Status | Descrição |
|------|--------|-----------|
| ✅ Fundação e Backend | 100% | Core, Auth, Panes, Aeronaves, Equipamentos, Inspeções e Calendário |
| ✅ Interface (UI/UX) | 100% | Login, Panes, Efetivo, Frota, Inspeções, Calendário e Configurações |
| ✅ Segurança | 100% | CSP Estrito, CSRF, Token Rotation e Bloqueio Brute Force Environment-Aware |
| ✅ Portabilidade | 100% | Suporte nativo e testado a SQLite e PostgreSQL |
| ✅ Equipamentos & Relatórios | 100% | Gestão de controles, vencimentos e exportação de dados (CSV UTF-8 / XLSX) |
| ✅ Arquitetura & DDD | 100% | Desacoplamento via `AeronaveLookupProtocol` e 179 testes unitários passing |
| ✅ Deploy Automatizado | 100% | CI/CD no GitHub Actions com matriz de testes em SQLite & Postgres |
| 🔲 Ordem de Inspeção (PDF) | Planejado | Emissão de PDF A4 da Ordem de Serviço com checklist e inventário controlado |

---

## 🚀 Como Rodar (Local)

O projeto está otimizado para rodar com **SQLite** sem dependências externas:

```bash
# 1. Setup
pip install -r requirements.txt
cp .env.example .env

# 2. Banco e Dados
alembic upgrade head
python scripts/db/init_db.py

# 3. Execução da Aplicação
python scripts/run_app.py
```

---

## 📋 Próximas Tarefas (Visão v1.3.0 & v2.0 - Hangar & Mobilidade)

1. **Emissão de PDF da Ordem de Inspeção (OS)**:
   - Implementação de gerador ReportLab para compilar o checklist com trigramas e inventário controlado da aeronave em PDF A4.
   - Endpoint `GET /api/v1/inspecoes/{id}/pdf` e botão de impressão em `inspecao_detalhe.html`.

2. **Carga e Importação em Lote via Excel (XLSX)**:
   - Interface para upload e validação de inventário massivo via planilha.

2. **Mobilidade & PWA (Hangar Floor)**:
   - Tornar a aplicação instalável como PWA para tablets e celulares no pátio.
   - Suporte a cache offline de consultas essenciais.

3. **Scanner de QR Code**:
   - Leitura via câmera do dispositivo para busca instantânea de caixas-pretas e células.

4. **Integração com Manual FIM (Fault Isolation Manual)**:
   - Recomendação de procedimentos de correção ao registrar códigos ATA de panes.

---

## 🛠️ Correções e Auditorias Concluídas

- [x] Implementação de `selectinload` para mitigar N+1 queries em inventários e panes.
- [x] Refatoração de Exceções de Domínio + Global Exception Handler no FastAPI.
- [x] Configuração de PRAGMA WAL no SQLite para alta concorrência.
- [x] Refatoração do Frontend com remoção de handlers inline (CSP Hardening).
- [x] Desacoplamento DDD entre Equipamentos e Aeronaves via `AeronaveLookupProtocol`.
- [x] Sistema genérico de exportação CSV (UTF-8 BOM) e XLSX em Panes, Inventário e Inspeções.
- [x] Resolução de 100% das 13 vulnerabilidades e defeitos auditados no `RELATORIO_FINAL.MD`.
- [x] Suíte automatizada com **179 testes unitários e de integração passing (100% sucesso)**.

---

*Última atualização: 2026-07-23*
