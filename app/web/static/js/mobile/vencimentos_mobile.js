// app/web/static/js/mobile/vencimentos_mobile.js
// Módulo Vencimentos do SAA29 Mobile (Etapa 5): aba do hub — 1 aeronave só,
// cada controle de cada slot vira uma linha, com registro de execução e
// histórico. Os inputs de data usam `min`/`max` nativos (última execução e
// hoje) para evitar de origem os 409/422 que o backend rejeitaria — assim o
// toast de erro genérico do apiFetch praticamente nunca aparece aqui.

window.carregarAbaVencimentos = async function carregarAbaVencimentos(aeronaveId, container) {
    container.innerHTML = '<div class="mobile-loading">Buscando vencimentos da aeronave...</div>';

    try {
        const matriz = await apiFetch(`/vencimentos/matriz?aeronave_id=${aeronaveId}`);
        const aeronave = (matriz && Array.isArray(matriz.aeronaves)) ? matriz.aeronaves[0] : null;
        renderizarVencimentos(aeronave, container);
    } catch (err) {
        console.error('Erro ao carregar vencimentos da aeronave:', err);
        container.innerHTML = '<div class="mobile-loading" style="color: var(--mobile-status-vencido);">Erro ao carregar vencimentos.</div>';
    }
};

const VENC_STATUS_CLASSE = {
    OK: 'status-ok',
    VENCENDO: 'status-vencendo',
    VENCIDO: 'status-vencido',
    PRORROGADO: 'status-prorrogado',
    DESINSTALADO: 'status-desinstalado',
};

function renderizarVencimentos(aeronave, container) {
    container.innerHTML = '';

    const linhas = [];
    (aeronave ? aeronave.slots || [] : []).forEach((slot) => {
        (slot.controles || []).forEach((controle) => linhas.push({ slot, controle }));
    });

    if (linhas.length === 0) {
        container.innerHTML = '<div class="mobile-loading">Nenhum controle de vencimento configurado para esta aeronave.</div>';
        return;
    }

    const lista = document.createElement('div');
    lista.className = 'mobile-task-list';
    linhas.forEach(({ slot, controle }) => lista.appendChild(montarLinhaVencimento(slot, controle, aeronave.aeronave_id)));
    container.appendChild(lista);
}

function formatarData(iso) {
    if (!iso) return null;
    const [ano, mes, dia] = iso.split('-');
    return `${dia}/${mes}/${ano}`;
}

function montarLinhaVencimento(slot, controle, aeronaveId) {
    const card = document.createElement('div');
    card.className = 'mobile-task-card';

    const statusClasse = VENC_STATUS_CLASSE[controle.status] || 'status-desinstalado';
    const metaPartes = [];
    if (controle.data_vencimento) metaPartes.push(`vence ${formatarData(controle.data_vencimento)}`);
    if (controle.prorrogado && controle.numero_documento_prorrogacao) metaPartes.push(controle.numero_documento_prorrogacao);
    if (!controle.data_vencimento && !controle.prorrogado) metaPartes.push('sem execução registrada');

    card.innerHTML = `
        <div class="mobile-task-card-top">
            <span class="badge-status ${statusClasse}">${escapeHtml(controle.status || '—')}</span>
            <span class="mobile-task-card-meta">${slot.numero_serie ? `S/N ${escapeHtml(slot.numero_serie)}` : ''}</span>
        </div>
        <p class="mobile-task-card-title">${escapeHtml(slot.nome_posicao || slot.sistema)} · ${escapeHtml(controle.tipo_controle_nome)}</p>
        <p class="mobile-task-card-meta">${escapeHtml(metaPartes.join(' · '))}</p>
    `;

    if (controle.vencimento_id) {
        const acoes = document.createElement('div');
        acoes.className = 'mobile-row-action-wrap';
        acoes.style.gap = '0.5rem';

        const btnHistorico = document.createElement('button');
        btnHistorico.type = 'button';
        btnHistorico.className = 'mobile-row-action';
        btnHistorico.style.color = 'var(--mobile-text-muted)';
        btnHistorico.style.background = 'rgba(255,255,255,0.06)';
        btnHistorico.style.border = '1px solid var(--mobile-card-border)';
        btnHistorico.textContent = 'Histórico';
        btnHistorico.addEventListener('click', () => alternarHistorico(card, controle.vencimento_id));

        const btnRegistrar = document.createElement('button');
        btnRegistrar.type = 'button';
        btnRegistrar.className = 'mobile-row-action';
        btnRegistrar.textContent = 'Registrar';
        btnRegistrar.addEventListener('click', () => abrirSheetExecucao(controle, slot, aeronaveId));

        acoes.appendChild(btnHistorico);
        acoes.appendChild(btnRegistrar);
        card.appendChild(acoes);
    }

    return card;
}

