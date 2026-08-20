// app/web/static/js/mobile/inventario_mobile.js
// Módulo Inventário do SAA29 Mobile (Etapa 6): aba do hub — remover item
// instalado e instalar item de estoque no mesmo slot, com a limitação de
// RBAC (só S/N já cadastrado) explicada em texto, nunca escondida.

window.carregarAbaInventario = async function carregarAbaInventario(aeronaveId, container) {
    container.innerHTML = '<div class="mobile-loading">Buscando inventário da aeronave...</div>';

    try {
        const itens = await apiFetch(`/equipamentos/inventario/${aeronaveId}`);
        renderizarInventario(Array.isArray(itens) ? itens : [], aeronaveId, container);
    } catch (err) {
        console.error('Erro ao carregar inventário da aeronave:', err);
        container.innerHTML = '<div class="mobile-loading" style="color: var(--mobile-status-vencido);">Erro ao carregar inventário.</div>';
    }
};

function renderizarInventario(itens, aeronaveId, container) {
    container.innerHTML = '';

    if (itens.length === 0) {
        container.innerHTML = '<div class="mobile-loading">Nenhum slot de inventário configurado para esta aeronave.</div>';
        return;
    }

    const lista = document.createElement('div');
    lista.className = 'mobile-task-list';
    itens.forEach((item) => lista.appendChild(montarLinhaInventario(item, aeronaveId)));
    container.appendChild(lista);
}

function montarLinhaInventario(item, aeronaveId) {
    const card = document.createElement('div');
    card.className = 'mobile-task-card';
    const instalado = !!item.item_id;

    card.innerHTML = `
        <div class="mobile-task-card-top">
            <span class="badge-status ${instalado ? 'status-ok' : 'status-desinstalado'}">${instalado ? 'instalado' : 'slot vazio'}</span>
            <span class="mobile-task-card-meta">${instalado && item.numero_serie ? `S/N ${escapeHtml(item.numero_serie)}` : ''}</span>
        </div>
        <p class="mobile-task-card-title">${escapeHtml(item.nome_posicao)} · ${escapeHtml(item.part_number)}</p>
        <p class="mobile-task-card-meta">${escapeHtml(instalado
            ? `instalado ${item.data_instalacao ? formatarDataInv(item.data_instalacao) : ''}${item.usuario_trigrama ? ` por ${item.usuario_trigrama}` : ''}`
            : (item.nome_generico || 'sem item instalado'))}</p>
    `;

    if (instalado) {
        const btnRemover = document.createElement('button');
        btnRemover.type = 'button';
        btnRemover.className = 'mobile-row-action';
        btnRemover.style.color = 'var(--mobile-status-vencido)';
        btnRemover.style.background = 'rgba(242, 88, 94, 0.1)';
        btnRemover.style.borderColor = 'rgba(242, 88, 94, 0.32)';
        btnRemover.textContent = 'Remover';
        btnRemover.addEventListener('click', () => handleRemoverItem(item, aeronaveId));

        const wrap = document.createElement('div');
        wrap.className = 'mobile-row-action-wrap';
        wrap.appendChild(btnRemover);
        card.appendChild(wrap);
    } else {
        const btnInstalar = document.createElement('button');
        btnInstalar.type = 'button';
        btnInstalar.className = 'mobile-row-action';
        btnInstalar.textContent = 'Instalar';
        btnInstalar.addEventListener('click', () => abrirSheetInstalar(item, aeronaveId));

        const wrap = document.createElement('div');
        wrap.className = 'mobile-row-action-wrap';
        wrap.appendChild(btnInstalar);
        card.appendChild(wrap);
    }

    return card;
}

function formatarDataInv(iso) {
    if (!iso) return '';
    const [ano, mes, dia] = iso.split('-');
    return `${dia}/${mes}/${ano}`;
}

async function handleRemoverItem(item, aeronaveId) {
    if (!confirm(`Remover ${item.part_number} (S/N ${item.numero_serie || '—'}) de ${item.nome_posicao}?`)) return;

    try {
        await apiFetch(`/equipamentos/instalacoes/${item.instalacao_id}/remover`, {
            method: 'PATCH',
            body: { data_remocao: new Date().toISOString().slice(0, 10) },
        });
        showToast('Remoção registrada.', 'success');
        const container = document.getElementById('tab-inventario');
        if (container) carregarAbaInventario(aeronaveId, container);
    } catch (err) {
        console.error('Erro ao remover item:', err);
    }
}

