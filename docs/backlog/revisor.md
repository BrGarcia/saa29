# Planejamento de Revisão — SAA29

> Documento de referência para as sessões de revisão de código do backend FastAPI.
> Caminho no repositório: `docs/backlog/Fable5/Planejamento_revisao.md`

---

## 1. Objetivo

Revisar o código de `app/` em busca de **bugs**, **riscos** e **pontos de melhoria**, produzindo achados classificados e acionáveis que alimentarão um backlog de correções.

O projeto está funcional. O objetivo **não** é reescrevê-lo, e sim encontrar o que quebra sob carga, sob dados inesperados ou sob manutenção futura — problemas que não aparecem no caminho feliz.

---

## 2. Contexto do projeto

- **Stack:** Python + FastAPI (backend)
- **Código-fonte:** `app/`
- **Módulos funcionais:** `app/modules/` (`aeronaves`, `inspecoes`, `panes`, `auth`, entre outros), cada um com suas camadas de serviço e regras de negócio
- **Documentação e arquitetura:** `docs/` e `INICIO.MD`
- **Histórico relevante:** partes do código foram geradas por modelos de IA com desempenho limitado em Python. Espere inconsistências entre módulos, padrões misturados e erros que "funcionam" em desenvolvimento mas falham em produção.

---

## 3. Como usar este documento

Uma sessão de revisão = **um módulo** (ou um submódulo, se o módulo for grande).

1. Iniciar sessão limpa no Claude Code
2. `/model opusplan`
3. Entrar em **Plan Mode** (`Shift+Tab` duas vezes)
4. Prompt:
   > Leia `docs/backlog/00_mapa_arquitetural.md` e `docs/backlog/revisor.md`. Revise `app/modules/<MODULO>/` conforme as orientações deste último. Não altere nenhum arquivo. Salve os achados em `docs/backlog/revisor/achados_<MODULO>.md`.
5. Ao final, `/clear` antes do próximo módulo

**Ordem sugerida:** `auth` → módulos com escrita em banco → módulos de leitura/relatório.
Começar por `auth` porque falhas ali contaminam todos os outros módulos.

---

## 4. Regras de conduta durante a revisão

- **Não alterar nenhum arquivo** na fase de revisão. A revisão produz apenas o documento de achados.
- **Não propor reescrita completa** de módulos. Correções devem ser localizadas e justificadas.
- **Não propor troca de biblioteca ou framework** sem que o problema atual seja concreto e documentado.
- **Não sinalizar preferência de estilo como achado.** Se o `ruff` não reclama e o código é legível, não é achado.
- **Todo achado precisa de arquivo, linha e justificativa.** "Poderia ser melhor" sem consequência descrita não entra.
- **Se algo parecer errado mas o comportamento for intencional**, marcar como `DÚVIDA` em vez de `BUG` e perguntar.

---

## 5. Formato obrigatório de saída

Cada achado no arquivo `achados_<MODULO>.md` segue este template:

```markdown
### [BUG-01] Título curto e descritivo

- **Classificação:** BUG | RISCO | MELHORIA | DÚVIDA
- **Severidade:** CRÍTICA | ALTA | MÉDIA | BAIXA
- **Arquivo:** `app/modules/<modulo>/services/exemplo.py:142`
- **Eixo:** Concorrência / Banco / Segurança / Contrato / Arquitetura / Testes
- **Problema:** o que está errado, em uma ou duas frases.
- **Consequência:** o que acontece na prática quando isso for exercitado.
- **Correção proposta:** o que fazer, sem escrever o código ainda.
- **Risco de regressão:** BAIXO | MÉDIO | ALTO — o que pode quebrar ao corrigir.
- **Precisa de teste antes?** SIM | NÃO
```

**Definições de classificação:**

| Classe | Significado |
|---|---|
| `BUG` | Comportamento incorreto, demonstrável. Existe entrada que produz resultado errado, exceção ou corrupção de dado. |
| `RISCO` | Não está errado hoje, mas falha sob carga, concorrência, dado inesperado ou é vetor de segurança. |
| `MELHORIA` | Funciona e é seguro, mas dificulta manutenção ou diverge do padrão dos outros módulos. |
| `DÚVIDA` | Parece errado, mas pode ser decisão de negócio deliberada. Requer confirmação humana. |