async function alternarHistorico(card, vencimentoId) {
    const existente = card.querySelector('.mobile-venc-historico');
    if (existente) {
        existente.remove();
        return;
    }

    const painel = document.createElement('div');
    painel.className = 'mobile-venc-historico';
    painel.style.cssText = 'margin-top:0.6rem; padding-top:0.6rem; border-top:1px solid var(--mobile-card-border); display:flex; flex-direction:column; gap:0.4rem;';
    painel.innerHTML = '<p class="mobile-task-card-meta">Carregando histórico...</p>';
    card.appendChild(painel);

    try {
        const historico = await apiFetch(`/vencimentos/${vencimentoId}/historico`);
        if (!Array.isArray(historico) || historico.length === 0) {
            painel.innerHTML = '<p class="mobile-task-card-meta">Nenhuma execução registrada ainda.</p>';
            return;
        }
        painel.innerHTML = historico.map((h) => `
            <p class="mobile-task-card-meta">
                <strong style="color:var(--mobile-text);">${formatarData(h.data_execucao)}</strong>
                · próximo vencimento ${formatarData(h.data_vencimento_calculada)}${h.observacao ? ` · ${escapeHtml(h.observacao)}` : ''}
            </p>
        `).join('');
    } catch (err) {
        console.error('Erro ao carregar histórico de vencimento:', err);
        painel.innerHTML = '<p class="mobile-task-card-meta">Erro ao carregar histórico.</p>';
    }
}

function abrirSheetExecucao(controle, slot, aeronaveId) {
    fecharSheetExecucao();

    const hojeIso = hojeLocalIso();
    const backdrop = document.createElement('div');
    backdrop.className = 'mobile-sheet-backdrop';
    backdrop.id = 'venc-sheet-backdrop';
    backdrop.addEventListener('click', fecharSheetExecucao);

    const sheet = document.createElement('div');
    sheet.className = 'mobile-sheet';
    sheet.id = 'venc-sheet';
    sheet.innerHTML = `
        <div class="mobile-sheet__handle"></div>
        <div>
            <p class="mobile-sheet__title">${escapeHtml(controle.tipo_controle_nome)}</p>
            <p class="mobile-sheet__meta">${escapeHtml(slot.nome_posicao || slot.sistema)}${slot.numero_serie ? ` · S/N ${escapeHtml(slot.numero_serie)}` : ''}</p>
        </div>
        <div class="mobile-field" style="margin-bottom:0;">
            <label for="venc-data-exec">Data de execução</label>
            <input type="date" id="venc-data-exec" class="mobile-input" value="${hojeIso}" max="${hojeIso}" ${controle.data_ultima_exec ? `min="${controle.data_ultima_exec}"` : ''}>
        </div>
        <div class="mobile-field" style="margin-bottom:0;">
            <label for="venc-observacao">Observação (opcional)</label>
            <textarea id="venc-observacao" class="mobile-textarea" rows="2"></textarea>
        </div>
        <button type="button" id="btn-venc-confirmar" class="btn-mobile-action btn-mobile-accent">Confirmar execução</button>
        <button type="button" id="btn-venc-cancelar" class="btn-mobile-action btn-mobile-ghost">Cancelar</button>
    `;

    document.body.appendChild(backdrop);
    document.body.appendChild(sheet);

    document.getElementById('btn-venc-cancelar').addEventListener('click', fecharSheetExecucao);
    document.getElementById('btn-venc-confirmar').addEventListener('click', () => handleConfirmarExecucao(controle.vencimento_id, aeronaveId));
}

function fecharSheetExecucao() {
    document.getElementById('venc-sheet-backdrop')?.remove();
    document.getElementById('venc-sheet')?.remove();
}

async function handleConfirmarExecucao(vencimentoId, aeronaveId) {
    const btn = document.getElementById('btn-venc-confirmar');
    const data = document.getElementById('venc-data-exec').value;
    const observacao = document.getElementById('venc-observacao').value.trim();

    if (!data) return;
    if (btn) { btn.disabled = true; btn.textContent = 'Registrando...'; }

    try {
        await apiFetch(`/vencimentos/${vencimentoId}/executar`, {
            method: 'PATCH',
            body: { data_ultima_exec: data, observacao: observacao || null },
        });
        showToast('Execução registrada.', 'success');
        fecharSheetExecucao();

        const container = document.getElementById('tab-vencimentos');
        if (container) carregarAbaVencimentos(aeronaveId, container);
    } catch (err) {
        console.error('Erro ao registrar execução de vencimento:', err);
        if (btn) { btn.disabled = false; btn.textContent = 'Confirmar execução'; }
    }
}
