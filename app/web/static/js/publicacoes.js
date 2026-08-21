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

    // `mobile/publicacoes.html` reusa este arquivo; a lista de resultados é
    // renderizada aqui via JS (não no template), então precisa saber em qual
    // casca está rodando para usar `.mobile-card` (fundo escuro) em vez de
    // `.card` (fundo branco do desktop) e as variáveis de cor certas.
    const isMobile = document.body.classList.contains("mobile-body");
    const corSecundaria = isMobile ? "var(--mobile-text-muted)" : "var(--text-secondary)";
    const corBorda = isMobile ? "var(--mobile-card-border-soft)" : "var(--border-color)";

    async function popularFiltroManuais() {
        // Se o filtro é um <input> livre (versão antiga do mobile), não há o
        // que popular — este só é um <select> na versão convertida da Etapa 2.
        if (!filtroManual || filtroManual.tagName !== "SELECT") return;
        try {
            const manuais = await apiFetch("/publicacoes/api/manuais");
            manuais.forEach((m) => {
                const opcao = document.createElement("option");
                opcao.value = m.codigo;
                // O mesmo código pode existir duas vezes (Manutenção/Operacional,
                // ver docs/backlog/modulo_publicacoes/12_refinamento_gestao_e_envio.md
                // §6) — a origem no rótulo evita duas opções com o mesmo texto.
                const origemRotulo = m.origem === "OPERACIONAL" ? "Operacional" : "Manutenção";
                opcao.textContent = `${m.descricao} (${m.codigo}) · ${origemRotulo}`;
                filtroManual.appendChild(opcao);
            });
        } catch (e) {
            // Sem manuais indexados: os selects ficam vazios, a busca livre continua funcionando.
        }
    }

    async function popularFiltroCapitulos(codigoManual) {
        if (!filtroCapitulo || filtroCapitulo.tagName !== "SELECT") return;
        filtroCapitulo.innerHTML = '<option value="">Todos</option>';
        if (!codigoManual) {
            filtroCapitulo.disabled = true;
            return;
        }
        try {
            const resposta = await apiFetch(
                `/publicacoes/api/manuais/${encodeURIComponent(codigoManual)}/capitulos`
            );
            resposta.capitulos.forEach((c) => {
                const opcao = document.createElement("option");
                opcao.value = c.capitulo;
                const rotulo = c.capitulo || "(raiz do manual)";
                opcao.textContent = c.ata_codigo ? `ATA ${c.ata_codigo} — ${rotulo}` : rotulo;
                filtroCapitulo.appendChild(opcao);
            });
            filtroCapitulo.disabled = false;
        } catch (e) {
            filtroCapitulo.disabled = true;
        }
    }

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
        div.className = isMobile ? "mobile-card" : "card";
        div.style.marginBottom = "0.5rem";
        div.style.cursor = "pointer";
        div.innerHTML = `
            <div style="display:flex; justify-content:space-between; gap:0.5rem; flex-wrap:wrap;">
                <strong>${escapeHtml(item.title)}</strong>
                <span style="color:${corSecundaria}; font-size:0.85rem;">
                    ${escapeHtml(item.manual.path)} · ${escapeHtml(item.chapter || "—")} · pág. ${item.page ?? "—"}
                </span>
            </div>
            <div style="margin-top:0.35rem; color:${corSecundaria};">${snippetSeguro(item.snippet)}</div>
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
                const classeVazia = isMobile ? "mobile-card" : "card";
                resultadosLista.innerHTML =
                    `<div class="${classeVazia}" style="text-align:center; color:${corSecundaria};">Nenhum resultado.</div>`;
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
                    `<div style="color:${corSecundaria};">Nenhuma mensagem encontrada com esse prefixo.</div>`;
                return;
            }
            resposta.results.forEach((item) => {
                const linha = document.createElement("div");
                linha.style.padding = "0.4rem 0";
                linha.style.borderBottom = `1px solid ${corBorda}`;
                const corLink = isMobile ? "color:var(--mobile-accent-soft);" : "";
                const alvo = item.viewer_url
                    ? `<a href="${item.viewer_url}" style="${corLink}">${escapeHtml(item.title || item.procedimento)}</a>`
                    : `${escapeHtml(item.procedimento)} <em style="color:${corSecundaria};">(sem PDF no acervo)</em>`;
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
    if (filtroManual && filtroManual.tagName === "SELECT") {
        filtroManual.addEventListener("change", () => popularFiltroCapitulos(filtroManual.value));
    }

    verificarStatus();
    popularFiltroManuais();

    // Pré-preenche e dispara a busca quando a página é aberta com `?q=...`
    // — usado pelo link "Buscar no manual" do checklist de inspeção (M3
    // tarefa 3), que não tem como saber qual documento corresponde ao item
    // sem rodar a busca de verdade.
    const paramsIniciais = new URLSearchParams(window.location.search);
    const qInicial = paramsIniciais.get("q");
    if (qInicial) {
        inputBusca.value = qInicial;
        buscar();
    }
})();
