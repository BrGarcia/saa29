/**
 * app/web/static/js/publicacoes_avulsas.js
 * Cadastro e busca de publicações avulsas (BO/BS/NPO/BT).
 *
 * `snippetSeguro` é a MESMA receita de `publicacoes.js` (escapar tudo, só
 * então trocar sentinela por `<mark>`) — a ementa é entrada de usuário e vai
 * direto para o snippet da busca (achado B8), exatamente como o texto do
 * PDF no acervo A.
 */
(function () {
    "use strict";

    const URL_API = "/publicacoes/api/avulsas";

    const filtroNumero = document.getElementById("av-filtro-numero");
    const filtroAno = document.getElementById("av-filtro-ano");
    const filtroTipo = document.getElementById("av-filtro-tipo");
    const filtroAta = document.getElementById("av-filtro-ata");
    const filtroTexto = document.getElementById("av-filtro-texto");
    const botaoBusca = document.getElementById("av-busca-btn");
    const botaoNovo = document.getElementById("av-novo-btn");
    const resultadosMeta = document.getElementById("av-resultados-meta");
    const resultadosLista = document.getElementById("av-resultados-lista");

    const modalForm = document.getElementById("modal-avulsa");
    const form = document.getElementById("form-avulsa");
    const modalDetalhe = document.getElementById("modal-avulsa-detalhe");

    if (!resultadosLista) return; // página não é esta

    function snippetSeguro(bruto) {
        return escapeHtml(bruto)
            .replaceAll("\x02", "<mark>")
            .replaceAll("\x03", "</mark>");
    }

    function montarUrlBusca() {
        const params = new URLSearchParams();
        if (filtroNumero.value.trim()) params.set("numero", filtroNumero.value.trim());
        if (filtroAno.value) params.set("ano", filtroAno.value);
        if (filtroTipo.value) params.set("tipo", filtroTipo.value);
        if (filtroAta.value.trim()) params.set("ata", filtroAta.value.trim());
        if (filtroTexto.value.trim()) params.set("texto", filtroTexto.value.trim());
        return `${URL_API}?${params.toString()}`;
    }

    function renderResultado(item) {
        const div = document.createElement("div");
        div.className = "card";
        div.style.marginBottom = "0.5rem";
        div.style.cursor = "pointer";
        const snippetHtml = item.snippet
            ? `<div style="margin-top:0.35rem; color:var(--text-secondary);">${snippetSeguro(item.snippet)}</div>`
            : "";
        div.innerHTML = `
            <div style="display:flex; justify-content:space-between; gap:0.5rem; flex-wrap:wrap;">
                <strong>${escapeHtml(item.tipo)} ${escapeHtml(item.numero)}/${item.ano}</strong>
                <span style="color:var(--text-secondary); font-size:0.85rem;">${escapeHtml(item.status)}</span>
            </div>
            <div>${escapeHtml(item.titulo)}</div>
            ${snippetHtml}
        `;
        div.addEventListener("click", () => abrirDetalhe(item.id));
        return div;
    }

    async function buscar() {
        resultadosLista.innerHTML = "";
        resultadosMeta.textContent = "Buscando…";
        try {
            const resposta = await apiFetch(montarUrlBusca());
            resultadosMeta.textContent = `${resposta.total} resultado(s)`;
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

    // --- Cadastro ---

    function abrirModalCadastro() {
        form.reset();
        modalForm.style.display = "flex";
    }

    function fecharModalCadastro() {
        modalForm.style.display = "none";
    }

    async function salvarAvulsa(e) {
        e.preventDefault();
        const dados = {
            tipo: document.getElementById("av-tipo").value,
            numero: document.getElementById("av-numero").value,
            ano: parseInt(document.getElementById("av-ano").value, 10),
            emissor: document.getElementById("av-emissor").value,
            data_emissao: document.getElementById("av-data-emissao").value,
            data_recebimento: document.getElementById("av-data-recebimento").value,
            titulo: document.getElementById("av-titulo").value,
            ementa: document.getElementById("av-ementa").value,
        };
        try {
            await apiFetch(URL_API, { method: "POST", body: dados });
            showToast("Publicação cadastrada.", "success");
            fecharModalCadastro();
            buscar();
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    // --- Detalhe / anexos ---

    let avulsaAtualId = null;

    async function abrirDetalhe(id) {
        avulsaAtualId = id;
        try {
            const avulsa = await apiFetch(`${URL_API}/${id}`);
            document.getElementById("detalhe-avulsa-titulo").textContent =
                `${avulsa.tipo} ${avulsa.numero}/${avulsa.ano}`;
            document.getElementById("detalhe-avulsa-corpo").innerHTML = `
                <p><strong>${escapeHtml(avulsa.titulo)}</strong></p>
                <p>${escapeHtml(avulsa.ementa)}</p>
                <p style="color:var(--text-secondary); font-size:0.85rem;">
                    Emissor: ${escapeHtml(avulsa.emissor)} · Recebido em ${escapeHtml(avulsa.data_recebimento)} ·
                    Status: ${escapeHtml(avulsa.status)}
                </p>
            `;
            const listaAnexos = document.getElementById("detalhe-avulsa-anexos");
            listaAnexos.innerHTML = avulsa.anexos.length
                ? ""
                : '<p style="color:var(--text-secondary);">Sem anexos.</p>';
            avulsa.anexos.forEach((anexo) => {
                const link = document.createElement("a");
                link.href = `/publicacoes/avulsas/${avulsa.id}/anexo/${anexo.id}`;
                link.target = "_blank";
                link.textContent = anexo.nome_original;
                link.style.display = "block";
                listaAnexos.appendChild(link);
            });

            // O `data-role` do botão de upload/exclusão já foi resolvido por
            // auth_check.js no carregamento da página (o elemento existe no
            // DOM desde o início, só o modal que o envolve estava oculto) —
            // não precisa reprocessar nada aqui.
            modalDetalhe.style.display = "flex";
        } catch (e) {
            // apiFetch já notificou.
        }
    }

    function fecharModalDetalhe() {
        modalDetalhe.style.display = "none";
        avulsaAtualId = null;
    }

    async function enviarAnexo() {
        const input = document.getElementById("input-novo-anexo");
        if (!avulsaAtualId || !input.files.length) {
            showToast("Selecione um arquivo.", "info");
            return;
        }
        const formData = new FormData();
        formData.append("arquivo", input.files[0]);
        try {
            await apiFetch(`${URL_API}/${avulsaAtualId}/anexos`, {
                method: "POST",
                body: formData,
            });
            showToast("Anexo enviado.", "success");
            input.value = "";
            abrirDetalhe(avulsaAtualId);
        } catch (e) {
            // apiFetch já notificou (inclui 413 de limite excedido e 422 de tipo inválido).
        }
    }

    async function excluirAvulsa() {
        if (!avulsaAtualId) return;
        if (!window.confirm("Excluir esta publicação? A ação move para inativo (soft delete).")) return;
        try {
            await apiFetch(`${URL_API}/${avulsaAtualId}`, { method: "DELETE" });
            showToast("Publicação excluída.", "success");
            fecharModalDetalhe();
            buscar();
        } catch (e) {
            // apiFetch já notificou.
        }
    }

    // --- Wiring ---

    botaoBusca.addEventListener("click", buscar);
    filtroTexto.addEventListener("keydown", (e) => {
        if (e.key === "Enter") buscar();
    });
    botaoNovo.addEventListener("click", abrirModalCadastro);
    document.getElementById("btn-close-modal-avulsa").addEventListener("click", fecharModalCadastro);
    document.getElementById("btn-cancel-modal-avulsa").addEventListener("click", fecharModalCadastro);
    form.addEventListener("submit", salvarAvulsa);

    document.getElementById("btn-close-modal-detalhe").addEventListener("click", fecharModalDetalhe);
    document.getElementById("btn-upload-anexo").addEventListener("click", enviarAnexo);
    document.getElementById("btn-excluir-avulsa").addEventListener("click", excluirAvulsa);

    buscar();
})();
