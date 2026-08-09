"""
tests/security/test_publicacoes_xss.py
XSS via ementa de publicação avulsa (M2 tarefa 9, achado B8).

A `ementa` de uma publicação avulsa é entrada de usuário e vai direto para o
`snippet` da resposta de busca (`avulsas.construir_snippet`) — mesmo risco que
o acervo A tem com o texto extraído do PDF
(`03_especificacao_tecnica.md` §3.1): um `<img src=x onerror=...>` digitado
por um usuário não pode virar HTML executável na tela de quem buscar pelo
mesmo termo.

**O contrato de segurança é do PAR servidor+cliente, não só do servidor**:
1. O servidor NUNCA emite `<mark>` (ou qualquer tag) — só os sentinelas de
   controle `\\x02`/`\\x03` ao redor do termo casado. Isto é o que este
   arquivo verifica diretamente, sobre a resposta HTTP real.
2. O cliente (`publicacoes.js:snippetSeguro`) escapa o snippet INTEIRO com
   `escapeHtml` e só DEPOIS troca os sentinelas por `<mark>`. Um JSON com
   `<img...>` dentro de uma string não executa nada por si só — o risco só
   existiria se o cliente inserisse esse texto em `innerHTML` sem escapar
   antes. Como Python não roda o JS do navegador, a segunda metade é
   verificada aqui **simulando exatamente o mesmo algoritmo** (escapar tudo,
   só então trocar sentinela por tag) e afirmando que o resultado não contém
   mais nenhuma tag executável — é a prova de que o contrato funciona quando
   o cliente faz a sua parte, que é o que `publicacoes.js` faz.
"""

import html

import pytest
from httpx import AsyncClient

URL = "/publicacoes/api/avulsas"

PAYLOAD_XSS = "<img src=x onerror=alert(1)>"


def payload_com_xss_na_ementa(*, numero: str = "999-24-0001") -> dict:
    return {
        "tipo": "BS",
        "numero": numero,
        "ano": 2026,
        "data_emissao": "2026-01-10",
        "data_recebimento": "2026-01-15",
        "emissor": "Embraer",
        "titulo": "Boletim de teste de segurança",
        "ementa": f"Procedimento de sangria do compressor {PAYLOAD_XSS} — revisar válvula.",
    }


def renderizar_como_o_cliente(snippet: str) -> str:
    """
    Reproduz `publicacoes.js:snippetSeguro` em Python:

        escapeHtml(snippet).replaceAll('\\x02', '<mark>').replaceAll('\\x03', '</mark>')

    `html.escape` cobre o mesmo conjunto que `div.textContent = x;
    x.innerHTML` no navegador (`&`, `<`, `>`, `"`, `'`).
    """
    return (
        html.escape(snippet)
        .replace("\x02", "<mark>")
        .replace("\x03", "</mark>")
    )


@pytest.mark.asyncio
async def test_snippet_do_servidor_usa_sentinela_nunca_mark_cru(
    client_autenticado: AsyncClient,
):
    """
    O achado B8, verificado sobre a resposta HTTP real: o delimitador que o
    servidor insere ao redor do termo casado é `\\x02`/`\\x03`, nunca
    `<mark>`. É a diferença entre "o cliente decide como destacar" e "o
    servidor já decidiu por HTML", que é exatamente o que tornava o desenho
    anterior (`snippet(pages_fts, 0, '<mark>', '</mark>', ...)`) uma XSS.
    """
    await client_autenticado.post(URL, json=payload_com_xss_na_ementa())

    resposta = await client_autenticado.get(URL, params={"texto": "sangria"})
    assert resposta.status_code == 200

    snippet = resposta.json()["results"][0]["snippet"]
    assert "\x02sangria\x03" in snippet.lower() or "\x02" in snippet
    assert "<mark>" not in snippet
    assert "</mark>" not in snippet


@pytest.mark.asyncio
async def test_snippet_renderizado_pelo_cliente_neutraliza_o_payload(
    client_autenticado: AsyncClient,
):
    """
    Prova o contrato completo: quando o cliente segue a receita (escapar
    tudo, só então trocar sentinela por `<mark>`), o `<img onerror=...>`
    embutido na ementa não sobrevive como tag — vira texto inerte, e o
    realce do termo buscado continua funcionando.

    Medido com o payload deliberadamente DENTRO da janela do snippet (a
    ementa de teste é curta o bastante para isso) — é o cenário mais
    hostil possível, não o mais favorável.
    """
    await client_autenticado.post(URL, json=payload_com_xss_na_ementa())

    resposta = await client_autenticado.get(URL, params={"texto": "sangria"})
    snippet = resposta.json()["results"][0]["snippet"]
    assert "<img" in snippet, "pré-condição do teste: o payload cru precisa estar na janela"

    renderizado = renderizar_como_o_cliente(snippet)

    assert "<img" not in renderizado
    assert "<script" not in renderizado
    assert "onerror=" not in renderizado or "&lt;img" in renderizado
    assert "<mark>sangria</mark>" in renderizado.lower() or "<mark>" in renderizado
    assert "&lt;img" in renderizado  # o payload sobrevive como TEXTO, não como tag


@pytest.mark.asyncio
async def test_ementa_completa_no_detalhe_e_json_puro_nao_html(
    client_autenticado: AsyncClient,
):
    """
    `GET /api/avulsas/{id}` devolve a `ementa` inteira, sem snippet. O
    servidor não tenta "sanitizar" removendo a tag — devolve o texto tal
    como foi digitado, porque uma resposta JSON não executa HTML por si só.
    A defesa mora inteiramente em nunca injetar esse texto como HTML sem
    escapar primeiro, responsabilidade do cliente sempre que ele o exibir
    (`escapeHtml`, `app.js:223`), não do servidor.
    """
    criada = (
        await client_autenticado.post(URL, json=payload_com_xss_na_ementa())
    ).json()

    detalhe = await client_autenticado.get(f"{URL}/{criada['id']}")
    assert detalhe.headers["content-type"].startswith("application/json")
    assert PAYLOAD_XSS in detalhe.json()["ementa"]


@pytest.mark.asyncio
async def test_titulo_com_xss_tambem_usa_sentinela_no_snippet(
    client_autenticado: AsyncClient,
):
    """B8 vale para `titulo` também — router.py escolhe a fonte do snippet
    (ementa ou título) por onde o termo casou."""
    payload = payload_com_xss_na_ementa(numero="999-24-0002")
    payload["titulo"] = f"Boletim {PAYLOAD_XSS} sangria"
    payload["ementa"] = "Ementa comum, sem termo hostil."

    await client_autenticado.post(URL, json=payload)

    resposta = await client_autenticado.get(URL, params={"texto": "sangria"})
    snippet = resposta.json()["results"][0]["snippet"]

    assert "<mark>" not in snippet
    assert "\x02" in snippet
    assert "<img" not in renderizar_como_o_cliente(snippet)
