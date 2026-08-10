# ROADMAP.md – Roteiro de Entregas e Evolução SAA29

**Projeto:** SAA29 – Sistema de Gestão de Panes – Eletrônica A-29

---

## 📊 Visão Geral do Ciclo de Vida

```
v1.x: Estabilização e UX   ██ Concluído/Refinando (v1.5.0)
v2.0: Pedidos e Hangar     ░░ Em Execução / Próxima Entrega
v3.0: Inteligência e Dados ░░ Planejado (Analytics)
v4.0: Conformidade Legal   ░░ Planejado (Oficialização)
v5.0: Ecossistema Total    ░░ Visão Final (IA & Supply)
```

---

## 🚀 Próxima Etapa Imediata: Refatoração FABLE 5

*Foco: Qualidade de código, eliminação de débitos técnicos e otimização de performance.*

- [ ] **1. Correção de Bug Crítico (`NameError: Aeronave`):** Tratar a ausência de import no topo do `app/modules/equipamentos/service.py` em `_validar_e_resolver_conflitos`.
- [ ] **2. Otimização N+1 Query no Inventário:** Substituir as chamadas SQL repetidas dentro do loop de slots em `listar_inventario_aeronave` por subqueries agrupadas com `row_number()`.
- [ ] **3. Eliminação de Anti-Padrões (`print`/`traceback`):** Migrar tratamento de erros em `service.py` para `logging.getLogger(__name__)`.
- [ ] **4. Deduplicação e Padronização:** Unificar a herança de controles de vencimento (`_herdar_controles_do_modelo`) e padronizar exceções de domínio (`domain_exc`).
- [ ] **5. Proteção de Concorrência (TOCTOU):** Garantir atocimidade em `criar_modelo` e `_obter_ou_criar_item_por_pn` tratando `IntegrityError`.
- [ ] **6. Auditoria Estendida:** Expandir a revisão FABLE 5 para os módulos `app/modules/panes/service.py` e `app/modules/vencimentos/service.py`.

---

## ✅ Histórico de Versões Concluídas (v1.x)

- [x] **v1.0.0**: Lançamento estável com CRUD de Panes, Frota e Efetivo.
- [x] **v1.1.0**: Implementação de Soft Delete de usuários e Interface de Intervenção Direta.
- [x] **v1.2.0**: Exportação universal de relatórios (CSV/XLSX), desacoplamento de contratos DDD (`AeronaveLookupProtocol`), matriz CI/CD no GitHub Actions e 179 testes automatizados com 100% de sucesso.
- [x] **v1.3.0**: Emissão de PDF da Ordem de Inspeção e Checklist de Manutenção (`/inspecoes/{id}/pdf` e `/inspecoes/{id}/checklist` no formato A4 oficial FAB).
- [x] **v1.4.0**: Módulo Mobile da Linha de Voo (`/m/`), menu hambúrguer off-canvas drawer, baixa de tarefas em 1 toque, sincronização automatizada e atômica da hierarquia de status de aeronaves (DISPONÍVEL ➔ INDISPONÍVEL), conformidade estrita com CSP e 205 testes automatizados com 100% de sucesso.
- [x] **v1.5.0 (Atual)**: 
  - Especificação Técnica (`docs/backlog/feature_controle_pedidos.md`) e Mockup Visual Interativo Aprovado (`docs/backlog/mockup_pedidos.html`) do módulo **Central de Pedidos**.
  - Reorganização estrutural e saneamento da pasta de documentação `docs/` em camadas limpas e legíveis.

---

## 📦 v2.0 – Central de Pedidos e Mobilidade Hangar

*Objetivo: Levar a gestão de reposição e operações de campo para debaixo da asa da aeronave.*

- [x] **Módulo Central de Pedidos (Fase 1 - Backend)**: Modelo `Pedido` standalone e desacoplado de `equipamentos`/`vencimentos` (revisão v2.0 — `part_number`/`nomenclatura` como texto de referência, sem FK para o catálogo), numeração server-side `P-{ano}-{seq}`, RBAC (Encarregado/Inspetor/Admin), service e rotas REST completas (`/pedidos`) com 24 testes automatizados.
- [x] **Módulo Central de Pedidos (Fase 2 - Frontend)**: Interface web integrada no SAA29 (`/pedidos`) com cards de resumo, filtros, tabela paginada com linha expansível, modais de criação/edição e cancelamento — layout adaptado do mockup aprovado à v2.0.
- [ ] **PWA (Progressive Web App)**: Interface instalável em tablets e celulares com suporte a **Modo Offline** para hangares sem Wi-Fi estável.
- [ ] **Scanner de QR Code**: Identificação instantânea de aeronaves e caixas pretas via câmera do dispositivo.
- [ ] **Gestão de Evidências Pro**: Upload múltiplo de fotos com ferramentas de anotação (desenhar círculos em falhas físicas) diretamente na imagem.

---

## 🧠 v3.0 – Inteligência e Performance (The Analytical Version)

*Objetivo: Transformar registros em dados estratégicos para o Comando.*

- **Dashboard de MTTR / MTBF**: Cálculos automáticos de Tempo Médio de Reparo e Tempo Médio Entre Falhas por sistema (ATA).
- **Análise de Tendências**: Identificação automática de "aeronaves problemáticas" ou sistemas com falhas recorrentes acima da média.
- **Gestão de Estoque Local**: Vínculo básico de peças (P/N e S/N) utilizadas na pane, com alerta de nível crítico de componentes em prateleira.
- **Central de Alertas**: Notificações via Telegram/E-mail para Encarregados quando uma pane crítica for aberta ou ultrapassar 24h sem solução.

---

## 📝 v4.0 – Conformidade e Formalismo (The Formal Version)

*Objetivo: Eliminar o papel e oficializar o sistema como fonte única de verdade.*

- **Gerador de Documentos Oficiais**: Exportação automática de Folhas de Alteração e registros de caderneta no padrão oficial da FAB em PDF.
- **Assinatura Digital (ICP-Brasil)**: Integração com certificados digitais (Token/Nuvem) para assinatura eletrônica de ordens de serviço.
- **Advanced TBO Tracking**: Controle rigoroso de vida útil de componentes por horas de voo e ciclos, com cronômetro visual de vencimento.

---

## 🌐 v5.0 – Ecossistema e Autonomia (The Enterprise Version)

*Objetivo: Manutenção preditiva e integração total da cadeia logística.*

- **IA Preditiva**: Algoritmo que prevê a probabilidade de falha de um componente baseando-se no histórico de telemetria e voo.
- **Pedigree Total do Componente**: Histórico completo de cada S/N, rastreando por quais aeronaves passou e quais intervenções sofreu desde a incorporação.
- **Supply Chain Integration**: Comunicação automática com sistemas logísticos superiores para solicitação de compra/suprimento ao atingir estoque mínimo.

---

## 🏁 Critérios de Sucesso da Evolução

| Versão | Meta Principal |
|--------|----------------|
| **v1.5 / Refatoração** | 0 bugs críticos em `service.py`, eliminando N+1 e garantindo 100% de testes limpos. |
| **v2.0** | Gestão de pedidos integrada ao inventário e redução do tempo de digitação no hangar em 50%. |
| **v3.0** | Identificação de 100% das falhas repetitivas via sistema. |
| **v4.0** | Redução de 90% no uso de papel para registros técnicos. |
| **v5.0** | Aumento da disponibilidade média da frota em 15% via predição. |

---

*Uso interno – Força Aérea Brasileira.*