**Severidade CRÍTICA** reservada para: perda ou corrupção de dados, falha de autenticação/autorização, exposição de segredo, indisponibilidade do serviço.

---

## 6. Checklist de revisão

### A. Concorrência e async (prioridade máxima em FastAPI)

Este é o eixo onde código gerado por IA fraca mais erra, e onde os erros **não aparecem em desenvolvimento**.

- [ ] Endpoints declarados `async def` que executam **I/O bloqueante** — `requests`, `time.sleep`, `open()`, driver de banco síncrono, chamada a subprocesso. Isso trava o event loop inteiro, não só a requisição.
- [ ] Uso de ORM síncrono (SQLAlchemy sessão padrão) dentro de rota `async`. Se o projeto é síncrono, o correto é `def` puro — o FastAPI então roda em threadpool.
- [ ] Mistura de `def` e `async def` sem critério entre endpoints do mesmo módulo.
- [ ] `await` faltando em coroutine (a chamada retorna a coroutine e o código segue silenciosamente).
- [ ] Estado mutável global ou de módulo compartilhado entre requisições (dicionários de cache, listas, contadores).
- [ ] Operações de leitura-depois-escrita sem lock ou sem transação — condição de corrida em contadores, numeração sequencial, checagem de disponibilidade.
- [ ] `BackgroundTasks` ou tarefas assíncronas cujo erro é engolido sem log.

### B. Banco de dados e persistência

- [ ] Sessão de banco obtida fora de dependência do FastAPI, ou não fechada em caminho de exceção.
- [ ] Ausência de `commit`/`rollback` explícito, ou `commit` dentro de laço.
- [ ] **N+1 queries** — acesso a relacionamento dentro de laço sem `joinedload`/`selectinload`.
- [ ] Query construída por concatenação de string com input do usuário (SQL injection).
- [ ] Operações que deveriam ser atômicas divididas em múltiplas transações.
- [ ] Ausência de índice em coluna usada em filtro frequente ou em chave estrangeira.
- [ ] Deleção sem verificação de integridade referencial, ou cascade não intencional.
- [ ] Migrações (Alembic ou equivalente) fora de sincronia com os modelos declarados.
- [ ] Campos de data/hora sem timezone, ou mistura de `datetime.now()` e `datetime.utcnow()`.
- [ ] Uso de `float` para valores monetários ou de precisão (deveria ser `Decimal`).

### C. Validação, contrato e Pydantic

- [ ] Mistura de Pydantic v1 e v2 no mesmo projeto (`@validator` vs `@field_validator`, `.dict()` vs `.model_dump()`, `orm_mode` vs `from_attributes`).
- [ ] Endpoint sem `response_model`, expondo o modelo do banco diretamente — vaza campos internos, hashes, IDs de terceiros.
- [ ] Schema de entrada e schema de saída sendo o mesmo objeto (permite ao cliente enviar campos que não deveria).
- [ ] Validadores declarados que não validam nada, ou que não levantam exceção.
- [ ] Uso de `Any`, `dict` ou `**kwargs` onde um schema tipado era possível.
- [ ] Campos opcionais sem valor default coerente, ou `Optional` usado como muleta para contornar validação.
- [ ] Códigos de status HTTP incorretos: `200` em criação (deveria ser `201`), `200` com corpo de erro, `500` para erro de validação.
- [ ] Paginação ausente em endpoints de listagem.

### D. Tratamento de erros

- [ ] `except Exception: pass` ou `except: pass` — engolimento silencioso.
- [ ] `except` amplo capturando o que deveria propagar.
- [ ] Exceção capturada e relançada perdendo o traceback original (falta `raise ... from e`).
- [ ] Mensagem de exceção interna (traceback, SQL, caminho de arquivo) devolvida ao cliente.
- [ ] Erro apenas `print()`ado em vez de logado.
- [ ] Ausência de tratamento para caminhos previsíveis: registro não encontrado, conflito de unicidade, timeout de serviço externo.

### E. Segurança e autorização

