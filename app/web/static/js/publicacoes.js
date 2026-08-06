/**
 * app/web/static/js/publicacoes.js
 * Busca unificada do acervo de manuais + resolução de mensagem do FIM.
 *
 * O snippet devolvido pela API vem com sentinelas de controle (\x02/\x03),
 * NUNCA com <mark> cru — é a única forma segura de realçar o termo sem abrir
 * XSS pelo texto extraído do PDF (ou, nas avulsas, digitado por usuário).
 * Por isso o realce aqui segue a mesma receita do resto do projeto: escapar
 * tudo primeiro, só então trocar os sentinelas pela tag.
 */
(function () {
    "use strict";

    const contexto = document.getElementById("publicacoes-context");
    const inputBusca = document.getElementById("pub-busca-input");
    const filtroManual = document.getElementById("pub-filtro-manual");
    const filtroCapitulo = document.getElementById("pub-filtro-capitulo");
    const filtroAta = document.getElementById("pub-filtro-ata");
    const botaoBusca = document.getElementById("pub-busca-btn");
    const statusVazio = document.getElementById("pub-status-vazio");
    const resultadosMeta = document.getElementById("pub-resultados-meta");
    const resultadosLista = document.getElementById("pub-resultados-lista");

    const inputFim = document.getElementById("pub-fim-input");
    const botaoFim = document.getElementById("pub-fim-btn");
    const resultadosFim = document.getElementById("pub-fim-resultados");

    if (!contexto) return;

    function snippetSeguro(bruto) {
        return escapeHtml(bruto)
            .replaceAll("\x02", "<mark>")
            .replaceAll("\x03", "</mark>");
    }

    async function verificarStatus() {
        try {
            const resposta = await apiFetch(contexto.dataset.statusUrl);
            if (!resposta.indice_disponivel) {
                statusVazio.style.display = "block";
            }
        } catch (e) {
            // apiFetch já mostra o toast; a busca simplesmente não encontrará nada.
        }
    }

    function montarUrlBusca() {
        const params = new URLSearchParams({ q: inputBusca.value.trim() });
        if (filtroManual.value.trim()) params.set("manual", filtroManual.value.trim());
        if (filtroCapitulo.value.trim()) params.set("capitulo", filtroCapitulo.value.trim());
        if (filtroAta.value.trim()) params.set("ata", filtroAta.value.trim());
        return `/publicacoes/api/busca?${params.toString()}`;
    }

    function renderResultado(item) {
        const div = document.createElement("div");
        div.className = "card";
        div.style.marginBottom = "0.5rem";
        div.style.cursor = "pointer";
        div.innerHTML = `
            <div style="display:flex; justify-content:space-between; gap:0.5rem; flex-wrap:wrap;">
                <strong>${escapeHtml(item.title)}</strong>
                <span style="color:var(--text-secondary); font-size:0.85rem;">
                    ${escapeHtml(item.manual.path)} · ${escapeHtml(item.chapter || "—")} · pág. ${item.page ?? "—"}
                </span>
            </div>
            <div style="margin-top:0.35rem; color:var(--text-secondary);">${snippetSeguro(item.snippet)}</div>
        `;
        div.addEventListener("click", () => {
            window.location.href = item.viewer_url;
        });
        return div;
    }

    async function buscar() {
        const termo = inputBusca.value.trim();
        if (!termo) {
            showToast("Digite um termo de busca.", "info");
            return;
        }
        resultadosLista.innerHTML = "";
        resultadosMeta.textContent = "Buscando…";
        try {
            const resposta = await apiFetch(montarUrlBusca());
            resultadosMeta.textContent = `${resposta.total} resultado(s) em ${resposta.took_ms} ms`;
            if (resposta.results.length === 0) {
                resultadosLista.innerHTML =
                    '<div class="card" style="text-align:center; color:var(--text-secondary);">Nenhum resultado.</div>';
                return;
            }
            resposta.results.forEach((item) => resultadosLista.appendChild(renderResultado(item)));
        } catch (e) {
            resultadosMeta.textContent = "";
        }
    }

    async function resolverFim() {
        const mensagem = inputFim.value.trim();
        if (!mensagem) {
            showToast("Digite a mensagem exibida no CAS/EICAS.", "info");
            return;
        }
        resultadosFim.innerHTML = "";
        try {
            const resposta = await apiFetch(
                `/publicacoes/api/fim?${new URLSearchParams({ mensagem }).toString()}`
            );
            if (resposta.results.length === 0) {
                resultadosFim.innerHTML =
                    '<div style="color:var(--text-secondary);">Nenhuma mensagem encontrada com esse prefixo.</div>';
                return;
            }
            resposta.results.forEach((item) => {
                const linha = document.createElement("div");
                linha.style.padding = "0.4rem 0";
                linha.style.borderBottom = "1px solid var(--border-color)";
                const alvo = item.viewer_url
                    ? `<a href="${item.viewer_url}">${escapeHtml(item.title || item.procedimento)}</a>`
                    : `${escapeHtml(item.procedimento)} <em style="color:var(--text-secondary);">(sem PDF no acervo)</em>`;
                linha.innerHTML = `<strong>${escapeHtml(item.mensagem)}</strong> → ${alvo}`;
                resultadosFim.appendChild(linha);
            });
        } catch (e) {
            // apiFetch já notificou.
        }
    }

    botaoBusca.addEventListener("click", buscar);
    inputBusca.addEventListener("keydown", (e) => {
        if (e.key === "Enter") buscar();
    });
    botaoFim.addEventListener("click", resolverFim);
    inputFim.addEventListener("keydown", (e) => {
        if (e.key === "Enter") resolverFim();
    });

    verificarStatus();
})();
