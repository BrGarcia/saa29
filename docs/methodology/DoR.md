# Definition of Ready (DoR) – SAA29

A **Definition of Ready** define quando uma história ou tarefa está **pronta para ser iniciada**. Uma tarefa que não atenda aos critérios abaixo não deve entrar em desenvolvimento.

---

## Critérios de Prontidão

### ✅ Clareza
- [ ] A tarefa tem título claro e descrição objetiva
- [ ] O comportamento esperado está descrito (o que deve acontecer, não como)
- [ ] Os critérios de aceitação estão listados e são verificáveis
- [ ] Ambiguidades foram discutidas e resolvidas com o responsável

### ✅ Referências
- [ ] A tarefa referencia o(s) requisito(s) do SRS (RF-XX ou RN-XX) quando aplicável
- [ ] O algoritmo correspondente em `01_SPECS.md` foi lido pelo desenvolvedor
- [ ] O modelo de dados em `Database.md` foi revisado se envolver banco

### ✅ Tamanho
- [ ] A tarefa é realizável em **1 sessão de trabalho** (≤ 4 horas)
- [ ] Se maior, foi quebrada em subtarefas menores

### ✅ Dependências
- [ ] Dependências técnicas identificadas (ex: "precisa de `get_current_user` implementado")
- [ ] Dependências bloqueantes estão resolvidas ou há workaround definido

### ✅ Testes (Dia 3 – antes do Dia 4)
- [ ] O caso de teste correspondente **já existe** em `tests/test_<modulo>.py`
- [ ] O teste está falhando (expected behavior em TDD)

---

## Modelo de Tarefa

Ao criar uma tarefa, use este formato:

```markdown
## [MÓDULO] Título da tarefa

**RF/RN relacionado:** RF-07, RN-02
**Arquivo(s) alvo:** app/panes/service.py::criar_pane()

### Comportamento esperado
Descreva o que deve acontecer (não como implementar).

### Critérios de aceitação
- [ ] Critério verificável 1
- [ ] Critério verificável 2
- [ ] Teste `test_criar_pane_sucesso` passando

### Referências
- [SPECS.md §3 – Fluxo de Criação de Pane](../core/SPECS.md)
- [Database.md §2.9 – Panes](../architecture/Database.md)
```

---

> **Princípio:** Uma tarefa bem definida é metade da implementação.
