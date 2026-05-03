# Definition of Done (DoD) – SAA29

A **Definition of Done** define os critérios que **toda** entrega deve satisfazer antes de ser considerada concluída. Uma história, tarefa ou PR que não atenda a **todos** os itens abaixo **não está pronto**.

---

## Critérios Obrigatórios

### ✅ Código
- [ ] O código implementa completamente o comportamento descrito na história/tarefa
- [ ] Nenhum `raise NotImplementedError` ou `# TODO` pendente no escopo da entrega
- [ ] Sem `print()` de debug ou código comentado desnecessário
- [ ] Sem credenciais, chaves ou dados sensíveis no código

### ✅ Testes
- [ ] Testes escritos **antes** do código (TDD)
- [ ] Todos os testes do módulo passam: `pytest tests/test_<modulo>.py -v`
- [ ] Cobertura do módulo ≥ **80%**: `pytest --cov=app/<modulo>`
- [ ] Casos de erro e edge cases cobertos (não apenas o happy path)

### ✅ Qualidade de Código
- [ ] Sem erros de linter: `ruff check app/`
- [ ] Sem erros de tipagem: `mypy app/`
- [ ] Funções com ≤ 20 linhas de lógica (exceto casos justificados)
- [ ] Nenhuma função com mais de 3 níveis de indentação sem refatoração

### ✅ Documentação
- [ ] Docstrings em todos os métodos públicos de `service.py`
- [ ] Docstring atualizada se o comportamento de um método existente mudou
- [ ] `CHANGELOG.md` atualizado na seção `[Unreleased]`

### ✅ Banco de Dados
- [ ] Se houver mudança de model: migração gerada via `alembic revision --autogenerate`
- [ ] A migração foi revisada manualmente antes de aplicar
- [ ] `alembic upgrade head` executa sem erros

### ✅ Processo
- [ ] PR revisado por pelo menos **um** membro da equipe
- [ ] Sem conflitos de merge com `main`
- [ ] Branch nomeada seguindo a convenção de `CONTRIBUTING.md`
- [ ] Commit com mensagem no padrão Conventional Commits

---

## Exceções

Itens podem ser marcados como **deferidos** somente se:
1. Documentados em comentário `# DEFER:` no código com justificativa
2. Registrados como tarefa no backlog antes de fechar o PR
3. Aprovados explicitamente pelo responsável técnico

---

> **Lembre-se:** "Pronto" significa que qualquer membro da equipe pode pegar o código e continuar sem surpresas.
