/**
 * app/web/static/js/publicacoes_viewer.js
 * Viewer de PDF em <canvas>, via PDF.js vendorizado.
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
 */
import { GlobalWorkerOptions, getDocument } from "/static/js/pdfjs/pdf.min.mjs";

const contexto = document.getElementById("pub-viewer-context");
if (contexto) {
    GlobalWorkerOptions.workerSrc = contexto.dataset.workerSrc;

    const canvas = document.getElementById("pub-viewer-canvas");
    const ctx = canvas.getContext("2d");
    const elTitulo = document.getElementById("pub-viewer-titulo");
    const elSubtitulo = document.getElementById("pub-viewer-subtitulo");
    const elPagina = document.getElementById("pub-viewer-pagina");
    const elErro = document.getElementById("pub-viewer-erro");
    const elRevisaoAnterior = document.getElementById("pub-viewer-revisao-anterior");
    const btnPrev = document.getElementById("pub-viewer-prev");
    const btnNext = document.getElementById("pub-viewer-next");
    const linkDownload = document.getElementById("pub-viewer-download");
    const btnFavorito = document.getElementById("pub-viewer-favorito");
    const iconeFavorito = document.getElementById("pub-viewer-favorito-icone");

    linkDownload.href = contexto.dataset.pdfUrl;

    let pdfDocumento = null;
    let paginaAtual = 1;
    let renderizando = false;

    function paginaDaHash() {
        const m = /page=(\d+)/.exec(window.location.hash);
        return m ? parseInt(m[1], 10) : 1;
    }

    async function renderizarPagina(numero) {
        if (!pdfDocumento || renderizando) return;
        renderizando = true;
        try {
            const pagina = await pdfDocumento.getPage(numero);
            // Ajusta a escala à largura disponível, com teto de nitidez em
            // telas de alta densidade (devicePixelRatio).
            const larguraDisponivel = Math.min(document.body.clientWidth - 96, 1100);
            const viewportBase = pagina.getViewport({ scale: 1 });
            const escala = Math.max(larguraDisponivel / viewportBase.width, 0.5);
            const dpr = window.devicePixelRatio || 1;
            const viewport = pagina.getViewport({ scale: escala * dpr });

            canvas.width = viewport.width;
            canvas.height = viewport.height;
            canvas.style.width = `${viewport.width / dpr}px`;
            canvas.style.height = `${viewport.height / dpr}px`;

            await pagina.render({ canvasContext: ctx, viewport }).promise;
            paginaAtual = numero;
            elPagina.textContent = `${paginaAtual} / ${pdfDocumento.numPages}`;
            window.history.replaceState(null, "", `#page=${paginaAtual}`);
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
    window.addEventListener("resize", () => renderizarPagina(paginaAtual));

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
            const loadingTask = getDocument(contexto.dataset.pdfUrl);
            pdfDocumento = await loadingTask.promise;
            await renderizarPagina(Math.max(1, Math.min(paginaDaHash(), pdfDocumento.numPages)));
        } catch (e) {
            console.error("Falha ao carregar o PDF", e);
            canvas.style.display = "none";
            elErro.style.display = "block";
            elErro.textContent =
                "Não foi possível carregar este documento. Ele pode ter sido removido do acervo.";
        }
    }

    carregarMetadados();
    carregarPdf();
    carregarEstadoFavorito();
}
