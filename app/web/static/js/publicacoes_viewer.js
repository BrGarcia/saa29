/**
 * app/web/static/js/publicacoes_viewer.js
 * Viewer de PDF em <canvas>, via PDF.js vendorizado — zoom, ajuste à
 * largura/página, rotação, tela cheia, miniaturas sob demanda e busca de
 * texto dentro do documento.
 *
 * Módulo ES, não script clássico: é o que permite `import` do build do
 * PDF.js sem tocar em CDN (a CSP do projeto é `script-src 'self'`).
 * `apiFetch`/`escapeHtml`/`showToast` vêm de app.js (script clássico, roda
 * antes de qualquer módulo) e ficam disponíveis aqui como globais — não
 * precisam de import.
 *
 * Nunca iframe/embed/object para o PDF em si — só o <canvas> recebe o
 * conteúdo renderizado, decisão D-F (`03_especificacao_tecnica.md` §4.4):
 * `X-Frame-Options: DENY` é global e bloqueia qualquer elemento que crie um
 * browsing context, mesmo same-origin.
 *
 * Miniaturas renderizam do MESMO `pdfDocumento` já carregado — nunca um novo
 * `fetch`/`getDocument` em `/doc/{id}/pdf`, que dispararia
 * `service.registrar_acesso` de novo e duplicaria a linha de auditoria.
 *
 * Duas telas usam este módulo, sobre o MESMO shell
 * (`templates/publicacoes/_viewer_shell.html`):
 *   - `/publicacoes/viewer/{id}` — página dedicada, um documento por carga;
 *     o bootstrap no fim deste arquivo monta sozinho ao ver `data-doc-id`.
 *   - `/publicacoes` — painel direito do explorador, que chama `criarViewer()`
 *     uma vez e depois `abrir(docId)` a cada PDF escolhido na árvore, sem
 *     recarregar a página.
 *
 * Por isso nada aqui usa `document.getElementById` para os elementos do
 * shell: tudo sai de `raiz.querySelector`, e o estado do documento (página,
 * zoom, rotação, miniaturas) vive no fecho de `criarViewer`, zerado a cada
 * `abrir()`.
 */
import { GlobalWorkerOptions, getDocument } from "/static/js/pdfjs/pdf.min.mjs";

const TEXTO_REVISAO_ANTERIOR =
    "Esta é uma REVISÃO ANTERIOR do documento — a edição vigente pode conter mudanças.";

function paginaDaHash() {
    const m = /page=(\d+)/.exec(window.location.hash);
    return m ? parseInt(m[1], 10) : 1;
}

/**
 * Monta o viewer sobre um shell já no DOM.
 *
 * @param {object}      opts
 * @param {HTMLElement} opts.raiz              `.pub-viewer-shell`.
 * @param {string}      opts.workerSrc         Caminho do worker do PDF.js.
 * @param {boolean}     [opts.sincronizarHash] Espelha a página atual em
 *   `#page=N` e obedece `hashchange`. Só na página dedicada: no explorador a
 *   URL é do explorador (`?manual=&capitulo=&doc=`) e o viewer não manda nela.
 * @param {Function}    [opts.aoVoltar]        Clique no botão de voltar do
 *   modo embutido (`#pub-viewer-voltar`); ausente na página dedicada, onde
 *   voltar é um link comum.
 * @param {Function}    [opts.aoTrocarDocumento] Recebe um `doc_id` quando o
 *   próprio viewer quer abrir outro documento (link "edição vigente"). Sem
 *   isso, navega para a página dedicada.
 * @returns {{abrir: Function, destruir: Function, docIdAtual: Function}}
 */
