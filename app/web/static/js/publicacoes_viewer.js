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
 */
import { GlobalWorkerOptions, getDocument } from "/static/js/pdfjs/pdf.min.mjs";

const contexto = document.getElementById("pub-viewer-context");
if (contexto) {
    GlobalWorkerOptions.workerSrc = contexto.dataset.workerSrc;

    const elShell = document.getElementById("pub-viewer-shell");
    const elPalco = document.getElementById("pub-viewer-palco");
    const canvas = document.getElementById("pub-viewer-canvas");
    const ctx = canvas.getContext("2d");
    const elMiniaturas = document.getElementById("pub-viewer-miniaturas");
    const elTitulo = document.getElementById("pub-viewer-titulo");
    const elSubtitulo = document.getElementById("pub-viewer-subtitulo");
    const elPaginaInput = document.getElementById("pub-viewer-pagina-input");
    const elTotalPaginas = document.getElementById("pub-viewer-total-paginas");
    const elZoomNivel = document.getElementById("pub-viewer-zoom-nivel");
    const elErro = document.getElementById("pub-viewer-erro");
    const elRevisaoAnterior = document.getElementById("pub-viewer-revisao-anterior");
    const btnPrev = document.getElementById("pub-viewer-prev");
    const btnNext = document.getElementById("pub-viewer-next");
    const btnZoomMais = document.getElementById("pub-viewer-zoom-mais");
    const btnZoomMenos = document.getElementById("pub-viewer-zoom-menos");
    const btnAjustarLargura = document.getElementById("pub-viewer-ajustar-largura");
    const btnAjustarPagina = document.getElementById("pub-viewer-ajustar-pagina");
    const btnRotacionar = document.getElementById("pub-viewer-rotacionar");
    const btnTelaCheia = document.getElementById("pub-viewer-tela-cheia");
    const linkDownload = document.getElementById("pub-viewer-download");
    const btnFavorito = document.getElementById("pub-viewer-favorito");
    const iconeFavorito = document.getElementById("pub-viewer-favorito-icone");
    const elBuscaInput = document.getElementById("pub-viewer-busca-input");
    const elBuscaLista = document.getElementById("pub-viewer-busca-lista");

    linkDownload.href = contexto.dataset.pdfUrl;

    let pdfDocumento = null;
    let paginaAtual = 1;
    let escalaAtual = 1.0;
    let modoAjuste = "largura"; // "largura" | "pagina" | "manual"
    let rotacao = 0;
    let renderizando = false;

    function paginaDaHash() {
        const m = /page=(\d+)/.exec(window.location.hash);
        return m ? parseInt(m[1], 10) : 1;
    }

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
        try {
            const pagina = await pdfDocumento.getPage(numero);
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
            paginaAtual = numero;
            elPaginaInput.value = String(paginaAtual);
            elZoomNivel.textContent = `${Math.round(escala * 100)}%`;
            window.history.replaceState(null, "", `#page=${paginaAtual}`);
            atualizarMiniaturaAtiva();
        } catch (e) {
            console.error("Falha ao renderizar página", numero, e);
            showToast("Falha ao renderizar a página do PDF.", "error");
        } finally {
            renderizando = false;
        }
    }

    function irPara(numero) {
        if (!pdfDocumento) return;
        const alvo = Math.max(1, Math.min(numero, pdfDocumento.numPages));
        renderizarPagina(alvo);
    }

    btnPrev.addEventListener("click", () => irPara(paginaAtual - 1));
    btnNext.addEventListener("click", () => irPara(paginaAtual + 1));
    window.addEventListener("hashchange", () => irPara(paginaDaHash()));

    let debounceResize = null;
    window.addEventListener("resize", () => {
        clearTimeout(debounceResize);
        debounceResize = setTimeout(() => renderizarPagina(paginaAtual), 150);
    });

    elPaginaInput.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        const numero = parseInt(elPaginaInput.value, 10);
        if (!Number.isNaN(numero)) irPara(numero);
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
                await elShell.requestFullscreen();
            } else {
                await document.exitFullscreen();
            }
        } catch (e) {
            // Navegador recusou (política de permissão, etc.) — sem tratamento especial.
        }
    });
    document.addEventListener("fullscreenchange", () => {
        // O viewport do palco muda de tamanho com a tela cheia — refaz o fit.
        setTimeout(() => renderizarPagina(paginaAtual), 60);
    });

    // --- Miniaturas (sob demanda, do MESMO pdfDocumento já carregado) ---

    const miniaturasRenderizadas = new Set();
    let observadorMiniaturas = null;

    function montarMiniaturas() {
        elMiniaturas.innerHTML = "";
        for (let n = 1; n <= pdfDocumento.numPages; n++) {
            const item = document.createElement("div");
            item.className = "pub-viewer-miniatura";
            item.dataset.pagina = String(n);
            const canvasMini = document.createElement("canvas");
            const rotulo = document.createElement("span");
            rotulo.className = "pub-viewer-miniatura-num";
            rotulo.textContent = String(n);
            item.append(canvasMini, rotulo);
            item.addEventListener("click", () => irPara(n));
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
        try {
            const pagina = await pdfDocumento.getPage(numero);
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

    // --- Busca de texto DENTRO do documento ---

    function snippetSeguro(bruto) {
        return escapeHtml(bruto).replaceAll("\x02", "<mark>").replaceAll("\x03", "</mark>");
    }

    async function executarBuscaNoDocumento(termo) {
        elBuscaLista.classList.add("is-aberto");
        elBuscaLista.innerHTML = '<div style="padding:0.5rem; color:var(--text-secondary);">Buscando…</div>';
        try {
            const params = new URLSearchParams({ q: termo, documento_id: contexto.dataset.docId, limit: "30" });
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
                    irPara(r.page);
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
    document.addEventListener("click", (e) => {
        if (!e.target.closest(".pub-viewer-busca-doc")) elBuscaLista.classList.remove("is-aberto");
    });

    // --- Favoritos (M3) ---

    let favoritoAtualId = null;

    function marcarIconeFavorito(ativo) {
        iconeFavorito.setAttribute("fill", ativo ? "currentColor" : "none");
        btnFavorito.title = ativo ? "Remover dos favoritos" : "Favoritar";
    }

    async function carregarEstadoFavorito() {
        try {
            const favoritos = await apiFetch("/publicacoes/api/favoritos");
            const existente = favoritos.find((f) => f.documento_id === contexto.dataset.docId);
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
                    body: { documento_id: contexto.dataset.docId },
                });
                favoritoAtualId = criado.id;
                marcarIconeFavorito(true);
            }
        } catch (e) {
            // apiFetch já notificou.
        }
    }

    btnFavorito.addEventListener("click", alternarFavorito);

    // --- Metadados e carga do PDF ---

    async function carregarMetadados() {
        try {
            const meta = await apiFetch(`/publicacoes/api/documentos/${contexto.dataset.docId}`);
            elTitulo.textContent = meta.titulo;
            elSubtitulo.textContent =
                `${meta.manual.description} (${meta.manual.path}) · ${meta.capitulo || "sem capítulo"}`;
            if (!meta.edicao_vigente) {
                elRevisaoAnterior.style.display = "block";
                if (meta.equivalente_vigente_id) {
                    const link = document.createElement("a");
                    link.href = `/publicacoes/viewer/${meta.equivalente_vigente_id}`;
                    link.textContent = " Abrir a edição vigente.";
                    link.style.marginLeft = "0.35rem";
                    elRevisaoAnterior.appendChild(link);
                }
            }
        } catch (e) {
            elTitulo.textContent = "Documento";
        }
    }

    async function carregarPdf() {
        try {
            // `{ url }`, nunca a string crua — o atalho `getDocument("/caminho")`
            // foi removido no pdfjs-dist 5.x e o vendorizado aqui é o 6.2.108.
            const loadingTask = getDocument({ url: contexto.dataset.pdfUrl });
            pdfDocumento = await loadingTask.promise;
            elTotalPaginas.textContent = String(pdfDocumento.numPages);
            montarMiniaturas();
            await renderizarPagina(Math.max(1, Math.min(paginaDaHash(), pdfDocumento.numPages)));
        } catch (e) {
            console.error("Falha ao carregar o PDF", e);
            elPalco.style.display = "none";
            elErro.style.display = "block";
            elErro.textContent =
                "Não foi possível carregar este documento. Ele pode ter sido removido do acervo.";
        }
    }

    carregarMetadados();
    carregarPdf();
    carregarEstadoFavorito();
}
