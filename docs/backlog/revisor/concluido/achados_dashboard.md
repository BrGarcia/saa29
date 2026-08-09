# Achados de Revisão — Módulo `dashboard`

> Revisão conforme `docs/backlog/revisor.md`, com contexto de `docs/backlog/00_mapa_arquitetural.md`.
> Nenhum arquivo de código foi alterado nesta sessão de revisão.

> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — 04/08/2026
> 5/7 corrigidos, 2 não corrigidos por decisão consciente (RISCO-02, escopo cross-module fora
> desta sessão — decisão tomada com o usuário durante a correção; RISCO-06, aberto/bloqueado por
> ADR de timezone pendente, conforme resposta do desenvolvedor). Commit `ca019ad`. Suite completa:
> 414 testes, 0 falhas (14 novos em `tests/unit/test_dashboard.py`). Os novos testes de
> `Instalacao` precisaram ser escritos à prova do vazamento de isolamento já documentado em
> `tests/unit/test_panes_alta_prioridade.py` (banco in-memory compartilhado pela sessão inteira +
> `db.commit()` explícito em `tests/architecture/test_performance_audit.py`) — nunca assumem
> banco vazio, sempre filtram pela matrícula única da própria aeronave do teste. Status por item
> marcado inline em cada achado abaixo (campo `**Status:**`).

---

### [BUG-01] Comparação string × UUID faz o dashboard nunca marcar aeronave com pane aberta como indisponível

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/dashboard/service.py:211-221,234-242`
- **Eixo:** Contrato
- **Problema:** `get_frota_summary` monta dois conjuntos de aeronaves para calcular o status exibido:
  - `inspecoes_ativas` (linha 211-214): `{str(id_) for id_ in (await db.execute(q_insp)).scalars().all()}` — um `set[str]`.
  - `panes_ativas` (linha 217-221): `set((await db.execute(q_panes)).scalars().all())` — um `set[uuid.UUID]`, **sem** conversão para string.

  Na hierarquia de status (linha 240-242), a variável usada para checar as duas listas é `ac_id_str = str(a.id)` (linha 235), uma string. `ac_id_str in inspecoes_ativas` funciona (ambos strings), mas `ac_id_str in panes_ativas` compara uma `str` contra um `set[uuid.UUID]` — nunca é `True`, mesmo quando a aeronave tem exatamente essa pane aberta. O comentário na linha 234 ("Forçar string para comparação de ID — garante compatibilidade UUID vs UUID") mostra que o ajuste foi feito para o lado de `inspecoes_ativas`, mas o mesmo tratamento não foi replicado para `panes_ativas`.
- **Consequência:** o ramal `elif ac_id_str in panes_ativas and status_final not in [...]:  status_final = "INDISPONIVEL"` (linha 242) é código morto — nunca executa. Uma aeronave com pane `ABERTA` continua aparecendo no `/dashboard/resumo` com o status base do banco (tipicamente `DISPONIVEL`), enquanto `panes.service.sincronizar_status_aeronave` (a lógica canônica, já documentada no mapa §4) de fato atualiza `aeronaves.status` para `INDISPONIVEL` no banco em outros fluxos — ou seja, o dashboard e o restante do sistema podem discordar sobre a mesma aeronave. Existe `test_frota_summary_override_status_inspecao_ativa` cobrindo o caso de inspeção, mas nenhum teste equivalente para pane aberta — por isso o bug não foi pego.
- **Correção proposta:** trocar `panes_ativas = set(...)` por `panes_ativas = {str(id_) for id_ in (await db.execute(q_panes)).scalars().all()}`, no mesmo padrão já usado para `inspecoes_ativas`.
- **Risco de regressão:** BAIXO — corrige um ramal hoje inalcançável; nenhum teste depende do comportamento errado.
- **Precisa de teste antes?** SIM — `test_frota_summary_override_status_pane_aberta` (equivalente ao teste de inspeção já existente).
- **Status:** ✅ CORRIGIDO exatamente como proposto. `panes_ativas` agora é `{str(id_) for id_ in ...}`. Teste: `test_frota_summary_override_status_pane_aberta`.

---

### [RISCO-02] Quarta reimplementação da regra "status de frota derivado de panes/inspeções ativas"

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/dashboard/service.py:200-261`
- **Eixo:** Arquitetura
- **Problema:** `get_frota_summary` reimplementa, com sua própria hierarquia de prioridades (`INSPEÇÃO` > `INDISPONIVEL` por pane > status base), a mesma regra de negócio que já existe em `panes.service.sincronizar_status_aeronave` (a versão canônica, segundo o mapa §4) e que já teve duas outras cópias documentadas e corrigidas em `docs/backlog/revisor/concluido/achados_panes.md` (MELHORIA-06) e `docs/backlog/revisor/concluido/achados_aeronaves.md` (BUG-02/RISCO-03). Esta é a quarta versão da mesma lógica, com um conjunto de exclusões próprio (`status_final not in ["INSPEÇÃO", "INSPECAO", "INATIVA", "ESTOCADA"]`, linha 242) que não considera `status_anterior_inativacao` (campo adicionado especificamente para o fluxo de reativação, ver `aeronaves/models.py:74-78`).
- **Consequência:** o card de frota do `/dashboard/resumo` pode discordar do `GET /aeronaves/` sobre o status de uma mesma aeronave em cenários de borda (ex. aeronave recém-reativada), porque cada endpoint deriva o status "ao vivo" com uma implementação diferente da mesma regra, em vez de uma fonte única.
- **Correção proposta:** extrair a lógica de derivação de status (pane aberta / inspeção ativa / status base) para uma função compartilhada — reaproveitável por `dashboard`, `aeronaves` e qualquer outro consumidor — em vez de reimplementá-la a cada módulo que precisa exibir status "ao vivo".
- **Risco de regressão:** MÉDIO — mexe em lógica usada por um endpoint de leitura consumido pela tela principal do sistema; precisa de testes de regressão para todos os status possíveis antes de consolidar.
- **Precisa de teste antes?** SIM.
- **Status:** 🚫 NÃO CORRIGIDO nesta sessão — decisão consciente, confirmada com o usuário. A correção proposta exigiria tocar 3 módulos (2 com sessão de revisão já concluída) e contraria o princípio hoje documentado no próprio `dashboard/service.py` ("não chama services de outros módulos"), o que tornaria essa extração uma decisão de arquitetura própria, não uma correção pontual deste achado. O sintoma imediato (divergência de status pane-aberta) já é coberto pelo BUG-01. Fica como risco documentado e follow-up cross-module.