- [ ] Endpoint sem dependência de autenticação que deveria ter.
- [ ] Autenticação presente mas **autorização ausente**: usuário autenticado consegue acessar ou alterar recurso de outro (IDOR). Verificar se cada endpoint que recebe um ID confere a propriedade do recurso.
- [ ] Aplicação inconsistente da dependência de auth entre módulos — um módulo protege, outro esqueceu.
- [ ] Segredos, tokens, senhas ou strings de conexão hardcoded no código.
- [ ] Senha armazenada sem hash adequado, ou com algoritmo fraco.
- [ ] JWT sem verificação de expiração, sem validação de assinatura, ou com segredo default.
- [ ] CORS com `allow_origins=["*"]` combinado com credenciais.
- [ ] Upload de arquivo sem validação de tipo, tamanho ou nome (path traversal).
- [ ] Log gravando dado sensível (senha, token, CPF, dado pessoal).

### F. Arquitetura e camadas

- [ ] Regra de negócio dentro da função de rota em vez da camada de serviço.
- [ ] Camada de serviço importando objetos do FastAPI (`Request`, `HTTPException`, `Depends`) — acopla negócio ao transporte.
- [ ] Acesso direto ao ORM a partir da rota, pulando o serviço.
- [ ] Import circular, ou resolvido com import dentro de função sem comentário explicando.
- [ ] Lógica duplicada entre módulos que deveria estar em `app/core/` ou equivalente.
- [ ] Divergência de padrão entre módulos: comparar `aeronaves`, `inspecoes`, `panes` e `auth` e apontar onde fazem a mesma coisa de formas diferentes.
- [ ] Dependência entre módulos funcionais que deveria passar por uma interface.

### G. Testes

- [ ] Módulo sem nenhum teste (cruzar com a saída de `pytest --cov`).
- [ ] Teste que exercita apenas o caminho feliz.
- [ ] Teste que depende de estado deixado por outro teste, ou de ordem de execução.
- [ ] Teste que bate em banco ou serviço real em vez de fixture/mock.
- [ ] Ausência de teste para as regras de negócio críticas do módulo.
- [ ] Assert genérico (`assert result`) que passaria com quase qualquer retorno.

### H. Configuração e operação

- [ ] Configuração lida de `os.environ` espalhada pelo código em vez de centralizada em um objeto de settings.
- [ ] Ausência de valores default seguros, ou defaults que funcionam em dev e falham em produção sem aviso.
- [ ] `debug=True`, `reload=True` ou documentação `/docs` exposta sem controle em produção.
- [ ] Ausência de healthcheck.
- [ ] Logging sem nível configurável, ou usando `print`.
- [ ] Dependências sem versão fixada em `requirements.txt` / `pyproject.toml`.

---

## 7. Anti-padrões frequentes em código gerado por IA

Verificar explicitamente a presença destes, pois são comuns e passam despercebidos:

1. **Função que aceita `**kwargs` e repassa cegamente** — perde validação e mascara erros de digitação em nomes de parâmetro.
2. **Comentário que descreve algo que o código não faz** (a implementação mudou, o comentário não).
3. **Docstring genérica gerada automaticamente** que apenas repete o nome da função.
4. **Tratamento defensivo excessivo** — checagens de `None` em valores que nunca podem ser `None`, escondendo a real origem do problema.
5. **Reimplementação de algo que a stdlib ou o próprio FastAPI já oferece.**
6. **Mutable default argument** (`def f(itens=[])`).
7. **Variável de laço vazando para uso posterior**, ou reuso de nome de variável com tipo diferente.
8. **Conversão de tipo silenciosa** (`int(x)` sem tratar `ValueError`).
9. **Código morto**: função nunca chamada, import não usado, branch inalcançável.
10. **Nomes que mentem** — função chamada `get_*` que também escreve no banco.

---

## 8. Priorização dos achados

Na consolidação, ordenar por **impacto × probabilidade**, com estes desempates:

1. Segurança e autorização (qualquer severidade) vêm primeiro
2. Perda ou corrupção de dados
3. Bugs com caminho de reprodução conhecido
4. Riscos de concorrência e performance
5. Melhorias de arquitetura que desbloqueiam outras correções
6. Melhorias isoladas de manutenibilidade

Itens de **risco de regressão ALTO** devem ser marcados para: escrever teste primeiro, corrigir depois.

---

## 9. Fora de escopo desta revisão

- Reescrita de módulos funcionais
- Mudança de framework, ORM ou biblioteca de validação
- Refatoração puramente estética ou renomeação em massa
- Otimização de performance sem medição prévia que a justifique
- Alteração de contrato de API que quebre clientes existentes (se identificado que o contrato está errado, registrar como achado e sinalizar `BREAKING`)
- Adição de novas funcionalidades

