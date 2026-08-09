arquivo:
app/modules/panes/service.py

> ## ✅ DOCUMENTO FINALIZADO — 02/08/2026
> Todos os itens priorizados (Alta 6/6, Média 4/4, Baixa 7/7 — incluindo #21, cuja parte principal já
> saiu como efeito colateral do #34) foram corrigidos e verificados. Suíte completa final:
> **250 testes, 0 falhas**. Este relatório passa a ser registro histórico das decisões tomadas — inclui
> uma tentativa de otimização (#16 em `criar_pane`) que foi revertida por introduzir um bug real
> (`MissingGreenlet`), documentada como aprendizado para quem retomar o trabalho.

---

## 📌 Status de Execução (atualizado em 02/08/2026)

**Todos os itens do relatório foram corrigidos: Alta 6/6, Média 4/4, Baixa 7/7.**

| Item | Prioridade | Status | Onde |
|---|---|---|---|
| #9 editar_pane não sincroniza aeronave | 🔴 Alta | ✅ CORRIGIDO | `editar_pane` chama `_sincronizar_status_aeronave_pane` |
| #20 `_escape_like` sem `escape=` no `.like()` | 🔴 Alta | ✅ CORRIGIDO | `listar_panes`, 3 chamadas `.like(..., escape="\\")` |
| #5 Background não durável (anexos presos) | 🔴 Alta | ✅ MITIGADO | job `limpar_anexos_processando_antigos` (mínimo do relatório) |
| #34 Race exclusão × processamento background | 🔴 Alta | ✅ CORRIGIDO | `_atualizar_caminho_anexo_se_pendente` |
| #2 Race em `adicionar_responsavel`/`concluir_pane` | 🔴 Alta | ✅ CORRIGIDO | UNIQUE + SAVEPOINT + `IntegrityError` |
| #3 Race em `_sincronizar_status_aeronave_pane` | 🔴 Alta | ✅ CORRIGIDO | `db.get(..., with_for_update=True)` |
| #4 Anexo órfão no storage | 🟡 Média | ✅ CORRIGIDO | compensação no `upload_anexo`; ordem invertida em `excluir_anexo` |
| #28 `data_fim` exclui o último dia | 🟡 Média | ✅ CORRIGIDO | `< data_fim + timedelta(days=1)` |
| #31 Extensão × MIME incoerentes | 🟡 Média | ✅ CORRIGIDO | `_EXTENSAO_MIME_MAP` |
| #24 `ValueError` genérico | 🟡 Média | ✅ CORRIGIDO (escopo: editar/concluir) | exceções de domínio, sem string-matching |
| #6 Imports mortos / variável `pane` não usada | 🟢 Baixa | ✅ CORRIGIDO | `anyio`, `Path` removidos |
| #14 Subquery de ranking duplicada | 🟢 Baixa | ✅ CORRIGIDO | `_get_ranking_subquery(db)` compartilhada |
| #15 `count()` para checar existência | 🟢 Baixa | ✅ CORRIGIDO | `EXISTS` |
| #16 Excesso de `db.refresh` | 🟢 Baixa | ✅ CORRIGIDO parcialmente | só `concluir_pane`; `criar_pane` tentado e revertido (ver nota) |
| #18 `get_settings()` a cada chamada | 🟢 Baixa | ✅ CORRIGIDO | `db.bind.dialect.name` |
| #21 Duplicação em `processar_imagem_background` | 🟢 Baixa | ✅ CORRIGIDO | helper (via #34) + 3 sub-itens finalizados agora |
| #23 Variáveis `resultado → pane` | 🟢 Baixa | ✅ CORRIGIDO | 5 funções simplificadas |

**Arquivos alterados/criados (consolidado — todas as prioridades):**
- `app/modules/panes/service.py`, `models.py` (constraint UNIQUE em `PaneResponsavel`), `router.py`
- `app/bootstrap/tasks.py` (+ `anexos_travados_cleanup_task`), `events.py` (task agendada no lifespan)
- `migrations/versions/20260802_1130_f3c2b8a1d4e6_add_unique_pane_responsavel.py` (**aplicada em `var/db`**)
- `tests/unit/test_panes_alta_prioridade.py` (13 testes), `test_panes_media_prioridade.py` (12 testes),
  `test_panes_baixa_prioridade.py` (5 testes) — **30 testes novos no total**

**Suíte completa final:** `pytest tests/unit tests/architecture tests/test_calendario.py
tests/test_exporter.py` → **250 testes, 0 falhas**.

**Aviso para quem for mexer em `criar_pane` de novo:** não repita a tentativa de popular `anexos`/
`responsaveis` manualmente para evitar o `db.refresh()` final. Um objeto ORM recém-`flush()`ado deixa de
ser transient — suas coleções passam a exigir carregamento explícito, e acessá-las sem refresh estoura
`MissingGreenlet` em contexto assíncrono. Verifiquei isso com um teste direto antes de reverter (ver nota
do item #16 abaixo).

---

Relatorio:
Revisão de Código: app/panes/service.py
🔴 Bugs e Problemas Críticos
1. Race condition na validação de tamanho vs. leitura em memória

A validação de tamanho ocorre depois de o arquivo já estar completamente em memória (arquivo_bytes: bytes). Um upload de 5GB consumiria toda a RAM antes da validação.

# Problema: bytes já carregados em memória
max_bytes = settings.max_upload_size_mb * 1024 * 1024
if len(arquivo_bytes) > max_bytes:

Correção: validar Content-Length no router antes de ler o corpo, ou usar streaming com limite:

# No router, antes de chamar o service:
if request.headers.get("content-length") and int(...) > max_bytes:
    raise HTTPException(413)

Além disso, a validação de tamanho deveria vir antes da validação de MIME (fail-fast e mais barato).

2. Race condition em adicionar_responsavel e concluir_pane (TOCTOU)

A verificação de duplicidade e o INSERT não são atômicos:

if result.scalar_one_or_none():
    raise ValueError("Usuário já é responsável...")
# ⚠️ Outra requisição pode inserir aqui
db.add(responsavel)

Correção: adicionar constraint UNIQUE(pane_id, usuario_id) no modelo e tratar IntegrityError:

from sqlalchemy.exc import IntegrityError
try:
    db.add(responsavel)
    await db.flush()
except IntegrityError:
    raise ValueError("Usuário já é responsável por esta pane.")

O mesmo vale para o ranking row_number() — panes criadas simultaneamente podem gerar comportamento inesperado se data_abertura colidir (mitigado pelo tie-break com Pane.id, mas UUIDs não são ordenados cronologicamente — considere UUIDv7 ou timestamp de precisão).

> **✅ Correção aplicada:** `PaneResponsavel` ganhou `UniqueConstraint("pane_id", "usuario_id",
> name="uq_pane_responsavel_pane_usuario")` (migration `f3c2b8a1d4e6`, aplicada em `var/db` — 0 duplicatas
> encontradas na base antes de criar a constraint). Tanto `adicionar_responsavel` quanto o auto-add de
> responsável em `concluir_pane` agora envolvem o insert em `async with db.begin_nested()` (SAVEPOINT) e
> tratam `IntegrityError`: em `adicionar_responsavel` vira `ValueError` amigável (a checagem prévia foi
> extraída para `_ja_e_responsavel`, reaproveitada e monkeypatchável em teste); em `concluir_pane` o
> `IntegrityError` é apenas absorvido (`pass`), pois o objetivo ali é garantir que o usuário conste como
> responsável — se outra transação já o inseriu, o resultado desejado já foi alcançado.
> **Tie-break do ranking (UUID) não alterado:** está fora do escopo de alta prioridade; documentado aqui
> como pendência caso o volume de panes simultâneas cresça (mitigação: `Pane.id` como tie-break já existe).

3. Race condition em _sincronizar_status_aeronave_pane

Duas panes sendo resolvidas/criadas concorrentemente para a mesma aeronave podem gerar status inconsistente (lost update).

Correção: usar lock pessimista:

aeronave = await db.get(Aeronave, aeronave_id, with_for_update=True)

> **✅ Correção aplicada:** `_sincronizar_status_aeronave_pane` agora usa exatamente
> `await db.get(Aeronave, aeronave_id, with_for_update=True)` no lugar do import local de
> `aeronaves.service.buscar_aeronave`. **Nota de honestidade:** o backend atual é SQLite
> (`app/bootstrap/database.py`), cujo dialect compila `with_for_update` como no-op (verificado
> compilando o `SELECT` — sem cláusula `FOR UPDATE` gerada) — ou seja, a proteção real de exclusão mútua
> só passa a valer se/quando o projeto migrar para um banco que suporte locking de linha (ex.: PostgreSQL).
> Mantive a mudança porque (a) é exatamente a correção pedida pelo relatório, (b) é inofensiva no SQLite,
> e (c) documenta a intenção para quando a portabilidade for exercida — mas é importante não superestimar
> a proteção obtida agora.

4. Anexo órfão em caso de falha após upload (upload_anexo)

Se storage_svc.upload() tiver sucesso mas o db.flush() (ou o commit posterior) falhar, o arquivo fica órfão no storage sem registro no banco.

Correção: implementar compensação (deletar do storage em caso de exceção) ou padrão outbox:

caminho_salvo = await storage_svc.upload(...)
try:
    db.add(anexo)
    await db.flush()
except Exception:
    await storage_svc.delete(caminho_salvo)
    raise

O inverso ocorre em excluir_anexo: o arquivo é deletado do storage antes do commit do banco — se o commit falhar (rollback), o registro fica apontando para arquivo inexistente. Melhor: deletar do banco primeiro, e deletar do storage após o commit (ou tolerar falha no delete físico com log, sem levantar exceção).

> **✅ Correção aplicada — as duas frentes:**
> - `upload_anexo`: o `db.add(anexo)` + `db.flush()` agora está em `try/except Exception`; em caso de falha,
>   `storage_svc.delete(caminho_salvo)` roda antes de re-lançar, exatamente como sugerido.
> - `excluir_anexo`: ordem invertida — o registro é removido do banco **primeiro**; a exclusão física roda
>   depois e, se falhar (retorno `False` ou exceção), apenas loga um `logger.warning` em vez de levantar
>   `ValueError` (2ª alternativa do relatório, escolhida por não haver hook de "após o commit" disponível
>   dentro do escopo da função — o commit real acontece na dependência `get_db`, fora do service).
> **Regressão:** 3 testes — falha simulada no `flush()` aciona a compensação no storage; exclusão com
> falha simulada no storage ainda remove o registro do banco; caminho feliz continua removendo o arquivo.

5. processar_imagem_background recebe bytes grandes e pode perder dados

Se o processo reiniciar (deploy, crash) entre o registro do placeholder "processando" e a execução do background task, os bytes se perdem para sempre — o anexo fica eternamente como "processando". BackgroundTasks do FastAPI não é durável.

Correção: salvar o arquivo original no storage imediatamente e processar depois (substituindo), ou usar fila persistente (Celery/ARQ/RQ). No mínimo, criar job de limpeza para anexos "processando" antigos.

> **✅ Mitigação mínima aplicada (não é a correção definitiva):** implementei exatamente o "no mínimo"
> sugerido — `limpar_anexos_processando_antigos(db, minutos_limite=30)` marca como `ERRO` anexos presos em
> "processando" além do limite de tempo, chamada por `anexos_travados_cleanup_task` (novo, em
> `app/bootstrap/tasks.py`) a cada 15 minutos, agendada no `lifespan` (`app/bootstrap/events.py`).
> **Isso não recupera os bytes perdidos** — apenas destrava a UI (o anexo some do estado "processando"
> eterno e passa a exibir erro claro). A correção definitiva (salvar o original no storage antes de
> otimizar, ou fila durável) segue como dívida arquitetural registrada aqui, não implementada nesta rodada.

6. Import anyio não utilizado
import anyio  # nunca usado

Também: Path de pathlib importado e não usado; Aeronave importado no topo mas re-importado localmente dentro de listar_panes (redundante); uuid só é usado para type hints; pane capturado mas não usado em upload_anexo e adicionar_responsavel (variável pane/resultado desnecessária).

> **✅ Correção aplicada:** `import anyio` e `from pathlib import Path` removidos (nenhum dos dois era
> usado em `service.py` — `Path` é usado em `router.py`, arquivo diferente). O reimport local de
> `Aeronave` em `listar_panes` já havia sido removido durante a correção do item #20 (mesma região de
> código). `uuid` foi mantido — é genuinely usado nos type hints (`uuid.UUID`) por todo o módulo, não é
> código morto. A variável `pane` não usada em `upload_anexo` e `adicionar_responsavel` foi eliminada
> (ver nota do item #23, mesma correção).
> **⬜ Não verificado neste módulo:** `except ImportError` no lugar de `except Exception` na importação
> de `magic` — não estava listado nos itens priorizados (#6 cobre só os imports mortos citados acima).

7. Exceção capturada e ignorada silenciosamente (variável e não usada)
except Exception as e:
    from app.shared.core.file_validators import _detect_mime_type_fallback
    mime_real = _detect_mime_type_fallback(...)

A exceção e é descartada sem log. Deveria logar (logger.warning). Além disso, except Exception no import de magic é amplo demais — use except ImportError.

8. Uso de função privada de outro módulo
from app.shared.core.file_validators import _detect_mime_type_fallback

Importar _função_privada de outro módulo viola encapsulamento. Exponha uma função pública detect_mime_type() que encapsule a lógica magic + fallback — isso também eliminaria a duplicação do bloco try/except no service.

🟡 Defeitos de Lógica
9. editar_pane valida transição mas concluir_pane não sincroniza da mesma forma

Quando editar_pane transiciona para RESOLVIDA, não chama _sincronizar_status_aeronave_pane — a aeronave permanece INDISPONIVEL mesmo sem panes abertas. Bug de inconsistência:

if novo_status == StatusPane.RESOLVIDA:
    pane.data_conclusao = datetime.now(timezone.utc)
    pane.concluido_por_id = usuario_id
    # ⚠️ FALTA: await _sincronizar_status_aeronave_pane(db, pane.aeronave_id)

Também não preenche observacao_conclusao nem adiciona o usuário como responsável (comportamento divergente de concluir_pane — duplicação de lógica com regras diferentes). Recomendo: editar_pane delegar a transição para concluir_pane.

> **✅ Correção aplicada (mínima, não a refatoração "delegar para concluir_pane"):** `editar_pane` agora
> chama `_sincronizar_status_aeronave_pane(db, pane.aeronave_id)` quando `dados.status == RESOLVIDA` —
> resolve o bug real relatado (aeronave presa em INDISPONIVEL).
> **Decisão consciente:** não fiz `editar_pane` delegar para `concluir_pane`. Os dois têm contratos
> diferentes — `editar_pane` é RF-10 (edição genérica, sem `observacao_conclusao` no payload de
> `PaneUpdate`) e `concluir_pane` é RF-12/13 (fluxo de conclusão dedicado, com observação e
> auto-adição de responsável). Delegar exigiria mudar a assinatura de `PaneUpdate` ou inventar uma
> observação vazia, alterando o contrato da API — maior que o escopo de "corrigir o bug de alta
> prioridade". A duplicação de lógica entre as duas funções permanece como dívida técnica registrada.

10. Comparação frágil de status com string literal
if status_str not in [StatusAeronave.INSPECAO.value, "INSPEÇÃO", ...]:

A string mágica "INSPEÇÃO" hardcoded sugere inconsistência de dados no banco (com/sem acento). Isso é um code smell grave — normalize os dados via migração em vez de tolerar as duas formas no código.

11. buscar_pane retorna None se a pane existe mas o ranking falhar

O join (inner) com a subquery de ranking pode ocultar panes se data_abertura for NULL. Considere outerjoin com coalesce, ou garantir NOT NULL na coluna.

12. restaurar_pane não valida estado da aeronave

Restaurar uma pane de uma aeronave que foi inativada pode colocá-la como INDISPONIVEL indevidamente? A sincronização trata, mas restaurar pane de aeronave INATIVA deveria talvez ser bloqueado (como em criar_pane).

13. Filtro excluidas semanticamente confuso

excluidas=True mostra apenas inativas, nunca ambas. Se a intenção era "incluir excluídas", o comportamento está errado. Confirme a spec.

🟢 Melhorias e Otimizações
14. Duplicação da subquery de ranking

listar_panes duplica inline o código de _get_ranking_subquery(). Use a função helper (que, aliás, não precisa ser async — não tem await):

def _get_ranking_subquery():  # remover async
    ...

> **✅ Correção aplicada:** `_get_ranking_subquery` virou função síncrona (recebe `db` para detectar o
> dialeto — ver #18) e `listar_panes` passou a chamá-la em vez de duplicar a lógica inline.
> **Regressão:** teste verifica que `listar_panes` e `buscar_pane` retornam exatamente a mesma
> sequência/ano para a mesma pane — antes, um ajuste feito só no helper (usado por `buscar_pane`) podia
> divergir silenciosamente da cópia inline em `listar_panes`.

15. count() desnecessário para verificar existência
q_panes = select(func.count(Pane.id)).where(...)

Mais eficiente com EXISTS:

from sqlalchemy import exists
q = select(exists().where(Pane.aeronave_id == aeronave_id, ...))
tem_panes_abertas = (await db.execute(q)).scalar()

> **✅ Correção aplicada:** as duas checagens em `_sincronizar_status_aeronave_pane` (panes abertas,
> inspeções ativas) usam `select(exists().where(...))` em vez de `select(func.count(...))`.
> Comportamento idêntico (só muda a forma da query SQL, não a semântica) — confirmado pela suíte completa
> (250 testes) e por um teste dedicado com 3 panes abertas simultâneas.

16. Excesso de db.refresh com relacionamentos

criar_pane e concluir_pane fazem refresh com 4-5 relações — cada refresh dispara queries. Como as relações já são conhecidas (aeronave carregada, anexos vazios em criação), considere popular manualmente ou usar um único select final com selectinload.

> **✅ Correção aplicada — apenas em `concluir_pane`; `criar_pane` foi tentado e revertido:**
> - **`concluir_pane`:** removido um `db.refresh(pane, ["responsaveis"])` totalmente redundante (a pane
>   já vem de `_buscar_pane_por_id`, que carrega `responsaveis` via `selectinload` linhas antes, sem nada
>   invalidar isso no meio do caminho). O refresh final passou de 4 relações fixas para 1–2 condicionais:
>   `responsavel_conclusao` (sempre — o FK `concluido_por_id` acabou de mudar) e `responsaveis` (só se um
>   insert foi de fato tentado). `aeronave` e `anexos` saíram da lista: `aeronave` é o MESMO objeto
>   identity-mapped que `_sincronizar_status_aeronave_pane` já atualiza em memória; `anexos` nunca é
>   tocado nesta função. Isso funciona porque, neste caminho, `pane` vem de uma query com `selectinload`
>   real (relações genuinamente carregadas, não "presumidas vazias").
> - **`criar_pane` — tentativa revertida:** cheguei a aplicar a mesma ideia (popular `aeronave`
>   manualmente e pular o refresh de `anexos`/`responsaveis` "porque nascem vazios"), mas essa premissa
>   estava **errada**: um objeto recém-`flush()`ado deixa de ser transient e suas coleções passam a exigir
>   carregamento explícito — acessá-las sem refresh disparou `sqlalchemy.exc.MissingGreenlet` (lazy-load
>   síncrono em contexto async). Descobri isso com um teste direto **antes** de consolidar a mudança, e
>   revertida para o `db.refresh(pane, ["aeronave", "anexos", "responsaveis", "sistema_ata"])` original.
>   Registro aqui para quem tentar de novo: a otimização segura em `criar_pane` exigiria `selectinload`
>   explícito no INSERT (não existe atalho) ou aceitar o custo do refresh.
> **Regressão:** teste prova que `concluir_pane` não dispara `MissingGreenlet` e que o refresh de
> `responsaveis` é condicional — comparando contagem de queries entre um cenário que precisa inserir
> responsável e outro que não precisa, o segundo é mensuravelmente mais barato.

17. Magic strings "processando" e "ERRO"

Espalhadas em 3 lugares. Extrair para constantes ou, melhor, adicionar coluna status_processamento (enum) no modelo Anexo em vez de sobrecarregar caminho_arquivo.

class StatusProcessamentoAnexo(str, Enum):
    PROCESSANDO = "PROCESSANDO"
    CONCLUIDO = "CONCLUIDO"
    ERRO = "ERRO"
18. _get_year_func chama get_settings() a cada invocação

Cachear a detecção do dialeto (ou melhor, detectar via db.bind.dialect.name em vez de parsear a URL com "sqlite" in ..., que é frágil).

> **✅ Correção aplicada — exatamente a alternativa "melhor" sugerida:** `_get_year_func(db, column)`
> agora lê `db.bind.dialect.name` (atributo já resolvido pela engine, sem I/O nem parsing de string) em
> vez de `get_settings().database_url` + `"sqlite" in ...`. Isso também elimina a fragilidade de
> depender do texto da URL (ex.: um `database_url` customizado sem a palavra "sqlite" no caminho
> quebraria a detecção antiga). A assinatura mudou (`db` como parâmetro) — propagada para
> `_get_ranking_subquery(db)`, seu único chamador.
> **Regressão:** teste confirma que o código ddd/yy continua correto após a troca de estratégia.

19. Comparações booleanas não-idiomáticas
Pane.ativo == True  # noqa: E712

Preferir o idiomático SQLAlchemy:

Pane.ativo.is_(True)   # ou apenas Pane.ativo

Elimina os # noqa.

20. _escape_like sem escape na query

O escape manual só funciona se o .like() declarar o caractere de escape:

func.lower(Pane.descricao).like(texto_like, escape="\\")

Sem o parâmetro escape, o comportamento varia entre bancos (PostgreSQL usa \ por padrão, mas SQLite não). Bug potencial de segurança/corretude. Alternativa mais robusta: usar .ilike() (elimina os func.lower) com escape explícito.

> **✅ Correção aplicada:** os 3 `.like(texto_like)` em `listar_panes` ganharam `escape="\\"`, exatamente
> como sugerido. `.ilike()` não foi adotado (manteria `func.lower()` mesmo assim, já que a comparação
> também é feita em `SistemaAta.descricao`/`Aeronave.matricula`, e trocar teria custo de teste maior sem
> ganho real — `func.lower(...).like(..., escape="\\")` já resolve o bug).
> **Regressão:** dois testes provam o bug antigo diretamente — busca por texto contendo `%` literal (que
> antes falhava silenciosamente, pois o escape sem `ESCAPE '\'` na cláusula não tinha efeito) agora
> encontra o registro; busca por `_` não vira coringa e não retorna falsos positivos.

21. Duplicação massiva em processar_imagem_background — ✅ RESOLVIDO (helper na rodada de alta prioridade + sub-itens finalizados agora)

> A correção do item #34 já havia extraído o helper (`_atualizar_caminho_anexo_se_pendente`), eliminando
> os 3 blocos duplicados. Nesta rodada de baixa prioridade, finalizei os 3 sub-itens que ficaram
> pendentes:
> - `from sqlalchemy import select` re-importado localmente dentro do helper — removido (já está no topo
>   do módulo).
> - `loop.run_in_executor(None, lambda: process_image(...))` → `asyncio.to_thread(process_image,
>   arquivo_bytes, filename_hint=nome_original)` — mesma semântica, sem a lambda intermediária.
> - `logging.error(...)` direto (+ `import logging` local) → `logger.error(...)` usando o
>   `logger = logging.getLogger(__name__)` de módulo (já existia, criado para o item #4).

Três blocos quase idênticos de "abrir sessão → buscar anexo → atualizar → commit". Extrair helper:

async def _atualizar_caminho_anexo(anexo_id: uuid.UUID, caminho: str) -> None:
    SessionMaker = get_session_factory()
    async with SessionMaker() as session:
        anexo = await session.get(Anexo, anexo_id)
        if anexo:
            anexo.caminho_arquivo = caminho
            await session.commit()

Também: from sqlalchemy import select re-importado localmente (já está no topo); use asyncio.to_thread() em vez de loop.run_in_executor(None, lambda: ...) (Python 3.9+); use logger = logging.getLogger(__name__) no módulo em vez de logging.error direto.

22. Docstring desatualizada e formatação
upload_anexo docstring diz "jpg, png, pdf" mas aceita heic/heif e webp (após processamento).
Linha com comentário grudado no código (falta quebra de linha):
if is_image and is_background:        # Retorna placeholder para processamento em background (Etapa 5)

Deveria ser:

if is_image and is_background:
    # Retorna placeholder para processamento em background (Etapa 5)
Vários trechos têm trailing whitespace e linhas em branco com espaços (visível após await db.flush() em alguns blocos) — configurar ruff/black no CI resolveria.
Docstring de excluir_anexo diz "deleta o arquivo físico", mas com R2 é remoto — pequeno detalhe de precisão.
23. Variáveis com nomes enganosos (resultado → pane)

Padrão repetido em várias funções:

resultado = await _buscar_pane_por_id(db, pane_id)
if not resultado:
    raise ValueError("Pane não encontrada.")
pane = resultado  # atribuição redundante

Simplificar:

pane = await _buscar_pane_por_id(db, pane_id)
if not pane:
    raise ValueError("Pane não encontrada.")

> **✅ Correção aplicada — exatamente como sugerido, nas 5 funções afetadas:** `concluir_pane`,
> `excluir_pane`, `restaurar_pane`, `upload_anexo` e `adicionar_responsavel`. Nas duas últimas, a variável
> `pane` não era usada em nenhum outro lugar da função — a atribuição foi simplesmente removida (não só
> simplificada), ficando `if not await _buscar_pane_por_id(db, pane_id): raise ValueError(...)`.

24. ValueError genérico para todos os erros de negócio

Todas as falhas usam ValueError, forçando o router a distinguir "não encontrada" (404) de "transição inválida" (422) de "já resolvida" (409) por string matching — frágil e propenso a quebrar com i18n.

Correção: hierarquia de exceções de domínio:

class PaneError(Exception): ...
class PaneNaoEncontradaError(PaneError): ...
class TransicaoInvalidaError(PaneError): ...
class PaneJaResolvidaError(PaneError): ...
class AnexoInvalidoError(PaneError): ...

Com exception handlers globais no FastAPI mapeando cada uma para o status HTTP correto.

> **✅ Correção aplicada — reaproveitando a hierarquia já existente, não uma nova (`app.shared.core.exceptions`):**
> `editar_pane` e `concluir_pane` (as duas funções com string-matching real no router) agora levantam
> `domain_exc.EntidadeNaoEncontradaError` (404) e `domain_exc.ConflitoNegocioError` (409) em vez de
> `ValueError`. Como essas exceções **já são `HTTPException`** (mesma base usada no módulo de
> equipamentos), o FastAPI as converte automaticamente — os blocos `except ValueError: if "não encontrada"
> in detail_str: ...` foram **removidos** dos dois endpoints (`PUT /panes/{id}` e
> `POST /panes/{id}/concluir}`), sem exception handler novo a registrar.
> **Não criei `PaneError`/`PaneNaoEncontradaError`/etc. como classes novas:** as exceções compartilhadas
> já cobrem exatamente os 2 status usados por essas duas funções (404/409); duplicar a hierarquia só para
> ter nomes "Pane*" adicionaria uma camada sem ganho de comportamento.
> **Escopo deliberadamente limitado a `editar_pane`/`concluir_pane`:** são as únicas funções do módulo
> com string-matching por *substring de mensagem* (`"abertas" in detail_str`, `"Transição" in detail_str`),
> que é o padrão frágil citado no relatório. Os demais endpoints (criar_pane, deletar_pane, restaurar_pane,
> adicionar_responsavel, upload_anexo, excluir_anexo) já mapeiam **todo** `ValueError` para um único status
> fixo (sem diferenciar por conteúdo da mensagem) — não sofrem do mesmo risco de regressão com i18n, e
> converter também exigiria decidir se comportamentos hoje "questionáveis" (ex.: `criar_pane` retorna 404
> tanto para aeronave inexistente quanto para aeronave inativa) devem mudar — decisão de produto fora do
> escopo desta correção técnica. Registrado aqui como próximo passo, não como bug.
> **Regressão:** 5 testes verificam o *tipo* da exceção e o `status_code` que ela carrega diretamente
> (sem passar pelo router), cobrindo pane inexistente, transição inválida e já resolvida nas duas funções.

25. Comparação de papel com strings mágicas
if usuario_responsavel.funcao not in ["MANTENEDOR", "ENCARREGADO"]:

Se existe enum de funções (provável, dado o padrão do projeto), usar:

_FUNCOES_RESPONSAVEL = {FuncaoUsuario.MANTENEDOR, FuncaoUsuario.ENCARREGADO}
if usuario_responsavel.funcao not in _FUNCOES_RESPONSAVEL:
26. listar_panes sem count total para paginação

A função retorna a página, mas o frontend não tem como saber o total de registros para renderizar a paginação. Considere retornar (items, total):

total_query = select(func.count()).select_from(query_sem_offset_limit.subquery())
total = (await db.execute(total_query)).scalar()
27. Filtro de texto pode gerar produto cartesiano acidental

Em listar_panes, o outerjoin com Aeronave e SistemaAta é feito após o join com a subquery de ranking. Como são relações N:1 não há duplicação aqui, mas se futuramente adicionarem busca em responsaveis (1:N), surgirão linhas duplicadas sem distinct(). Vale deixar comentário defensivo ou já aplicar .distinct().

28. data_fim provavelmente exclui o último dia
if filtros.data_fim:
    query = query.where(Pane.data_abertura <= filtros.data_fim)

Se data_abertura é datetime e data_fim chega como date (ex.: 2025-01-15 → 2025-01-15 00:00:00), panes abertas às 10h do dia 15 ficam fora do filtro. Bug clássico de UX de filtros de data.

Correção:

from datetime import timedelta
query = query.where(Pane.data_abertura < filtros.data_fim + timedelta(days=1))

(Ou normalizar no schema Pydantic com validator.)

> **✅ Correção aplicada — exatamente como sugerido:** `Pane.data_abertura <= filtros.data_fim` virou
> `Pane.data_abertura < filtros.data_fim + timedelta(days=1)`. Tratei `data_fim` como limite de **dia**
> (não de instante exato), que é a leitura mais compatível com um filtro de UI tipo `<input type="date">`.
> Não usei a alternativa "normalizar no schema Pydantic" porque `FiltroPane.data_fim` é `datetime` (não
> `date`) e pode legitimamente chegar com hora — normalizar ali "zeraria" um horário que o cliente talvez
> tenha enviado de propósito; resolver no service (somando 1 dia ao limite) é mais seguro e não descarta
> informação do payload.
> **Regressão:** 2 testes — uma pane aberta às 18h do "último dia" do filtro agora aparece (antes ficava
> de fora); uma pane do dia seguinte continua corretamente excluída (garante que não virou filtro sem teto).

29. skip/limit sem validação de limites no service

Se o schema FiltroPane não impuser teto, um cliente pode passar limit=999999 e anular a proteção AUD-14. Garantir no schema:

limit: int = Field(default=50, ge=1, le=200)
skip: int = Field(default=0, ge=0)
30. Sanitização do nome de arquivo antes do upload

nome_original vem do cliente e é passado direto ao storage_svc.upload(). Se o storage usar o nome no path, há risco de path traversal (../../etc/passwd) ou caracteres problemáticos. Mesmo que o storage gere UUID, o service deveria sanitizar defensivamente:

nome_original = os.path.basename(nome_original or "arquivo")

Em processar_imagem_background isso é ainda mais relevante, pois novo_nome deriva diretamente de nome_original.

31. Inconsistência de MIME validado vs. extensão

O código valida extensão e MIME separadamente, mas não valida coerência entre eles. Um arquivo foto.pdf contendo bytes de PNG passa (extensão .pdf permitida, MIME image/png permitido) e será classificado como imagem com extensão de PDF. Validar o par:

_EXTENSAO_MIME_MAP = {
    ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"},
    ".png": {"image/png"}, ".pdf": {"application/pdf"},
    ".heic": {"image/heic", "image/heif"}, ".heif": {"image/heif", "image/heic"},
}
if mime_real not in _EXTENSAO_MIME_MAP.get(extensao, set()):
    raise ValueError("Extensão não corresponde ao conteúdo do arquivo.")

> **✅ Correção aplicada — literalmente o `_EXTENSAO_MIME_MAP` sugerido:** adicionado como constante de
> módulo em `service.py` e a checagem entra logo após a validação de MIME em `upload_anexo`.
> **Nota:** `app/shared/core/file_validators.validate_file_upload` (chamada pelo **router**, antes do
> service, na rota `POST /panes/{id}/anexos`) já fazia esse cross-check para jpg/png/pdf — então, pela
> HTTP, o exemplo `foto.pdf` com bytes de PNG já era bloqueado antes de chegar ao service. A correção
> no service continua necessária como defesa em profundidade (qualquer chamador direto do service, sem
> passar pelo router, ficava desprotegido) e cobre heic/heif, que `validate_file_upload` sequer conhece.
> **Regressão:** teste chama `service.upload_anexo` diretamente (contornando o router) com extensão
> `.pdf` e bytes de PNG — confirma que o service rejeita mesmo sem a camada do router.

32. Parâmetro tipo_mime recebido e nunca usado
async def upload_anexo(
    db, pane_id, arquivo_bytes, nome_original,
    tipo_mime: str,  # ⚠️ nunca usado no corpo
    ...

O MIME declarado pelo cliente é ignorado (correto por segurança), mas então o parâmetro deveria ser removido da assinatura, ou ao menos logado quando divergir do mime_real (útil para detectar clientes maliciosos/bugados).

33. listar_anexos e buscar_anexo sem verificação de existência da pane

listar_anexos retorna lista vazia tanto para "pane sem anexos" quanto para "pane inexistente" — o router não consegue retornar 404 corretamente. Considere validar a pane primeiro ou documentar o comportamento.

34. Sessão nova no background task não compartilha configuração transacional

Em processar_imagem_background, cada bloco abre sessão própria e faz commit direto — correto para background, mas o update deveria ser condicional para evitar sobrescrever um anexo que foi excluído durante o processamento:

anexo = result.scalar_one_or_none()
if anexo and anexo.caminho_arquivo == "processando":  # só atualiza se ainda pendente
    anexo.caminho_arquivo = caminho_salvo
    await session.commit()
else:
    # anexo foi excluído ou já processado — limpar o arquivo recém-enviado
    await storage_svc.delete(caminho_salvo)

Sem isso: usuário exclui o anexo "processando" → background termina → arquivo órfão no storage e possível ressurreição do registro (dependendo do timing do delete).

> **✅ Correção aplicada — exatamente o padrão sugerido, extraído como helper:**
> `_atualizar_caminho_anexo_se_pendente(anexo_id, caminho_novo, arquivo_para_limpar=None)` centraliza a
> checagem "só atualiza se `caminho_arquivo == 'processando'`" e a limpeza do arquivo órfão quando o anexo
> foi excluído ou já processado por outra execução. Usada nos 3 pontos de `processar_imagem_background`
> (sucesso, fallback e marcação de ERRO) — isso também elimina a duplicação apontada no item #21 (helper
> único em vez de 3 blocos quase idênticos "abrir sessão → buscar → atualizar → commit").
> **Regressão:** 3 testes cobrem diretamente a função — anexo excluído não é ressuscitado, anexo já
> processado não é sobrescrito, anexo ainda pendente é atualizado normalmente.

📋 Resumo Priorizado — Alta: ✅ 6/6 · Média: ✅ 4/4 · Baixa: ✅ 7/7
Prioridade	Item	Descrição	Status
🔴 Alta	#9	editar_pane não sincroniza status da aeronave ao resolver	✅
🔴 Alta	#20	_escape_like sem parâmetro escape no .like() — escape não funciona	✅
🔴 Alta	#5	Background task não durável — anexos presos em "processando"	✅ (mitigação mínima)
🔴 Alta	#34	Race entre exclusão de anexo e processamento background	✅
🔴 Alta	#2, #3	Race conditions (responsável duplicado, status da aeronave)	✅
🟡 Média	#4	Arquivos órfãos no storage em falha de transação	✅
🟡 Média	#28	Filtro data_fim exclui o último dia	✅
🟡 Média	#31	Extensão e MIME não validados em conjunto	✅
🟡 Média	#24	ValueError genérico dificulta mapeamento HTTP	✅ (escopo: editar_pane/concluir_pane)
🟢 Baixa	#6, #14, #21, #23	Limpeza: imports mortos, duplicação, nomes	✅ 4/4
🟢 Baixa	#15, #16, #18	Otimizações de queries	✅ 3/3 (#16 parcial — ver nota)

---

## 🔎 Notas gerais da execução (02/08/2026)

**Todas as prioridades concluídas nesta sessão** (17/17 itens do resumo priorizado, em três rodadas:
alta → média → baixa).

**Arquivos alterados/criados (consolidado — todas as rodadas):**
- `app/modules/panes/service.py` — reescrito nos pontos afetados: sincronização de status, escape de LIKE,
  race conditions, job de limpeza, helper de atualização condicional de anexo, compensação de storage,
  filtro de data, coerência extensão/MIME, exceções de domínio, EXISTS no lugar de COUNT, subquery de
  ranking compartilhada, detecção de dialeto sem parsing, refresh reduzido em `concluir_pane`, imports
  mortos removidos, variáveis `resultado→pane` simplificadas, `asyncio.to_thread` + logger de módulo.
- `app/modules/panes/router.py` — `editar_pane`/`concluir_pane` sem try/except de tradução de erro.
- `app/modules/panes/models.py` — `UniqueConstraint` em `PaneResponsavel`.
- `app/bootstrap/tasks.py` (+ `anexos_travados_cleanup_task`), `events.py` (task agendada).
- `migrations/versions/20260802_1130_f3c2b8a1d4e6_add_unique_pane_responsavel.py` (**aplicada em `var/db`**).
- `tests/unit/test_panes_alta_prioridade.py` (13), `test_panes_media_prioridade.py` (12),
  `test_panes_baixa_prioridade.py` (5) — **30 testes novos no total**.

**Suíte completa final:** `pytest tests/unit tests/architecture tests/test_calendario.py
tests/test_exporter.py` → **250 testes, 0 falhas**.

**Decisões conscientes que ficam registradas para quem continuar:**
- `#5`: mitigação mínima (job de limpeza), não a correção definitiva (fila durável ou salvar original
  antes de otimizar) — perda de dados em crash durante o processamento ainda é possível, só não trava a UI.
- `#3`: `with_for_update=True` é no-op no SQLite atual — só protege de fato se o projeto migrar de banco.
- `#24`: hierarquia de exceções aplicada apenas a `editar_pane`/`concluir_pane` (onde havia string-matching
  real); os demais endpoints mapeiam `ValueError` para um status fixo e não foram tocados.
- `#9`: corrigido o bug (sincronização ausente), mas **não** fiz `editar_pane` delegar para `concluir_pane`
  como o relatório sugeria como alternativa — mudaria o contrato de `PaneUpdate`.
- `#16`: aplicado só em `concluir_pane`. Em `criar_pane` a mesma ideia foi **tentada e revertida** — quebrava
  em runtime (`MissingGreenlet`) porque um objeto recém-flushado não tem coleções "presumidamente vazias"
  como eu havia assumido; confirmado com um teste direto antes de reverter. Ver nota completa no item #16
  acima — vale ler antes de tentar de novo.
- Itens fora do resumo priorizado (#1, #7, #8, #10–#13, #17, #19, #22, #25–#33 exceto os já citados)
  permanecem no relatório original, não tocados — não estavam na lista de prioridades do usuário.

O código está bem estruturado, com boa documentação de regras de negócio (referências a SPECS/RN/COR) e preocupação com segurança (validação de MIME, escape de LIKE). Os pontos mais urgentes eram os de consistência de estado (#9, #34) e a correção do escape do LIKE (#20) — todos corrigidos.