export function criarViewer({ raiz, workerSrc, sincronizarHash = false, aoVoltar = null, aoTrocarDocumento = null }) {
    GlobalWorkerOptions.workerSrc = workerSrc;

    const $ = (id) => raiz.querySelector(`#${id}`);

    const elPalco = $("pub-viewer-palco");
    const canvas = $("pub-viewer-canvas");
    const ctx = canvas.getContext("2d");
    const elMiniaturas = $("pub-viewer-miniaturas");
    const elTitulo = $("pub-viewer-titulo");
    const elSubtitulo = $("pub-viewer-subtitulo");
    const elPaginaInput = $("pub-viewer-pagina-input");
    const elTotalPaginas = $("pub-viewer-total-paginas");
    const elZoomNivel = $("pub-viewer-zoom-nivel");
    const elErro = $("pub-viewer-erro");
    const elRevisaoAnterior = $("pub-viewer-revisao-anterior");
    const elCorpo = raiz.querySelector(".pub-viewer-corpo");
    const btnVoltar = $("pub-viewer-voltar");
    const btnPrev = $("pub-viewer-prev");
    const btnNext = $("pub-viewer-next");
    const btnZoomMais = $("pub-viewer-zoom-mais");
    const btnZoomMenos = $("pub-viewer-zoom-menos");
    const btnAjustarLargura = $("pub-viewer-ajustar-largura");
    const btnAjustarPagina = $("pub-viewer-ajustar-pagina");
    const btnRotacionar = $("pub-viewer-rotacionar");
    const btnTelaCheia = $("pub-viewer-tela-cheia");
    const linkDownload = $("pub-viewer-download");
    const btnFavorito = $("pub-viewer-favorito");
    const iconeFavorito = $("pub-viewer-favorito-icone");
    const elBuscaInput = $("pub-viewer-busca-input");
    const elBuscaLista = $("pub-viewer-busca-lista");

    let docId = null;
    let pdfDocumento = null;
    let paginaAtual = 1;
    /** Página pedida em `abrir()` — aplicada assim que o PDF termina de carregar. */
    let paginaAlvo = 1;
    let escalaAtual = 1.0;
    let modoAjuste = "largura"; // "largura" | "pagina" | "manual"
    let rotacao = 0;
    let renderizando = false;
    let favoritoAtualId = null;
    /** Cada `abrir()` incrementa: descarta resultado de carga de um documento já trocado. */
    let seqCarga = 0;

    // ----------------------------------------------------------------------
    // Renderização da página
    // ----------------------------------------------------------------------

    function calcularEscala(viewportBase, larguraDisponivel, alturaDisponivel) {
        if (modoAjuste === "largura") return larguraDisponivel / viewportBase.width;
        if (modoAjuste === "pagina") {
            return Math.min(larguraDisponivel / viewportBase.width, alturaDisponivel / viewportBase.height);
        }
        return escalaAtual;
    }

    async function renderizarPagina(numero) {
        if (!pdfDocumento || renderizando) return;
        renderizando = true;
        const minhaSeq = seqCarga;
        try {
            const pagina = await pdfDocumento.getPage(numero);
            if (minhaSeq !== seqCarga) return; // outro documento entrou no meio
            const viewportBase = pagina.getViewport({ scale: 1, rotation: rotacao });
            const larguraDisponivel = Math.min(elPalco.clientWidth - 32, 1600);
            const alturaDisponivel = Math.max(elPalco.clientHeight - 32, 200);
            const escala = Math.max(calcularEscala(viewportBase, larguraDisponivel, alturaDisponivel), 0.2);
            escalaAtual = escala;

            const dpr = window.devicePixelRatio || 1;
            const viewport = pagina.getViewport({ scale: escala * dpr, rotation: rotacao });

            canvas.width = viewport.width;
            canvas.height = viewport.height;
            canvas.style.width = `${viewport.width / dpr}px`;
            canvas.style.height = `${viewport.height / dpr}px`;

            await pagina.render({ canvasContext: ctx, viewport }).promise;
            if (minhaSeq !== seqCarga) return;
            paginaAtual = numero;
            elPaginaInput.value = String(paginaAtual);
            elZoomNivel.textContent = `${Math.round(escala * 100)}%`;
            if (sincronizarHash) {
                window.history.replaceState(null, "", `#page=${paginaAtual}`);
            }
            atualizarMiniaturaAtiva();
        } catch (e) {
            console.error("Falha ao renderizar página", numero, e);
            showToast("Falha ao renderizar a página do PDF.", "error");
        } finally {
            renderizando = false;
        }
    }

    function irParaPagina(numero) {
        if (!pdfDocumento) return;
        const alvo = Math.max(1, Math.min(numero, pdfDocumento.numPages));
        renderizarPagina(alvo);
    }

    btnPrev.addEventListener("click", () => irParaPagina(paginaAtual - 1));
    btnNext.addEventListener("click", () => irParaPagina(paginaAtual + 1));
    if (btnVoltar && aoVoltar) btnVoltar.addEventListener("click", aoVoltar);

    const aoMudarHash = () => irParaPagina(paginaDaHash());
    if (sincronizarHash) window.addEventListener("hashchange", aoMudarHash);

    let debounceResize = null;
    const aoRedimensionar = () => {
        clearTimeout(debounceResize);
        debounceResize = setTimeout(() => renderizarPagina(paginaAtual), 150);
    };
    window.addEventListener("resize", aoRedimensionar);

    elPaginaInput.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        const numero = parseInt(elPaginaInput.value, 10);
        if (!Number.isNaN(numero)) irParaPagina(numero);
        else elPaginaInput.value = String(paginaAtual);
    });
    elPaginaInput.addEventListener("blur", () => {
        elPaginaInput.value = String(paginaAtual);
    });

    // --- Zoom, ajuste, rotação ---

    btnZoomMais.addEventListener("click", () => {
        modoAjuste = "manual";
        escalaAtual = Math.min(escalaAtual * 1.15, 5);
        renderizarPagina(paginaAtual);
    });
    btnZoomMenos.addEventListener("click", () => {
        modoAjuste = "manual";
        escalaAtual = Math.max(escalaAtual / 1.15, 0.2);
        renderizarPagina(paginaAtual);
    });
    btnAjustarLargura.addEventListener("click", () => {
        modoAjuste = "largura";
        renderizarPagina(paginaAtual);
    });
    btnAjustarPagina.addEventListener("click", () => {
        modoAjuste = "pagina";
        renderizarPagina(paginaAtual);
    });
    btnRotacionar.addEventListener("click", () => {
        rotacao = (rotacao + 90) % 360;
        renderizarPagina(paginaAtual);
    });

    // --- Tela cheia ---

    btnTelaCheia.addEventListener("click", async () => {
        try {
            if (!document.fullscreenElement) {
                await raiz.requestFullscreen();
            } else {
                await document.exitFullscreen();
            }
        } catch (e) {
            // Navegador recusou (política de permissão, etc.) — sem tratamento especial.
        }
    });
    const aoTrocarTelaCheia = () => {
        // O viewport do palco muda de tamanho com a tela cheia — refaz o fit.
        setTimeout(() => renderizarPagina(paginaAtual), 60);
    };
    document.addEventListener("fullscreenchange", aoTrocarTelaCheia);

    // ----------------------------------------------------------------------
    // Miniaturas (sob demanda, do MESMO pdfDocumento já carregado)
    // ----------------------------------------------------------------------

    let miniaturasRenderizadas = new Set();
    let observadorMiniaturas = null;

    function montarMiniaturas() {
        elMiniaturas.innerHTML = "";
        miniaturasRenderizadas = new Set();
        for (let n = 1; n <= pdfDocumento.numPages; n++) {
            const item = document.createElement("div");
            item.className = "pub-viewer-miniatura";
            item.dataset.pagina = String(n);
            const canvasMini = document.createElement("canvas");
            const rotulo = document.createElement("span");
            rotulo.className = "pub-viewer-miniatura-num";
            rotulo.textContent = String(n);
            item.append(canvasMini, rotulo);
            item.addEventListener("click", () => irParaPagina(n));
            elMiniaturas.appendChild(item);
        }
        if (observadorMiniaturas) observadorMiniaturas.disconnect();
        observadorMiniaturas = new IntersectionObserver(
            (entradas) => {
                entradas.forEach((entrada) => {
                    if (!entrada.isIntersecting) return;
                    const numero = parseInt(entrada.target.dataset.pagina, 10);
                    renderizarMiniatura(numero, entrada.target.querySelector("canvas"));
                });
            },
            { root: elMiniaturas, rootMargin: "200px 0px" }
        );
        elMiniaturas.querySelectorAll(".pub-viewer-miniatura").forEach((el) => observadorMiniaturas.observe(el));
    }

    async function renderizarMiniatura(numero, canvasEl) {
        if (miniaturasRenderizadas.has(numero)) return;
        miniaturasRenderizadas.add(numero);
        const minhaSeq = seqCarga;
        try {
            const pagina = await pdfDocumento.getPage(numero);
            if (minhaSeq !== seqCarga) return;
            const viewportBase = pagina.getViewport({ scale: 1 });
            const escala = 130 / viewportBase.width;
            const viewport = pagina.getViewport({ scale: escala });
            canvasEl.width = viewport.width;
            canvasEl.height = viewport.height;
            await pagina.render({ canvasContext: canvasEl.getContext("2d"), viewport }).promise;
        } catch (e) {
            miniaturasRenderizadas.delete(numero); // permite tentar de novo ao rolar de volta
        }
    }

    function atualizarMiniaturaAtiva() {
        elMiniaturas.querySelectorAll(".pub-viewer-miniatura").forEach((el) => {
            el.classList.toggle("is-atual", parseInt(el.dataset.pagina, 10) === paginaAtual);
        });
        const ativa = elMiniaturas.querySelector(".pub-viewer-miniatura.is-atual");
        if (ativa) ativa.scrollIntoView({ block: "nearest" });
    }

    // ----------------------------------------------------------------------
    // Busca de texto DENTRO do documento
    // ----------------------------------------------------------------------

    function snippetSeguro(bruto) {
        return escapeHtml(bruto).replaceAll("\x02", "<mark>").replaceAll("\x03", "</mark>");
    }

    async function executarBuscaNoDocumento(termo) {
        elBuscaLista.classList.add("is-aberto");
        elBuscaLista.innerHTML = '<div style="padding:0.5rem; color:var(--text-secondary);">Buscando…</div>';
        try {
            const params = new URLSearchParams({ q: termo, documento_id: docId, limit: "30" });
            const resposta = await apiFetch(`/publicacoes/api/busca?${params.toString()}`);
            if (resposta.results.length === 0) {
                elBuscaLista.innerHTML =
                    '<div style="padding:0.5rem; color:var(--text-secondary);">Nenhuma página encontrada.</div>';
                return;
            }
            elBuscaLista.innerHTML = "";
            resposta.results.forEach((r) => {
                const el = document.createElement("div");
                el.className = "pub-acervo-busca-resultado";
                el.innerHTML =
                    `<div class="pub-acervo-busca-resultado-titulo">Página ${r.page}</div>` +
                    `<div class="pub-acervo-busca-resultado-trecho">${snippetSeguro(r.snippet)}</div>`;
                el.addEventListener("click", () => {
                    elBuscaLista.classList.remove("is-aberto");
                    irParaPagina(r.page);
                });
                elBuscaLista.appendChild(el);
            });
        } catch (e) {
            elBuscaLista.innerHTML = '<div style="padding:0.5rem; color:var(--text-secondary);">Busca indisponível.</div>';
        }
    }

    let debounceBuscaDoc = null;
    elBuscaInput.addEventListener("input", () => {
        clearTimeout(debounceBuscaDoc);
        const termo = elBuscaInput.value.trim();
        if (termo.length < 3) {
            elBuscaLista.classList.remove("is-aberto");
            elBuscaLista.innerHTML = "";
            return;
        }
        debounceBuscaDoc = setTimeout(() => executarBuscaNoDocumento(termo), 400);
    });
    elBuscaInput.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        clearTimeout(debounceBuscaDoc);
        const termo = elBuscaInput.value.trim();
        if (termo) executarBuscaNoDocumento(termo);
    });
    const aoClicarFora = (e) => {
        if (!e.target.closest(".pub-viewer-busca-doc")) elBuscaLista.classList.remove("is-aberto");
    };
    document.addEventListener("click", aoClicarFora);

    // ----------------------------------------------------------------------
    // Favoritos (M3)
    // ----------------------------------------------------------------------

    function marcarIconeFavorito(ativo) {
        iconeFavorito.setAttribute("fill", ativo ? "currentColor" : "none");
        btnFavorito.title = ativo ? "Remover dos favoritos" : "Favoritar";
    }

    async function carregarEstadoFavorito() {
        const minhaSeq = seqCarga;
        try {
            const favoritos = await apiFetch("/publicacoes/api/favoritos");
            if (minhaSeq !== seqCarga) return;
            const existente = favoritos.find((f) => f.documento_id === docId);
            favoritoAtualId = existente ? existente.id : null;
            marcarIconeFavorito(!!existente);
        } catch (e) {
            // Silencioso: favoritos são um extra, não bloqueiam a leitura do documento.
        }
    }

    async function alternarFavorito() {
        try {
            if (favoritoAtualId) {
                await apiFetch(`/publicacoes/api/favoritos/${favoritoAtualId}`, { method: "DELETE" });
                favoritoAtualId = null;
                marcarIconeFavorito(false);
            } else {
                const criado = await apiFetch("/publicacoes/api/favoritos", {
                    method: "POST",
                    body: { documento_id: docId },
                });
                favoritoAtualId = criado.id;
                marcarIconeFavorito(true);
            }
        } catch (e) {
            // apiFetch já notificou.
        }
    }

    btnFavorito.addEventListener("click", alternarFavorito);

    // ----------------------------------------------------------------------
    // Metadados e carga do PDF
    // ----------------------------------------------------------------------

    async function carregarMetadados() {
        const minhaSeq = seqCarga;
        try {
            const meta = await apiFetch(`/publicacoes/api/documentos/${docId}`);
            if (minhaSeq !== seqCarga) return;
            elTitulo.textContent = meta.titulo;
            elSubtitulo.textContent =
                `${meta.manual.description} (${meta.manual.path}) · ${meta.capitulo || "sem capítulo"}`;
            if (!meta.edicao_vigente) {
                elRevisaoAnterior.textContent = TEXTO_REVISAO_ANTERIOR;
                elRevisaoAnterior.style.display = "block";
                if (meta.equivalente_vigente_id) {
                    const vigenteId = meta.equivalente_vigente_id;
                    const link = document.createElement("a");
                    link.href = `/publicacoes/viewer/${vigenteId}`;
                    link.textContent = " Abrir a edição vigente.";
                    link.style.marginLeft = "0.35rem";
                    if (aoTrocarDocumento) {
                        // Embutido: troca o PDF no painel em vez de sair da página.
                        link.addEventListener("click", (e) => {
                            e.preventDefault();
                            aoTrocarDocumento(vigenteId);
                        });
                    }
                    elRevisaoAnterior.appendChild(link);
                }
            }
        } catch (e) {
            elTitulo.textContent = "Documento";
        }
    }

    async function carregarPdf() {
        const minhaSeq = seqCarga;
        try {
            // `{ url }`, nunca a string crua — o atalho `getDocument("/caminho")`
            // foi removido no pdfjs-dist 5.x e o vendorizado aqui é o 6.2.108.
            const loadingTask = getDocument({ url: `/publicacoes/doc/${docId}/pdf` });
            const documento = await loadingTask.promise;
            if (minhaSeq !== seqCarga) {
                documento.destroy();
                return;
            }
            pdfDocumento = documento;
            elTotalPaginas.textContent = String(pdfDocumento.numPages);
            montarMiniaturas();
            await renderizarPagina(Math.max(1, Math.min(paginaAlvo, pdfDocumento.numPages)));
        } catch (e) {
            if (minhaSeq !== seqCarga) return;
            console.error("Falha ao carregar o PDF", e);
            elCorpo.style.display = "none";
            elErro.style.display = "block";
            elErro.textContent =
                "Não foi possível carregar este documento. Ele pode ter sido removido do acervo.";
        }
    }

    /**
     * Carrega (ou troca para) um documento. Zera página, zoom, rotação,
     * miniaturas e estado de favorito — o shell é reaproveitado, o estado não.
     */
    function abrir(novoDocId, { pagina = 1 } = {}) {
        seqCarga += 1;
        if (pdfDocumento) {
            pdfDocumento.destroy();
            pdfDocumento = null;
        }
        docId = novoDocId;
        paginaAlvo = pagina;
        paginaAtual = pagina;
        escalaAtual = 1.0;
        modoAjuste = "largura";
        rotacao = 0;
        renderizando = false;
        favoritoAtualId = null;

        elTitulo.textContent = "Carregando…";
        elSubtitulo.textContent = "";
        elPaginaInput.value = "—";
        elTotalPaginas.textContent = "—";
        elZoomNivel.textContent = "—";
        elMiniaturas.innerHTML = "";
        elBuscaInput.value = "";
        elBuscaLista.innerHTML = "";
        elBuscaLista.classList.remove("is-aberto");
        elRevisaoAnterior.innerHTML = "";
        elRevisaoAnterior.style.display = "none";
        elErro.style.display = "none";
        elCorpo.style.display = "";
        marcarIconeFavorito(false);
        linkDownload.href = `/publicacoes/doc/${docId}/pdf`;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        carregarMetadados();
        carregarPdf();
        carregarEstadoFavorito();
    }

    function destruir() {
        seqCarga += 1;
        if (observadorMiniaturas) observadorMiniaturas.disconnect();
        if (pdfDocumento) {
            pdfDocumento.destroy();
            pdfDocumento = null;
        }
        window.removeEventListener("resize", aoRedimensionar);
        if (sincronizarHash) window.removeEventListener("hashchange", aoMudarHash);
        document.removeEventListener("fullscreenchange", aoTrocarTelaCheia);
        document.removeEventListener("click", aoClicarFora);
    }

    return { abrir, destruir, docIdAtual: () => docId };
}

// --------------------------------------------------------------------------
// Bootstrap da página dedicada (/publicacoes/viewer/{id})
//
// No explorador o mesmo `#pub-viewer-context` existe SEM `data-doc-id` — lá
// quem chama `criarViewer()` é `publicacoes_explorador.js`, e este bloco não
// deve montar nada.
// --------------------------------------------------------------------------

const contexto = document.getElementById("pub-viewer-context");
if (contexto && contexto.dataset.docId) {
    const viewer = criarViewer({
        raiz: document.getElementById("pub-viewer-shell"),
        workerSrc: contexto.dataset.workerSrc,
        sincronizarHash: true,
    });
    viewer.abrir(contexto.dataset.docId, { pagina: paginaDaHash() });
}
