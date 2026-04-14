# ROADMAP.md – Roteiro de Entregas e Evolução SAA29

**Projeto:** SAA29 – Sistema de Gestão de Panes – Eletrônica A-29

---

## 📊 Visão Geral do Ciclo de Vida

```
v1.x: Estabilização e UX   ██ Concluído/Refinando
v2.0: Mobilidade e Campo   ░░ Planejado (Hangar Floor)
v3.0: Inteligência e Dados ░░ Planejado (Analytics)
v4.0: Conformidade Legal   ░░ Planejado (Oficialização)
v5.0: Ecossistema Total    ░░ Visão Final (IA & Supply)
```

---

## 🛠️ Correções e Implementações Imediatas (Backlog Codex)
*Foco: Resolução de débitos técnicos e falhas de segurança identificados na auditoria Codex (14/04/26).*

- [ ] **Segurança (Logout - Critical):** Fazer `clearAuth()` chamar `POST /auth/logout` no backend antes de limpar o storage no client; resolver dependência de blacklist em memória para ambientes multi-workers.
- [ ] **Infraestrutura (DB - High):** Remover o rewrite silencioso da configuração de `DATABASE_URL` para SQLite em ambiente de desenvolvimento. O sistema deve validar e respeitar a URL informada.
- [ ] **Confiabilidade (Uploads - High):** Interromper o fluxo de criação da pane quando ocorrer falha no envio do anexo, checando corretamente o status da resposta HTTP no frontend ou criando um fluxo transacional único.
- [ ] **Segurança (Token - Medium):** Migrar a autenticação do frontend que hoje usa `localStorage` explícito para Cookies com `HttpOnly` e `SameSite`, bloqueando o acesso direto às proteções de rotas via navegador.
- [x] **Documentação (Docs - Medium):** Atualizar documentação principal e a documentação da API, removendo defasagens de papéis descontinuados, ajustando referências históricas para `archives` e limpando artefatos mortos.
- [ ] **Manutenção (Code Cleanup - Low):** Excluir esquemas (`LoginRequest`), imports mortos (`IntegrityError`) e código/métodos que não estão conectados à API ou à interface.

---

## ✅ v1.x – Estabilização e Refinamento (Atual)
*Foco: Usabilidade Web, Performance e Segurança.*
- [x] **v1.0.0**: Lançamento estável com CRUD de Panes, Frota e Efetivo.
- [x] **v1.1.0**: Implementação de Soft Delete de usuários e Interface de Intervenção Direta.
- [ ] **v1.2.0**: Exportação de dados (CSV/Excel) e melhoria nos filtros de busca global.

---

## 📱 v2.0 – Mobilidade e Hangar (The Hangar Version)
*Objetivo: Levar o sistema para debaixo da asa da aeronave.*

- **PWA (Progressive Web App)**: Interface instalável em tablets e celulares com suporte a **Modo Offline** para hangares sem Wi-Fi estável.
- **Scanner de QR Code**: Identificação instantânea de aeronaves e caixas pretas via câmera do dispositivo.
- **Gestão de Evidências Pro**: Upload múltiplo de fotos com ferramentas de anotação (desenhar círculos em falhas físicas) diretamente na imagem.
- **Geolocalização de Panes**: Registro automático da posição da aeronave no pátio ou hangar no momento da abertura.

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
- **Módulo de Inspeção**: Checklist digital de inspeções programadas integrado ao histórico de panes não-programadas.

---

## 🌐 v5.0 – Ecossistema e Autonomia (The Enterprise Version)
*Objetivo: Manutenção preditiva e integração total da cadeia logística.*

- **IA Preditiva**: Algoritmo que prevê a probabilidade de falha de um componente baseando-se no histórico de telemetria e voo.
- **Pedigree Total do Componente**: Histórico completo de cada S/N, rastreando por quais aeronaves passou e quais intervenções sofreu desde a incorporação.
- **Supply Chain Integration**: Comunicação automática com sistemas logísticos superiores para solicitação de compra/suprimento ao atingir estoque mínimo.
- **Real-Time Readiness**: Painel de prontidão tática em tempo real para o comando, exibindo a capacidade de geração de esforço aéreo baseada na saúde da frota.

---

## 🏁 Critérios de Sucesso da Evolução

| Versão | Meta Principal |
|--------|----------------|
| **v2.0** | Redução do tempo de digitação no hangar em 50%. |
| **v3.0** | Identificação de 100% das falhas repetitivas via sistema. |
| **v4.0** | Redução de 90% no uso de papel para registros técnicos. |
| **v5.0** | Aumento da disponibilidade média da frota em 15% via predição. |

---
*Uso interno – Força Aérea Brasileira.*