async function abrirSheetInstalar(item, aeronaveId) {
    fecharSheetInstalar();

    const backdrop = document.createElement('div');
    backdrop.className = 'mobile-sheet-backdrop';
    backdrop.id = 'inv-sheet-backdrop';
    backdrop.addEventListener('click', fecharSheetInstalar);

    const sheet = document.createElement('div');
    sheet.className = 'mobile-sheet';
    sheet.id = 'inv-sheet';
    sheet.innerHTML = `
        <div class="mobile-sheet__handle"></div>
        <div>
            <p class="mobile-sheet__title">Instalar em ${escapeHtml(item.nome_posicao)}</p>
            <p class="mobile-sheet__meta">${escapeHtml(item.part_number)}${item.nome_generico ? ` · ${escapeHtml(item.nome_generico)}` : ''}</p>
        </div>
        <div id="inv-sheet-corpo"><p class="mobile-task-card-meta">Buscando itens de estoque...</p></div>
    `;

    document.body.appendChild(backdrop);
    document.body.appendChild(sheet);

    if (!item.equipamento_id) {
        document.getElementById('inv-sheet-corpo').innerHTML =
            '<div class="mobile-note">Este slot não está vinculado a um modelo de equipamento cadastrado. Solicite ao Administrador a configuração do slot antes de instalar.</div>' +
            '<button type="button" id="btn-inv-sem-equipamento-fechar" class="btn-mobile-action btn-mobile-ghost" style="margin-top:0.75rem;">Fechar</button>';
        document.getElementById('btn-inv-sem-equipamento-fechar').addEventListener('click', fecharSheetInstalar);
        return;
    }

    try {
        const todosItens = await apiFetch(`/equipamentos/itens/?equipamento_id=${item.equipamento_id}`);
        const disponiveis = (Array.isArray(todosItens) ? todosItens : []).filter((i) => i.status === 'ESTOQUE');
        renderizarCorpoSheetInstalar(disponiveis, item, aeronaveId);
    } catch (err) {
        console.error('Erro ao buscar itens de estoque:', err);
        const corpo = document.getElementById('inv-sheet-corpo');
        if (corpo) corpo.innerHTML = '<p class="mobile-task-card-meta">Erro ao buscar itens de estoque.</p>';
    }
}

function renderizarCorpoSheetInstalar(disponiveis, item, aeronaveId) {
    const corpo = document.getElementById('inv-sheet-corpo');
    if (!corpo) return;

    if (disponiveis.length === 0) {
        corpo.innerHTML = `
            <div class="mobile-note">Nenhum item de estoque cadastrado para este PN. Solicite ao Administrador o cadastro do número de série antes de instalar.</div>
            <button type="button" id="btn-inv-fechar" class="btn-mobile-action btn-mobile-ghost" style="margin-top:0.75rem;">Fechar</button>
        `;
        document.getElementById('btn-inv-fechar').addEventListener('click', fecharSheetInstalar);
        return;
    }

    corpo.innerHTML = `
        <div class="mobile-field">
            <label for="inv-select-sn">Número de série</label>
            <select id="inv-select-sn" class="mobile-select">
                ${disponiveis.map((i) => `<option value="${i.id}">${escapeHtml(i.numero_serie)}</option>`).join('')}
            </select>
        </div>
        <button type="button" id="btn-inv-confirmar" class="btn-mobile-action btn-mobile-accent">Instalar</button>
        <button type="button" id="btn-inv-cancelar" class="btn-mobile-action btn-mobile-ghost">Cancelar</button>
    `;

    document.getElementById('btn-inv-cancelar').addEventListener('click', fecharSheetInstalar);
    document.getElementById('btn-inv-confirmar').addEventListener('click', () => handleConfirmarInstalacao(item, aeronaveId));
}

function fecharSheetInstalar() {
    document.getElementById('inv-sheet-backdrop')?.remove();
    document.getElementById('inv-sheet')?.remove();
}

async function handleConfirmarInstalacao(item, aeronaveId) {
    const select = document.getElementById('inv-select-sn');
    const itemId = select ? select.value : null;
    if (!itemId) return;

    const btn = document.getElementById('btn-inv-confirmar');
    if (btn) { btn.disabled = true; btn.textContent = 'Instalando...'; }

    try {
        await apiFetch(`/equipamentos/itens/${itemId}/instalar`, {
            method: 'POST',
            body: {
                aeronave_id: aeronaveId,
                slot_id: item.slot_id,
                data_instalacao: new Date().toISOString().slice(0, 10),
            },
        });
        showToast('Item instalado.', 'success');
        fecharSheetInstalar();

        const container = document.getElementById('tab-inventario');
        if (container) carregarAbaInventario(aeronaveId, container);
    } catch (err) {
        console.error('Erro ao instalar item:', err);
        if (btn) { btn.disabled = false; btn.textContent = 'Instalar'; }
    }
}