---

## 10. Ao final de cada sessão

O documento `achados_<MODULO>.md` deve terminar com:

```markdown
## Resumo

- Total de achados: N
- BUG: n (CRÍTICA: n, ALTA: n, MÉDIA: n, BAIXA: n)
- RISCO: n
- MELHORIA: n
- DÚVIDA: n

## Arquivos revisados
- lista dos arquivos efetivamente lidos

## Não revisado / limitações
- o que ficou de fora e por quê (contexto insuficiente, dependência de outro módulo, etc.)

## Perguntas para o desenvolvedor
- itens marcados como DÚVIDA que precisam de decisão humana
```

---

## 11. Sinalização de status após correção

Diferente da sessão de revisão (que só produz o documento), uma sessão de **correção** que
implementa itens de um `achados_<MODULO>.md` **altera o próprio documento** para registrar o
resultado — sem precisar que o desenvolvedor peça. Isso mantém o achado e o desfecho no mesmo
lugar, em vez de um ledger separado que pode divergir do código real.

**Regra:** ao corrigir (ou decidir conscientemente não corrigir) um item, adicionar um campo
`- **Status:**` como última linha do bloco desse achado, antes do `---` de separação:

```markdown
- **Precisa de teste antes?** SIM | NÃO
- **Status:** ✅ CORRIGIDO — commit `<hash curto>`. <nota breve opcional: o que foi feito>
```

Valores possíveis:

| Status | Quando usar |
|---|---|
| `✅ CORRIGIDO` | Implementado e coberto por teste (quando o achado pedia teste). Citar o commit. |
| `⚠️ CORRIGIDO PARCIALMENTE` | Parte do achado foi endereçada; citar o commit e, em uma frase, o que ficou de fora e por quê. |
| `🚫 NÃO CORRIGIDO` | Decisão consciente de não corrigir nesta sessão — sempre com o motivo (decisão de produto pendente, fora de escopo, risco de regressão alto demais sem confirmação, etc.). Nunca deixar um item sem status por esquecimento. |
| `⏳ PENDENTE` | Documento ainda não passou por uma sessão de correção. É o estado implícito de um achado recém-criado — só é necessário escrever explicitamente se o documento já tem outros itens com status (para deixar claro que este não foi esquecido). |

Ao final da sessão de correção, atualizar também a seção `## Resumo` do documento com a
contagem de itens por status (ex.: `Corrigidos: 20/24 · Não corrigidos: 3 (decisão de produto)
· Parciais: 1`), no mesmo padrão da contagem por classificação já existente. Adicionar também um
banner logo abaixo do cabeçalho do documento (mesmo padrão de `docs/backlog/Fable5/relatorio_auth_seguranca.md`):

```markdown
> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — <DD/MM/AAAA>
> X/N achados corrigidos, Y parciais, Z não corrigidos por exigirem decisão de produto/desenvolvedor
> ou risco de regressão fora do escopo (ver `## Perguntas para o desenvolvedor` ao final). Commit
> `<hash curto>`. Suite completa: <N> testes, 0 falhas. Status por item marcado inline em cada
> achado abaixo (campo `**Status:**`).
```

**Não criar um documento de status separado** (ex. `status_<MODULO>.md`) para este propósito —
o objetivo é que `achados_<MODULO>.md` continue sendo a fonte única de verdade sobre cada item,
da descoberta à resolução.

**Mover para `docs/backlog/revisor/concluido/`:** depois de marcar o status de todo item do
documento (nenhum item sem campo `**Status:**`, mesmo que seja `🚫 NÃO CORRIGIDO`), mover o
arquivo com `git mv docs/backlog/revisor/achados_<MODULO>.md docs/backlog/revisor/concluido/`.
"Concluído" aqui significa que a sessão de correção processou todos os achados — não que 100%
foram corrigidos; itens `🚫`/`⚠️` documentados contam como processados. Depois de mover, corrigir
qualquer referência cruzada de outros `achados_<MODULO>.md` que apontem para o arquivo movido
(`grep -rl "achados_<MODULO>.md" docs/backlog/revisor/`), atualizando o caminho para incluir
`concluido/`.