---

### [MELHORIA-03] `PaneCritica.sistema` na verdade é a descrição truncada, não o sistema ATA — e o eager-load do sistema é descartado

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/dashboard/service.py:71-91`; `app/modules/dashboard/schemas.py:10-14`
- **Eixo:** Contrato
- **Problema:** o campo `PaneCritica.sistema` (schema, "Resumo de uma pane aberta") é preenchido em `service.py:87` com `p.descricao[:40] + ("..." if len(p.descricao) > 40 else "")` — os primeiros 40 caracteres da descrição livre da pane, não o nome do sistema ATA da aeronave. A query em `q_criticas` (linha 71-80) faz `selectinload(Pane.sistema_ata)` explicitamente, mas `p.sistema_ata` nunca é lido no list comprehension (linhas 83-91) — é uma query extra (`sistemas_ata` via join) carregada e descartada em toda chamada de `get_panes_summary`.
- **Consequência:** o nome do campo (`sistema`) mente sobre o conteúdo (anti-padrão #10 do `revisor.md`) — qualquer consumidor do card "panes críticas" que espere ver o sistema ATA da pane (ex. "Aviônicos", "Trem de pouso") vê, em vez disso, um trecho arbitrário da descrição textual; e há uma query desnecessária a cada chamada.
- **Correção proposta:** usar `p.sistema_ata.nome` (ou campo equivalente) para preencher `sistema`, aproveitando o `selectinload` já presente — ou remover o `selectinload` se a descrição truncada for o comportamento desejado e renomear o campo para refletir isso (ex. `resumo`).
- **Risco de regressão:** BAIXO — é um campo de exibição, sem uso em lógica de negócio identificado.
- **Precisa de teste antes?** SIM, se o valor do campo mudar (testes existentes de dashboard não verificam o conteúdo de `sistema`, só a presença de `matricula`).
- **Status:** ✅ CORRIGIDO (opção a, com fallback). `sistema` usa `p.sistema_ata.descricao` quando a pane tem sistema ATA associado (aproveitando o `selectinload` já existente); cai para a descrição truncada só quando `sistema_ata_id` é nulo, preservando o comportamento anterior nesse caso em vez de quebrar a UI para panes sem sistema cadastrado. Testes: `test_pane_critica_sistema_usa_sistema_ata_quando_presente`, `test_pane_critica_sistema_usa_descricao_truncada_sem_sistema_ata`.

---

### [MELHORIA-04] Docstring desatualizada: "movimentações recentes" não filtra instalações já removidas

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/dashboard/service.py:160-193`
- **Eixo:** Contrato
- **Problema:** a docstring de `get_movimentacoes_recentes` (linhas 163-164) afirma: *"Nota: A tabela `instalacoes` registra apenas instalações — não remoções."* Isso deixou de ser verdade desde a migração `migrations/versions/20260802_1030_e7a1c3d9b2f4_add_removido_em_to_instalacoes.py`, que adicionou `Instalacao.removido_em` — campo que `equipamentos/service.py:558` grava (`instalacao.removido_em = func.now()`) na **mesma linha** ao remover um item de um slot, sem criar registro novo. A query desta função (linhas 165-174) não filtra `Instalacao.removido_em.is_(None)` nem exibe a remoção como evento distinto — ela ordena por `created_at` (data da instalação original), então uma instalação removida há muito tempo pode nunca aparecer como "recente" mesmo tendo sido desfeita ontem, e uma instalação recém-criada e já removida no mesmo dia aparece no feed como se ainda estivesse ativa (o `descricao` não indica remoção).
- **Consequência:** o mini-feed "Movimentações Recentes" do dashboard pode exibir instalações que já foram desfeitas como se fossem eventos ativos recentes, e não reflete remoções recentes como eventos próprios — informação operacional enganosa para quem consulta o card. Comentário desatualizado também induz o próximo desenvolvedor a erro (anti-padrão #2 do `revisor.md`).
- **Correção proposta:** decidir explicitamente o comportamento — (a) filtrar `removido_em.is_(None)` para mostrar só instalações ativas, ou (b) incluir remoções como eventos próprios no feed (usando `removido_em` como data de ordenação quando presente, como já faz `equipamentos/service.py:418`) — e atualizar a docstring para refletir a decisão.
- **Risco de regressão:** BAIXO — é um card informativo, sem uso em lógica de negócio.
- **Precisa de teste antes?** SIM, se o comportamento mudar.
- **Status:** ✅ CORRIGIDO (opção b, conforme resposta do desenvolvedor). `get_movimentacoes_recentes` agora consulta instalações recentes (`created_at`) e remoções recentes (`removido_em`) separadamente, gera um `MovimentacaoRecente` distinto para cada evento (novo campo `tipo`: `INSTALACAO`/`REMOCAO`, schema em `dashboard/schemas.py`), combina e reordena pela data real de cada evento, e retorna os 5 mais recentes. Frontend (`app/web/static/js/dashboard.js`) atualizado para usar `tipo` no ícone do feed (📥/📤). Docstring corrigida. Testes: `test_movimentacoes_recentes_instalacao_ativa_aparece_como_instalacao`, `test_movimentacoes_recentes_remocao_aparece_como_evento_distinto`, `test_movimentacoes_recentes_remocao_de_instalacao_antiga_ainda_aparece_no_feed`.

---

### [MELHORIA-05] Imports não usados e comparação de status inalcançável

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/dashboard/service.py:12-25,206-208,242`
- **Eixo:** Arquitetura
- **Problema:** três achados menores no mesmo arquivo: (1) `date` (linha 12), `monthrange` (linha 13), `case` (linha 15), `ModeloEquipamento` e `SlotInventario` (linha 23) são importados no topo do módulo e nunca usados em nenhuma função — confirmado por grep no arquivo inteiro. (2) `get_frota_summary` reimporta `Inspecao` e `Pane` localmente (linhas 207-208), sombreando os imports já feitos no topo do arquivo (linhas 21 e 19) sem necessidade — não há ciclo de import a justificar o import tardio aqui (diferente do padrão documentado no mapa §4 para `aeronaves ↔ inspecoes ↔ panes`). (3) a lista de exclusão `status_final not in ["INSPEÇÃO", "INSPECAO", "INATIVA", "ESTOCADA"]` (linha 242) inclui a variante sem cedilha `"INSPECAO"`, que nunca ocorre na prática — `Aeronave.status` é `Mapped[StatusAeronave]` com `Enum(StatusAeronave, ...)` (`aeronaves/models.py:68-72`), e o único valor do enum para esse estado é `StatusAeronave.INSPECAO.value == "INSPEÇÃO"` (com cedilha, `enums.py:63`); a variante sem acento nunca é gravada no banco por este caminho.
- **Consequência:** nenhuma funcional — é ruído de manutenção (imports mortos dificultam entender dependências reais do arquivo; branch inalcançável é código morto, anti-padrão #9).
- **Correção proposta:** remover os imports não usados; remover o reimport local redundante de `Inspecao`/`Pane`; remover `"INSPECAO"` da lista de exclusão (ou documentar por que está lá, se for defesa contra dado legado).
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO.
- **Status:** ✅ CORRIGIDO, os três pontos. Imports não usados (`date`, `monthrange`, `case`, `ModeloEquipamento`, `SlotInventario`) removidos; reimport local de `Inspecao`/`Pane` em `get_frota_summary` removido (usa os imports do topo do arquivo); `"INSPECAO"` (sem cedilha) removido da lista de exclusão. Sem teste novo — comportamento inalterado, coberto pelos testes de frota já existentes.

---

### [RISCO-06] "Mês corrente" calculado em UTC quando a operação é em fuso local

- **Classificação:** RISCO
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/dashboard/service.py:37-40`
- **Eixo:** Banco
- **Problema:** `_inicio_mes_atual()` usa `datetime.now(timezone.utc).replace(day=1, ...)` para definir o início do mês corrente, usado no filtro `Pane.data_conclusao >= inicio_mes` de `get_panes_summary`. Se a operação real é em um fuso diferente de UTC (ex. UTC−3, padrão Brasil), nas primeiras horas de cada mês em horário local (que ainda são o mês anterior em UTC, ou vice-versa dependendo da direção) a contagem "resolvidas no mês corrente" fica alinhada ao calendário UTC, não ao calendário local da unidade.
- **Consequência:** no card "Panes resolvidas no mês", números levemente errados durante uma janela de poucas horas na virada de cada mês. Mesmo eixo de risco já deixado explicitamente em aberto (pendente de decisão de infraestrutura) em `docs/backlog/revisor/concluido/achados_vencimentos.md` — vale cruzar as duas decisões para não corrigir de forma divergente em cada módulo.
- **Correção proposta:** não corrigir isoladamente aqui — aguardar a decisão de timezone canônico já registrada como pendente em `achados_vencimentos.md`, e aplicar de forma consistente a todos os módulos que hoje ancoram cálculos de "período corrente" em UTC.
- **Risco de regressão:** BAIXO, mas é uma decisão transversal, não local a este módulo.
- **Precisa de teste antes?** SIM, quando a decisão de timezone for tomada.
- **Status:** 🚫 NÃO CORRIGIDO — conforme a resposta detalhada do desenvolvedor (ver seção de perguntas), a pendência é reformulada como ADR de aplicação (timezone canônico via `ZoneInfo` + utilitário único, precedida de auditoria dos tipos de coluna de data), com prioridade para `vencimentos` primeiro (regra de negócio) e RISCO-06 explicitamente aberto/bloqueado, não aceito, até a ADR. Nenhuma mudança de código feita aqui nesta sessão — o item "liberado já" da resposta (centralizar cálculos de período em `app/core/tempo.py` + lint) é trabalho cross-module que abrange `vencimentos` e outros consumidores, fora do escopo de uma correção pontual do módulo `dashboard`.

---

### [MELHORIA-07] `get_movimentacoes_recentes` sem nenhum teste; `get_inspecoes_ativas` roda sem `limit`

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/dashboard/service.py:126-153,160-193`; `tests/unit/test_dashboard.py`
- **Eixo:** Testes
- **Problema:** `tests/unit/test_dashboard.py` cobre `get_panes_summary`, `get_vencimentos_summary`, `get_inspecoes_ativas` e `get_frota_summary` com testes específicos, mas não existe nenhum teste para `get_movimentacoes_recentes` — nem para o caminho feliz, nem para os campos derivados (`nome_equip`, `slot_nome`, `matricula`). Adicionalmente, `get_inspecoes_ativas` (linha 126-153) não aplica `.limit(...)` na query, diferente de `get_panes_summary` (`.limit(5)`) e `get_movimentacoes_recentes` (`.limit(5)`) — não há teste que garanta um teto de itens retornados para inspeções ativas, e o card correspondente no dashboard pode crescer sem limite conforme o número de inspeções abertas aumenta.
- **Consequência:** o MELHORIA-04 acima (docstring desatualizada sobre remoções) não foi pego justamente por não haver teste cobrindo esse caminho — checklist **G** do `revisor.md` ("ausência de teste para as regras de negócio críticas do módulo").
- **Correção proposta:** adicionar testes para `get_movimentacoes_recentes` (incluindo o cenário de instalação removida, uma vez resolvido o MELHORIA-04); avaliar se `get_inspecoes_ativas` deveria ter um `.limit(...)` como as demais agregações do dashboard.
- **Risco de regressão:** BAIXO — é adição de teste e, possivelmente, um `.limit()`.
- **Precisa de teste antes?** — (é o próprio item de teste faltante).
- **Status:** ✅ CORRIGIDO. `get_inspecoes_ativas` ganhou `.limit(5)`, alinhado com as demais agregações do card. `tests/unit/test_dashboard.py` ganhou 4 testes para `get_movimentacoes_recentes` (instalação ativa, remoção como evento distinto, remoção de instalação antiga ainda visível, teto de 5 itens) e 1 para o novo limite de `get_inspecoes_ativas`. Os testes de `Instalacao` precisaram ser escritos à prova do vazamento de isolamento entre arquivos de teste já documentado em `test_panes_alta_prioridade.py` (ver banner no topo deste documento) — nunca assumem banco vazio, sempre filtram pela matrícula única da própria aeronave do teste.

---

## Resumo

- Total de achados: 7
- BUG: 1 (CRÍTICA: 0, ALTA: 1, MÉDIA: 0, BAIXA: 0)
- RISCO: 2
- MELHORIA: 4
- DÚVIDA: 0
- **Corrigidos: 5/7** — 2 não corrigidos por decisão consciente: RISCO-02 (escopo cross-module,
  decisão tomada com o usuário nesta sessão) e RISCO-06 (aberto/bloqueado por ADR de timezone
  pendente, conforme resposta do desenvolvedor)

## Arquivos revisados

- `app/modules/dashboard/service.py`
- `app/modules/dashboard/router.py`
- `app/modules/dashboard/schemas.py`
- `tests/unit/test_dashboard.py`
- `app/modules/aeronaves/models.py` (para confirmar o enum `StatusAeronave` usado em `Aeronave.status`)
- `app/modules/equipamentos/models.py` e trechos de `app/modules/equipamentos/service.py` (para confirmar a semântica de `Instalacao.removido_em`)
- `app/shared/core/enums.py`

## Não revisado / limitações

- Rate limiting: o único endpoint do módulo (`GET /dashboard/resumo`) não tem `@limiter.limit(...)` — não é achado isolado, é o padrão de 116 dos 117 endpoints do sistema (mapa §5/§7.5), citado só para registro.
- Ausência de camada `repositories/`: idem, padrão de 100% dos módulos (mapa §1).
- O consumo do payload pelo front-end (`app/web/static/js/dashboard.js`) foi lido apenas para confirmar o formato esperado de `frota.aeronaves` e `panes_criticas.sistema`, não em profundidade.
- Não foi avaliado o impacto de performance de `get_dashboard_resumo` executar 5 agregações sequenciais (`await` em série, `service.py:273-277`) em vez de paralelas (`asyncio.gather`) — checklist **A** não aponta bloqueio de I/O, mas é uma oportunidade de latência não quantificada nesta sessão (fora do escopo por exigir medição prévia, conforme `revisor.md` §9).

## Perguntas para o desenvolvedor (respondidas)

- **MELHORIA-04:** para o feed "Movimentações Recentes", instalações removidas devem ser (a) ocultadas, ou (b) exibidas como um evento distinto de remoção? A resposta muda a correção e o teste a escrever. **Resposta: (b) exibidas como um evento distinto de remoção.** Implementado.
- **RISCO-06:** existe uma decisão de timezone canônico pendente (já levantada em `achados_vencimentos.md`)? Se sim, aplicar aqui também quando for decidida.
    **Resposta:** sim, existe a pendência, mas ela precisa ser reformulada antes de ser aplicada aqui.
    Os dois achados compartilham o eixo, não o defeito: vencimentos usa date.today() (timezone ambiente, indefinido) e dashboard usa datetime.now(timezone.utc) (UTC fixo). Consequência não registrada até agora: os módulos coincidem apenas porque o container roda em UTC. Uma alteração de TZ no deploy, sem nenhuma mudança de código, faz os dois divergirem entre si em silêncio.

    Encaminhamento:
    A pendência deixa de ser tratada como "decisão de infraestrutura". Definir TZ no servidor não afeta os datetime.now(timezone.utc) explícitos — não resolve. A decisão é de aplicação: timezone canônico em configuração (ZoneInfo, não offset fixo) + utilitário único. Vira ADR com dono e prazo.
    Precede a decisão: auditar os tipos das colunas de data. timestamptz é corrigível depois; date/timestamp naive gravou a ambiguidade no write e não tem correção retroativa. Isso define o escopo real.
    Liberado já, sem depender da ADR: centralizar os cálculos de período em app/core/tempo.py preservando o comportamento atual de cada chamador, e adicionar regra de lint proibindo date.today() / datetime.now() sem timezone. Sem mudança funcional.
    Prioridade entre os dois: vencimentos primeiro. Ali o erro de borda decide se um item está vencido — regra de negócio. RISCO-06 é card informativo e permanece BAIXA.
    RISCO-06 fica aberto/bloqueado pela ADR, não aceito. Testes de borda com relógio congelado (último dia 23h e primeiro dia 00h locais) entram junto com a aplicação. <fim da resposta>

    Nenhuma mudança de código feita aqui: o item "liberado já" da resposta (centralizar
    `app/core/tempo.py` + lint) é trabalho cross-module que não se limita ao `dashboard`, e a
    prioridade explícita do desenvolvedor é `vencimentos` primeiro.
- **RISCO-02** (não estava na lista original de perguntas, levantada durante esta sessão de
  correção): extrair a lógica de derivação de status para uma função compartilhada agora, ou
  deixar como risco documentado? **Resposta: não corrigir agora** — é decisão de arquitetura
  cross-module (contraria o princípio "não chama services de outros módulos" hoje documentado no
  próprio `dashboard/service.py`), fora do escopo de uma correção pontual. BUG-01 já resolve o
  sintoma imediato de divergência.