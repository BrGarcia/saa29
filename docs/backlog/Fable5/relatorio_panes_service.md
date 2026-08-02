arquivo:
app/modules/panes/service.py

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

3. Race condition em _sincronizar_status_aeronave_pane

Duas panes sendo resolvidas/criadas concorrentemente para a mesma aeronave podem gerar status inconsistente (lost update).

Correção: usar lock pessimista:

aeronave = await db.get(Aeronave, aeronave_id, with_for_update=True)
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

5. processar_imagem_background recebe bytes grandes e pode perder dados

Se o processo reiniciar (deploy, crash) entre o registro do placeholder "processando" e a execução do background task, os bytes se perdem para sempre — o anexo fica eternamente como "processando". BackgroundTasks do FastAPI não é durável.

Correção: salvar o arquivo original no storage imediatamente e processar depois (substituindo), ou usar fila persistente (Celery/ARQ/RQ). No mínimo, criar job de limpeza para anexos "processando" antigos.

6. Import anyio não utilizado
import anyio  # nunca usado

Também: Path de pathlib importado e não usado; Aeronave importado no topo mas re-importado localmente dentro de listar_panes (redundante); uuid só é usado para type hints; pane capturado mas não usado em upload_anexo e adicionar_responsavel (variável pane/resultado desnecessária).

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
15. count() desnecessário para verificar existência
q_panes = select(func.count(Pane.id)).where(...)

Mais eficiente com EXISTS:

from sqlalchemy import exists
q = select(exists().where(Pane.aeronave_id == aeronave_id, ...))
tem_panes_abertas = (await db.execute(q)).scalar()
16. Excesso de db.refresh com relacionamentos

criar_pane e concluir_pane fazem refresh com 4-5 relações — cada refresh dispara queries. Como as relações já são conhecidas (aeronave carregada, anexos vazios em criação), considere popular manualmente ou usar um único select final com selectinload.

17. Magic strings "processando" e "ERRO"

Espalhadas em 3 lugares. Extrair para constantes ou, melhor, adicionar coluna status_processamento (enum) no modelo Anexo em vez de sobrecarregar caminho_arquivo.

class StatusProcessamentoAnexo(str, Enum):
    PROCESSANDO = "PROCESSANDO"
    CONCLUIDO = "CONCLUIDO"
    ERRO = "ERRO"
18. _get_year_func chama get_settings() a cada invocação

Cachear a detecção do dialeto (ou melhor, detectar via db.bind.dialect.name em vez de parsear a URL com "sqlite" in ..., que é frágil).

19. Comparações booleanas não-idiomáticas
Pane.ativo == True  # noqa: E712

Preferir o idiomático SQLAlchemy:

Pane.ativo.is_(True)   # ou apenas Pane.ativo

Elimina os # noqa.

20. _escape_like sem escape na query

O escape manual só funciona se o .like() declarar o caractere de escape:

func.lower(Pane.descricao).like(texto_like, escape="\\")

Sem o parâmetro escape, o comportamento varia entre bancos (PostgreSQL usa \ por padrão, mas SQLite não). Bug potencial de segurança/corretude. Alternativa mais robusta: usar .ilike() (elimina os func.lower) com escape explícito.

21. Duplicação massiva em processar_imagem_background

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
24. ValueError genérico para todos os erros de negócio

Todas as falhas usam ValueError, forçando o router a distinguir "não encontrada" (404) de "transição inválida" (422) de "já resolvida" (409) por string matching — frágil e propenso a quebrar com i18n.

Correção: hierarquia de exceções de domínio:

class PaneError(Exception): ...
class PaneNaoEncontradaError(PaneError): ...
class TransicaoInvalidaError(PaneError): ...
class PaneJaResolvidaError(PaneError): ...
class AnexoInvalidoError(PaneError): ...

Com exception handlers globais no FastAPI mapeando cada uma para o status HTTP correto.

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

📋 Resumo Priorizado
Prioridade	Item	Descrição
🔴 Alta	#9	editar_pane não sincroniza status da aeronave ao resolver
🔴 Alta	#20	_escape_like sem parâmetro escape no .like() — escape não funciona
🔴 Alta	#5	Background task não durável — anexos presos em "processando"
🔴 Alta	#34	Race entre exclusão de anexo e processamento background
🔴 Alta	#2, #3	Race conditions (responsável duplicado, status da aeronave)
🟡 Média	#4	Arquivos órfãos no storage em falha de transação
🟡 Média	#28	Filtro data_fim exclui o último dia
🟡 Média	#31	Extensão e MIME não validados em conjunto
🟡 Média	#24	ValueError genérico dificulta mapeamento HTTP
🟢 Baixa	#6, #14, #21, #23	Limpeza: imports mortos, duplicação, nomes
🟢 Baixa	#15, #16, #18	Otimizações de queries

O código está bem estruturado, com boa documentação de regras de negócio (referências a SPECS/RN/COR) e preocupação com segurança (validação de MIME, escape de LIKE). Os pontos mais urgentes são os de consistência de estado (#9, #34) e a correção do escape do LIKE (#20), que atualmente pode não funcionar conforme esperado dependendo do banco.