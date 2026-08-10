/**
 * app/web/static/js/pedidos.js
 * Central de Pedidos — filtros, resumo, CRUD e ciclo de vida (RN-05 a RN-13).
 */
(function () {
    "use strict";

    const body = document.getElementById("pedidos-body");
    if (!body) return; // página não é esta

    const cardTotal = document.getElementById("card-total");
    const cardPendentes = document.getElementById("card-pendentes");
    const cardAtendidos = document.getElementById("card-atendidos");
    const cardEmergencias = document.getElementById("card-emergencias");

    const filterAeronave = document.getElementById("filter-aeronave");
    const filterStatus = document.getElementById("filter-status");
    const filterTipo = document.getElementById("filter-tipo");
    const filterExcluidos = document.getElementById("filter-excluidos");
    const searchInput = document.getElementById("search-input");

    const paginationInfo = document.getElementById("pagination-info");
    const paginationControls = document.getElementById("pagination-controls");

    const modalPedido = document.getElementById("modal-pedido");
    const formPedido = document.getElementById("form-pedido");
    const modalPedidoTitulo = document.getElementById("modal-pedido-titulo");
    const inputPedidoId = document.getElementById("pedido-id");
    const inputAeronave = document.getElementById("input-aeronave");
    const inputPartNumber = document.getElementById("input-part-number");
    const inputNomenclatura = document.getElementById("input-nomenclatura");
    const inputQuantidade = document.getElementById("input-quantidade");
    const radioNormal = document.getElementById("radio-normal");
    const radioEmergencia = document.getElementById("radio-emergencia");
    const fieldEmergencia = document.getElementById("field-emergencia");
    const inputEmergencia = document.getElementById("input-emergencia");
    const inputObservacao = document.getElementById("input-observacao");

    const modalCancelar = document.getElementById("modal-cancelar");
    const formCancelar = document.getElementById("form-cancelar");
    const inputCancelarPedidoId = document.getElementById("cancelar-pedido-id");
    const inputMotivoCancelamento = document.getElementById("input-motivo-cancelamento");

    const estado = { skip: 0, limit: 15, total: 0 };
    let buscaTimeout = null;

    function canManagePedidos() {
        return typeof window.hasPermission === "function" &&
            (window.hasPermission("ENCARREGADO") || window.hasPermission("INSPETOR"));
    }

    function montarParams(incluirPaginacao) {
        const params = new URLSearchParams();
        const texto = searchInput.value.trim();
        if (texto) params.set("texto", texto);
        if (filterStatus.value) params.set("status", filterStatus.value);
        if (filterTipo.value) params.set("tipo_pedido", filterTipo.value);
        if (filterAeronave.value) params.set("aeronave_id", filterAeronave.value);
        if (filterExcluidos.checked) params.set("excluidos", "true");
        if (incluirPaginacao) {
            params.set("skip", String(estado.skip));
            params.set("limit", String(estado.limit));
        }
        return params;
    }

    function formatarData(iso) {
        if (!iso) return "—";
        const partes = iso.split("-");
        if (partes.length !== 3) return iso;
        const [ano, mes, dia] = partes;
        return `${dia}/${mes}/${ano}`;
    }

    function badgeStatus(status) {
        const mapa = {
            PENDENTE: ["badge-pendente", "dot-pendente", "Pendente"],
            ATENDIDO: ["badge-atendido", "dot-atendido", "Atendido"],
            CANCELADO: ["badge-cancelado", "dot-cancelado", "Cancelado"],
        };
        const [cls, dot, label] = mapa[status] || ["badge-cancelado", "dot-cancelado", status];
        return `<span class="badge ${cls}"><span class="badge-dot ${dot}"></span>${label}</span>`;
    }

    function badgeTipo(tipo) {
        if (tipo === "EMERGENCIA") return '<span class="badge badge-emergencia">Emergência</span>';
        return '<span class="badge badge-normal">Normal</span>';
    }

    function acoesHtml(pedido, modoExcluidos) {
        if (!canManagePedidos()) {
            return '<span class="cell-muted">—</span>';
        }
        if (modoExcluidos) {
            return `<button class="btn btn-outline-primary btn-sm" data-action="restaurar" data-id="${pedido.id}">Restaurar</button>`;
        }
        if (pedido.status !== "PENDENTE") {
            return '<span class="cell-muted" style="font-style: italic;">Sem ações</span>';
        }
        return `
            <button class="btn btn-outline-danger btn-sm" data-action="cancelar" data-id="${pedido.id}">Cancelar</button>
            <button class="btn btn-outline-primary btn-sm" data-action="alterar" data-id="${pedido.id}">Alterar</button>
            <button class="btn btn-success btn-sm" data-action="atender" data-id="${pedido.id}">Atender</button>
            <button class="btn btn-outline btn-sm" data-action="excluir" data-id="${pedido.id}">Excluir</button>
        `;
    }

    function renderPedido(pedido, modoExcluidos) {
        const linhaClasse = pedido.status === "ATENDIDO" ? "is-atendido"
            : (pedido.status === "CANCELADO" ? "is-cancelado" : "");

        const meta = [];
        if (pedido.solicitante_trigrama) meta.push(`Solicitado por ${escapeHtml(pedido.solicitante_trigrama)}`);
        if (pedido.status === "ATENDIDO" && pedido.atendido_por_trigrama) {
            meta.push(`Atendido por ${escapeHtml(pedido.atendido_por_trigrama)}`);
        }
        if (pedido.status === "CANCELADO") {
            if (pedido.cancelado_por_trigrama) meta.push(`Cancelado por ${escapeHtml(pedido.cancelado_por_trigrama)}`);
            if (pedido.motivo_cancelamento) meta.push(`Motivo: ${escapeHtml(pedido.motivo_cancelamento)}`);
        }

        const div = document.createElement("div");
        div.className = "pedido-expanded";
        div.innerHTML = `
            <div class="pedido-row ${linhaClasse}">
                <div>${badgeStatus(pedido.status)}</div>
                <div class="cell-muted">${formatarData(pedido.data_pedido)}</div>
                <div class="cell-matricula">${escapeHtml(pedido.aeronave_matricula)}</div>
                <div>${badgeTipo(pedido.tipo_pedido)}</div>
                <div class="cell-numero">${escapeHtml(pedido.numero_pedido)}</div>
                <div class="${pedido.numero_emergencia ? "cell-emergencia" : "cell-muted"}">${pedido.numero_emergencia ? escapeHtml(pedido.numero_emergencia) : "—"}</div>
                <div>${escapeHtml(pedido.nomenclatura)}</div>
                <div class="cell-muted">${escapeHtml(pedido.part_number)}</div>
                <div style="text-align: center; font-weight: 600;">${pedido.quantidade}</div>
                <div style="text-align: right;">${acoesHtml(pedido, modoExcluidos)}</div>
            </div>
            <div class="pedido-detail">
                <div class="pedido-obs">${pedido.observacao ? escapeHtml(pedido.observacao) : "Sem observações."}</div>
                <div class="pedido-meta">${meta.map((m) => `<span>${m}</span>`).join("")}</div>
            </div>
        `;
        return div;
    }

    function mudarPagina(pagina) {
        estado.skip = (pagina - 1) * estado.limit;
        carregarPedidos();
    }

    function renderPaginacao() {
        const totalPaginas = Math.max(1, Math.ceil(estado.total / estado.limit));
        const paginaAtual = Math.floor(estado.skip / estado.limit) + 1;

        const inicio = estado.total === 0 ? 0 : estado.skip + 1;
        const fim = Math.min(estado.skip + estado.limit, estado.total);
        paginationInfo.textContent = `Mostrando ${inicio}–${fim} de ${estado.total} registros`;

        paginationControls.innerHTML = "";

        const btnAnterior = document.createElement("button");
        btnAnterior.className = "page-btn";
        btnAnterior.textContent = "‹";
        btnAnterior.disabled = paginaAtual <= 1;
        btnAnterior.addEventListener("click", () => mudarPagina(paginaAtual - 1));
        paginationControls.appendChild(btnAnterior);

        const janela = 5;
        let inicioJanela = Math.max(1, paginaAtual - Math.floor(janela / 2));
        const fimJanela = Math.min(totalPaginas, inicioJanela + janela - 1);
        inicioJanela = Math.max(1, fimJanela - janela + 1);

        for (let p = inicioJanela; p <= fimJanela; p++) {
            const btn = document.createElement("button");
            btn.className = "page-btn" + (p === paginaAtual ? " active" : "");
            btn.textContent = String(p);
            btn.addEventListener("click", () => mudarPagina(p));
            paginationControls.appendChild(btn);
        }

        const btnProximo = document.createElement("button");
        btnProximo.className = "page-btn";
        btnProximo.textContent = "›";
        btnProximo.disabled = paginaAtual >= totalPaginas;
        btnProximo.addEventListener("click", () => mudarPagina(paginaAtual + 1));
        paginationControls.appendChild(btnProximo);
    }

    async function carregarResumo() {
        try {
            const params = montarParams(false);
            const resumo = await apiFetch(`/pedidos/resumo?${params.toString()}`);
            cardTotal.textContent = String(resumo.total);
            cardPendentes.textContent = String(resumo.pendentes);
            cardAtendidos.textContent = String(resumo.atendidos);
            cardEmergencias.textContent = String(resumo.emergencias);
            estado.total = resumo.total;
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    async function carregarPedidos() {
        body.innerHTML = '<div class="estado-vazio">Carregando pedidos...</div>';
        try {
            const params = montarParams(true);
            const modoExcluidos = filterExcluidos.checked;
            const lista = await apiFetch(`/pedidos/?${params.toString()}`);
            body.innerHTML = "";
            if (lista.length === 0) {
                body.innerHTML = '<div class="estado-vazio">Nenhum pedido encontrado.</div>';
            } else {
                lista.forEach((pedido) => body.appendChild(renderPedido(pedido, modoExcluidos)));
            }
            renderPaginacao();
        } catch (e) {
            body.innerHTML = '<div class="estado-vazio">Falha ao carregar pedidos.</div>';
        }
    }

    async function atualizarTudo() {
        estado.skip = 0;
        await Promise.all([carregarResumo(), carregarPedidos()]);
    }

    async function carregarAeronaves() {
        try {
            const frota = await apiFetch("/aeronaves/?limit=200");
            [filterAeronave, inputAeronave].forEach((select) => {
                const valorAtual = select.value;
                const primeiraOpcao = select.querySelector("option");
                select.innerHTML = "";
                if (primeiraOpcao) select.appendChild(primeiraOpcao);
                frota.forEach((aeronave) => {
                    const opt = document.createElement("option");
                    opt.value = aeronave.id;
                    opt.textContent = aeronave.matricula;
                    select.appendChild(opt);
                });
                select.value = valorAtual;
            });
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    // --- Modal Novo/Editar Pedido ---

    function alternarCampoEmergencia() {
        const isEmergencia = radioEmergencia.checked;
        fieldEmergencia.style.display = isEmergencia ? "block" : "none";
        inputEmergencia.required = isEmergencia;
        if (!isEmergencia) inputEmergencia.value = "";
    }

    function abrirModalNovo() {
        formPedido.reset();
        inputPedidoId.value = "";
        modalPedidoTitulo.textContent = "Novo Pedido";
        inputAeronave.disabled = false;
        alternarCampoEmergencia();
        modalPedido.style.display = "flex";
    }

    function abrirModalEditar(pedido) {
        formPedido.reset();
        inputPedidoId.value = pedido.id;
        modalPedidoTitulo.textContent = `Alterar Pedido ${pedido.numero_pedido}`;
        inputAeronave.value = pedido.aeronave_id;
        inputAeronave.disabled = true;
        inputPartNumber.value = pedido.part_number;
        inputNomenclatura.value = pedido.nomenclatura;
        inputQuantidade.value = String(pedido.quantidade);
        inputObservacao.value = pedido.observacao || "";
        radioEmergencia.checked = pedido.tipo_pedido === "EMERGENCIA";
        radioNormal.checked = pedido.tipo_pedido !== "EMERGENCIA";
        inputEmergencia.value = pedido.numero_emergencia || "";
        alternarCampoEmergencia();
        modalPedido.style.display = "flex";
    }

    function fecharModalPedido() {
        modalPedido.style.display = "none";
    }

    async function salvarPedido(e) {
        e.preventDefault();
        const tipoPedido = radioEmergencia.checked ? "EMERGENCIA" : "NORMAL";
        const payload = {
            part_number: inputPartNumber.value.trim(),
            nomenclatura: inputNomenclatura.value.trim(),
            quantidade: parseInt(inputQuantidade.value, 10) || 1,
            tipo_pedido: tipoPedido,
            numero_emergencia: tipoPedido === "EMERGENCIA" ? inputEmergencia.value.trim() : null,
            observacao: inputObservacao.value.trim() || null,
        };

        try {
            if (inputPedidoId.value) {
                await apiFetch(`/pedidos/${inputPedidoId.value}`, { method: "PUT", body: payload });
                showToast("Pedido atualizado.", "success");
            } else {
                await apiFetch("/pedidos/", {
                    method: "POST",
                    body: { ...payload, aeronave_id: inputAeronave.value },
                });
                showToast("Pedido criado.", "success");
            }
            fecharModalPedido();
            atualizarTudo();
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    // --- Modal Cancelar ---

    function abrirModalCancelar(id) {
        formCancelar.reset();
        inputCancelarPedidoId.value = id;
        modalCancelar.style.display = "flex";
    }

    function fecharModalCancelar() {
        modalCancelar.style.display = "none";
    }

    async function confirmarCancelamento(e) {
        e.preventDefault();
        const id = inputCancelarPedidoId.value;
        const motivo = inputMotivoCancelamento.value.trim();
        try {
            await apiFetch(`/pedidos/${id}/cancelar`, { method: "POST", body: { motivo } });
            showToast("Pedido cancelado.", "success");
            fecharModalCancelar();
            atualizarTudo();
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    // --- Ações rápidas ---

    async function atenderPedido(id) {
        if (!confirm("Confirma o atendimento deste pedido? A ação é apenas administrativa e não altera o inventário.")) return;
        try {
            await apiFetch(`/pedidos/${id}/atender`, { method: "POST" });
            showToast("Pedido marcado como atendido.", "success");
            atualizarTudo();
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    async function excluirPedido(id) {
        if (!confirm("O pedido será movido para a lixeira (soft delete). Deseja prosseguir?")) return;
        try {
            await apiFetch(`/pedidos/${id}`, { method: "DELETE" });
            showToast("Pedido excluído.", "success");
            atualizarTudo();
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    async function restaurarPedido(id) {
        if (!confirm("Deseja restaurar este pedido para o estado ativo?")) return;
        try {
            await apiFetch(`/pedidos/${id}/restaurar`, { method: "POST" });
            showToast("Pedido restaurado.", "success");
            atualizarTudo();
        } catch (e) {
            // apiFetch já notificou o erro.
        }
    }

    // --- Event listeners ---

    document.getElementById("btn-novo-pedido").addEventListener("click", abrirModalNovo);
    document.getElementById("btn-close-modal-pedido").addEventListener("click", fecharModalPedido);
    document.getElementById("btn-cancel-modal").addEventListener("click", fecharModalPedido);
    formPedido.addEventListener("submit", salvarPedido);

    document.getElementById("btn-close-modal-cancelar").addEventListener("click", fecharModalCancelar);
    document.getElementById("btn-cancel-modal-cancelar").addEventListener("click", fecharModalCancelar);
    formCancelar.addEventListener("submit", confirmarCancelamento);

    radioNormal.addEventListener("change", alternarCampoEmergencia);
    radioEmergencia.addEventListener("change", alternarCampoEmergencia);

    filterAeronave.addEventListener("change", atualizarTudo);
    filterStatus.addEventListener("change", atualizarTudo);
    filterTipo.addEventListener("change", atualizarTudo);
    filterExcluidos.addEventListener("change", atualizarTudo);
    searchInput.addEventListener("input", () => {
        clearTimeout(buscaTimeout);
        buscaTimeout = setTimeout(atualizarTudo, 350);
    });

    body.addEventListener("click", async (e) => {
        const botao = e.target.closest("[data-action]");
        if (!botao) return;
        const acao = botao.getAttribute("data-action");
        const id = botao.getAttribute("data-id");
        if (!id) return;

        if (acao === "atender") {
            atenderPedido(id);
        } else if (acao === "excluir") {
            excluirPedido(id);
        } else if (acao === "restaurar") {
            restaurarPedido(id);
        } else if (acao === "cancelar") {
            abrirModalCancelar(id);
        } else if (acao === "alterar") {
            try {
                const pedido = await apiFetch(`/pedidos/${id}`);
                abrirModalEditar(pedido);
            } catch (err) {
                // apiFetch já notificou o erro.
            }
        }
    });

    // --- Inicialização ---
    carregarAeronaves();
    atualizarTudo();
})();
