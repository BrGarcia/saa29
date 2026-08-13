/**
 * app/web/static/js/encarregado.js
 * Ciência de Alterações — lista pendências (RN-ENC-01/02), registra e desfaz
 * ciência (RN-ENC-03/04). Módulo é read-only sobre os dados de origem: a
 * única escrita é POST/DELETE em /api/v1/encarregado/ciencia.
 */
(function () {
    "use strict";

    const CATEGORIAS = ["PANES", "INSPECAO", "INVENTARIO", "VENCIMENTOS"];

    const totalEl = document.getElementById("enc-total");
    if (!totalEl) return; // página não é esta

    const undoBar = document.getElementById("enc-undo-bar");
    const undoTexto = document.getElementById("enc-undo-texto");
    const undoBtn = document.getElementById("enc-undo-btn");

    let ultimaCiencia = null; // { id } — usado pelo botão Desfazer
    let undoTimeout = null;

    function podeDarCiencia() {
        // ADMINISTRADOR também passa: window.hasPermission trata ADMINISTRADOR
        // como acesso total independente do papel exigido (auth_check.js).
        return typeof window.hasPermission === "function" && window.hasPermission("ENCARREGADO");
    }

    function formatarData(iso) {
        if (!iso) return "—";
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;
        return d.toLocaleString("pt-BR", {
            day: "2-digit", month: "2-digit", year: "numeric",
            hour: "2-digit", minute: "2-digit",
        });
    }

    function iconeCheck() {
        return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            + 'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            + '<path d="M20 6L9 17l-5-5"></path></svg>';
    }

    function renderCard(item) {
        const div = document.createElement("div");
        div.className = "enc-card";
        div.dataset.categoria = item.categoria;
        div.dataset.evento = item.evento;
        div.dataset.registroId = item.registro_id;

        const meta = [escapeHtml(item.responsavel_trigrama || "—"), formatarData(item.data_evento)];

        const detalheHtml = item.detalhe
            ? `<div class="enc-card-detalhe">${escapeHtml(item.detalhe)}</div>`
            : "";
        const botaoHtml = podeDarCiencia()
            ? `<button type="button" class="enc-btn-visto" data-action="visto" aria-label="Dar ciência" title="Dar ciência">${iconeCheck()}</button>`
            : "";

        div.innerHTML = `
            <div class="enc-card-main">
                <div class="enc-card-linha1">
                    <span class="enc-card-aeronave">${escapeHtml(item.aeronave_matricula || "—")}</span>
                    <span class="enc-card-titulo">${escapeHtml(item.titulo)}</span>
                </div>
                ${detalheHtml}
                <div class="enc-card-meta">${meta.join(" · ")}</div>
            </div>
            ${botaoHtml}
        `;
        return div;
    }

    function renderCategoria(categoria, itens) {
        const container = document.getElementById(`cards-${categoria}`);
        const contador = document.getElementById(`contador-${categoria}`);
        if (!container || !contador) return;

        container.innerHTML = "";
        contador.textContent = String(itens.length);
        contador.classList.toggle("tem-pendencia", itens.length > 0);

        if (itens.length === 0) {
            container.innerHTML = '<div class="estado-vazio">Nenhuma alteração pendente de ciência.</div>';
            return;
        }
        itens.forEach((item) => container.appendChild(renderCard(item)));
    }

    async function carregar() {
        try {
            const resposta = await apiFetch("/api/v1/encarregado/pendentes");
            totalEl.textContent = String(resposta.total);
            CATEGORIAS.forEach((categoria) => {
                renderCategoria(categoria, resposta.itens_por_categoria[categoria] || []);
            });
        } catch (e) {
            CATEGORIAS.forEach((categoria) => {
                const container = document.getElementById(`cards-${categoria}`);
                if (container) container.innerHTML = '<div class="estado-vazio">Falha ao carregar.</div>';
            });
        }
    }

    function esconderUndo() {
        undoBar.style.display = "none";
        ultimaCiencia = null;
        clearTimeout(undoTimeout);
    }

    function mostrarUndo(ciencia, tituloItem) {
        ultimaCiencia = ciencia;
        undoTexto.textContent = `Ciência registrada: ${tituloItem}`;
        undoBar.style.display = "flex";
        clearTimeout(undoTimeout);
        undoTimeout = setTimeout(esconderUndo, 8000);
    }

    async function darCiencia(cardEl) {
        const categoria = cardEl.dataset.categoria;
        const evento = cardEl.dataset.evento;
        const registroId = cardEl.dataset.registroId;
        const tituloEl = cardEl.querySelector(".enc-card-titulo");
        const tituloItem = tituloEl ? tituloEl.textContent : "";

        try {
            const ciencia = await apiFetch("/api/v1/encarregado/ciencia", {
                method: "POST",
                body: { categoria, evento, registro_id: registroId },
            });
            cardEl.classList.add("enc-card-saindo");
            mostrarUndo(ciencia, tituloItem);
            setTimeout(carregar, 220);
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    async function desfazerUltima() {
        if (!ultimaCiencia) return;
        try {
            await apiFetch(`/api/v1/encarregado/ciencia/${ultimaCiencia.id}`, { method: "DELETE" });
            showToast("Ciência desfeita.", "success");
            esconderUndo();
            await carregar();
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    document.querySelectorAll(".enc-cards").forEach((container) => {
        container.addEventListener("click", (e) => {
            const botao = e.target.closest('[data-action="visto"]');
            if (!botao) return;
            const card = botao.closest(".enc-card");
            if (card) darCiencia(card);
        });
    });

    if (undoBtn) undoBtn.addEventListener("click", desfazerUltima);

    // auth_check.js só popula localStorage["saa29_user"] (usado por
    // podeDarCiencia -> window.hasPermission) no seu próprio listener de
    // DOMContentLoaded. Como esta IIFE roda durante o parsing do <script>,
    // chamar carregar() direto aqui poderia, em tese, renderizar os cards
    // antes desse listener rodar. Adiar para DOMContentLoaded garante que
    // o fetch de /auth/me (registrado antes, em auth_check.js) já foi
    // iniciado quando o nosso começa.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", carregar);
    } else {
        carregar();
    }
})();
