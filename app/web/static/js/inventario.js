/**
 * static/js/inventario.js
 * Gestão de Inventário de Equipamentos por Aeronave
 */

let aeronavesCache = [];

async function loadAeronaves() {
    const select = document.getElementById('aeronave-select');
    if (!select) return;
    try {
        const data = await apiFetch('/aeronaves/?limit=100&incluir_inativas=true');
        data.sort((a, b) => a.matricula.localeCompare(b.matricula));
        
        select.innerHTML = '<option value="">Selecione uma aeronave...</option>';
        data.forEach(acft => {
            const opt = document.createElement('option');
            opt.value = acft.id;
            opt.textContent = acft.matricula;
            select.appendChild(opt);
        });

        const urlParams = new URLSearchParams(window.location.search);
        const acftId = urlParams.get('aeronave_id');
        if (acftId) {
            select.value = acftId;
            loadInventario();
        } else {
            loadHistoricoRecente();
        }
    } catch (e) { console.error(e); }
}

async function loadInventario() {
    const select = document.getElementById('aeronave-select');
    const filterNome = document.getElementById('filter-nome');
    if(!select || !filterNome) return;
    
    const aeronaveId = select.value;
    const nomeFilter = filterNome.value;
    const container = document.getElementById('inventario-container');

    if (!aeronaveId) {
        loadHistoricoRecente();
        return;
    }

    try {
        let url = `/equipamentos/inventario/${aeronaveId}`;
        if (nomeFilter) url += `?nome=${encodeURIComponent(nomeFilter)}`;

        const data = await apiFetch(url);
        renderInventario(data);
    } catch (e) {
        container.innerHTML = `<div class="card glass-panel" style="padding: 2rem; text-align: center; color: var(--status-danger);">Erro ao carregar inventário.</div>`;
    }
}

async function loadHistoricoRecente() {
    const container = document.getElementById('inventario-container');
    const statsDiv = document.getElementById('stats-summary');
    if(statsDiv) statsDiv.innerHTML = '';
    
    try {
        const data = await apiFetch('/equipamentos/inventario/historico');
        renderHistorico(data);
    } catch (e) {
        if(container) container.innerHTML = `<div class="card glass-panel" style="padding: 2rem; text-align: center; color: var(--text-secondary);">Selecione uma aeronave para começar.</div>`;
    }
}

function renderHistorico(logs) {
    const container = document.getElementById('inventario-container');
    if(!container) return;
    
    let html = `
        <div style="margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.75rem; color: var(--primary-color);">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <h3 style="margin: 0; font-size: 1.1rem; text-transform: uppercase; letter-spacing: 0.5px;">Últimas Alterações no Inventário</h3>
        </div>
        <div class="card glass-panel" style="padding: 0; overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse; text-align: center;">
                <thead style="background-color: var(--bg-tertiary); border-bottom: 1px solid var(--border-color);">
                    <tr>
                        <th style="padding: 1rem; width: 15%;">Data/Hora</th>
                        <th style="padding: 1rem; width: 10%;">Aeronave</th>
                        <th style="padding: 1rem; width: 15%;">Posição</th>
                        <th style="padding: 1rem; width: 25%;">S/N Instalado</th>
                        <th style="padding: 1rem; width: 10%;">Trigrama</th>
                        <th style="padding: 1rem; width: 15%;">Ação</th>
                    </tr>
                </thead>
                <tbody>
    `;

    if (!logs || logs.length === 0) {
        html += `<tr><td colspan="6" style="padding: 2rem; text-align: center; color: var(--text-secondary);">Nenhuma movimentação registrada recentemente.</td></tr>`;
    } else {
        logs.forEach(log => {
            const dataFormatada = new Date(log.created_at).toLocaleString('pt-BR');
            html += `
                <tr style="border-bottom: 1px solid var(--border-color);">
                    <td style="padding: 0.8rem 1rem; font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(dataFormatada)}</td>
                    <td style="padding: 0.8rem 1rem; font-weight: 700; color: var(--primary-color);">${escapeHtml(log.aeronave_matricula)}</td>
                    <td style="padding: 0.8rem 1rem;">${escapeHtml(log.slot_nome)}</td>
                    <td style="padding: 0.8rem 1rem; font-family: monospace; font-weight: 500;">${escapeHtml(log.item_sn)}</td>
                    <td style="padding: 0.8rem 1rem; text-align: center;">
                        <span class="badge" style="background: var(--bg-tertiary); color: var(--text-primary); font-weight: 700;">${escapeHtml(log.usuario_trigrama || 'SYS')}</span>
                    </td>
                    <td style="padding: 0.8rem 1rem;">
                        <span style="font-size: 0.75rem; font-weight: 700; color: var(--status-success);">● ${escapeHtml(log.tipo_acao)}</span>
                    </td>
                </tr>
            `;
        });
    }

    html += `</tbody></table></div>`;
    container.innerHTML = html;
}

function compareSN(input, snOriginal, equipamentoId) {
    const val = input.value.trim().toUpperCase();
    const btn = document.getElementById(`btn-sync-${equipamentoId}`);
    input.classList.remove('status-match', 'status-mismatch', 'status-pending');
    const original = (snOriginal || "").toUpperCase();

    if (val === '') {
        input.classList.add('status-pending');
        if(btn) btn.classList.remove('visible');
    } else if (val === original) {
        input.classList.add('status-match');
        if(btn) btn.classList.remove('visible');
    } else {
        input.classList.add('status-mismatch');
        if(btn) btn.classList.add('visible');
    }
    updateStats();
}

async function ajustarInventario(equipamentoId, snReal, forcar = false) {
    const select = document.getElementById('aeronave-select');
    if(!select || !snReal) return;
    const aeronaveId = select.value;
    const user = JSON.parse(localStorage.getItem("saa29_user"));
    
    try {
        const response = await apiFetch(`/equipamentos/inventario/ajuste`, {
            method: 'POST',
            body: {
                aeronave_id: aeronaveId,
                equipamento_id: equipamentoId,
                numero_serie_real: snReal,
                forcar_transferencia: forcar,
                usuario_id: user ? user.id : null
            }
        });

        if (response.sucesso) {
            showToast(response.mensagem, "success");
            fecharModal();
            loadInventario();
        } else if (response.requer_confirmacao) {
            abrirModal(equipamentoId, snReal, response.aeronave_conflito);
        } else {
            showToast(response.mensagem, "error");
        }
    } catch (e) {
        showToast(e.message || "Erro ao ajustar inventário.", "error");
    }
}

async function removerEquipamento(instalacaoId) {
    if (!instalacaoId) return;
    try {
        await apiFetch(`/equipamentos/instalacoes/${instalacaoId}/remover`, {
            method: 'PATCH',
            body: { data_remocao: new Date().toISOString().split('T')[0] }
        });
        showToast("Item desinstalado com sucesso.", "info");
        fecharModalRemocao();
        loadInventario();
    } catch (e) {
        showToast("Erro ao remover equipamento.", "error");
    }
}

function renderInventario(items) {
    const container = document.getElementById('inventario-container');
    if(!container) return;

    container.innerHTML = '';
    
    const section = document.createElement('div');
    section.innerHTML = `
        <div class="card glass-panel" style="padding: 0; overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse; text-align: center;">
                <thead style="background-color: var(--bg-tertiary); border-bottom: 1px solid var(--border-color);">
                    <tr>
                        <th style="padding: 1rem; width: 6%;">Loc.</th>
                        <th style="padding: 1rem; width: 18%;">Item</th>
                        <th style="padding: 1rem; width: 12%;">P/N</th>
                        <th style="padding: 1rem; width: 14%;">S/N (SILOMS)</th>
                        <th style="padding: 1rem; width: 16%;">Atualização/Trigrama</th>
                        <th style="padding: 1rem; width: 22%;">S/N (REAL)</th>
                        <th style="padding: 1rem; width: 12%;">Anv Ant.</th>
                    </tr>
                </thead>
                <tbody id="inventory-tbody"></tbody>
            </table>
        </div>
    `;

    const tbody = section.querySelector('#inventory-tbody');
    
    // Sort: Primeiro por Sistema, depois por Nome
    items.sort((a,b) => {
        const sisA = a.sistema || 'ZZZ';
        const sisB = b.sistema || 'ZZZ';
        if(sisA !== sisB) return sisA.localeCompare(sisB);
        return a.equipamento_nome.localeCompare(b.equipamento_nome);
    });

    items.forEach(item => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = "1px solid var(--border-color)";
        const inputId = `real-${item.equipamento_id}`;
        
        const snSilomsHtml = item.numero_serie ? 
            `<span class="badge badge-sn-siloms" style="background-color: var(--status-ok); color: #fff; border: 1px solid var(--border-color); cursor: pointer; padding: 0.4rem 0.8rem; font-family: monospace;" title="Clique para desinstalar">${item.numero_serie}</span>` :
            `<span class="badge" style="background-color: var(--status-danger); color: #fff; border: 1px solid var(--border-color); font-weight: 700; font-size: 0.7rem; padding: 0.4rem 0.6rem;">DESINSTALADO</span>`;

        let rastreabilidade = '<span style="color: var(--text-secondary); opacity: 0.5;">-</span>';
        if (item.data_atualizacao) {
            const dataObj = new Date(item.data_atualizacao);
            if (!isNaN(dataObj)) {
                const dia = String(dataObj.getDate()).padStart(2, '0');
                const mes = String(dataObj.getMonth() + 1).padStart(2, '0');
                const ano = String(dataObj.getFullYear()).slice(-2);
                const hora = String(dataObj.getHours()).padStart(2, '0');
                const min = String(dataObj.getMinutes()).padStart(2, '0');
                rastreabilidade = `<div style="font-size: 0.8rem; line-height: 1.2;">
                    <div style="color: var(--text-secondary);">${dia}/${mes}/${ano} ${hora}:${min}</div>
                    <div style="font-weight: 700; color: var(--primary-color); margin-top: 2px;">${item.usuario_trigrama || 'SYS'}</div>
                </div>`;
            }
        }

        tr.innerHTML = `
            <td style="padding: 0.8rem 1rem;"><span class="badge" style="background: rgba(var(--primary-rgb), 0.1); color: var(--primary-color); font-weight: 600; font-size: 0.75rem;">${item.sistema || '-'}</span></td>
            <td style="padding: 0.8rem 1rem;"><div style="font-weight: 600;">${escapeHtml(item.equipamento_nome)}</div><div style="font-size: 0.75rem; color: var(--text-secondary);">${escapeHtml(item.status_item) || 'NÃO INSTALADO'}</div></td>
            <td style="padding: 0.8rem 1rem; font-family: monospace; font-size: 0.9rem;">${escapeHtml(item.part_number)}</td>
            <td style="padding: 0.8rem 1rem;" class="td-sn-siloms">${snSilomsHtml}</td>
            <td style="padding: 0.8rem 1rem;">${rastreabilidade}</td>
            <td style="padding: 0.6rem 1rem;">
                <div class="real-input-container">
                    <input type="text" id="${inputId}" class="real-input status-pending" placeholder="S/N real...">
                    <button id="btn-sync-${item.equipamento_id}" class="btn-sync" title="Sincronizar">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                    </button>
                </div>
            </td>
            <td style="padding: 0.8rem 1rem;">${item.aeronave_anterior ? `<span class="badge" style="background: var(--bg-tertiary); color: var(--primary-color);">${escapeHtml(item.aeronave_anterior)}</span>` : '-'}</td>
        `;
        
        const badgeSn = tr.querySelector('.badge-sn-siloms');
        if(badgeSn) {
            badgeSn.addEventListener('click', () => abrirModalRemocao(item.instalacao_id, item.numero_serie, item.nome_posicao));
        }
        
        const input = tr.querySelector('.real-input');
        input.addEventListener('input', () => compareSN(input, item.numero_serie || '', item.equipamento_id));
        
        const btnSync = tr.querySelector('.btn-sync');
        btnSync.addEventListener('click', () => ajustarInventario(item.equipamento_id, input.value));
        
        tbody.appendChild(tr);
    });

    container.appendChild(section);
    updateStats(items);
}

function updateStats(items) {
    const statsDiv = document.getElementById('stats-summary');
    if (!statsDiv) return;

    if (!items) {
        statsDiv.innerHTML = '';
        return;
    }

    const total = items.length;
    const ok = items.filter(i => {
        const input = document.getElementById(`real-${i.equipamento_id}`);
        return input && input.classList.contains('status-match');
    }).length;

    const pendente = items.filter(i => {
        const input = document.getElementById(`real-${i.equipamento_id}`);
        return !input || input.classList.contains('status-pending');
    }).length;

    const erro = total - ok - pendente;

    statsDiv.innerHTML = `
        <span style="color: var(--text-secondary);">Total: <strong>${total}</strong></span>
        <span style="color: var(--status-success);">Conferidos: <strong>${ok}</strong></span>
        <span style="color: var(--status-danger);">Divergentes: <strong>${erro}</strong></span>
    `;
}

function abrirModal(equipamentoId, snReal, anvConflito) {
    const msg = document.getElementById('modal-transferencia-msg');
    const modal = document.getElementById('modal-transferencia');
    const btn = document.getElementById('btn-confirmar-transferencia');
    if(!msg || !modal || !btn) return;

    msg.innerHTML = `O item <strong>${escapeHtml(snReal)}</strong> consta como instalado na aeronave <strong>${escapeHtml(anvConflito)}</strong>.`;
    modal.style.display = 'flex';

    const oldBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(oldBtn, btn);
    oldBtn.addEventListener('click', () => {
        ajustarInventario(equipamentoId, snReal, true);
    });
}

function fecharModal() {
    const modal = document.getElementById('modal-transferencia');
    if(modal) modal.style.display = 'none';
}

function abrirModalRemocao(instalacaoId, sn, slotNome) {
    const msg = document.getElementById('modal-remocao-msg');
    const modal = document.getElementById('modal-remocao');
    const btn = document.getElementById('btn-confirmar-remocao');
    if(!msg || !modal || !btn) return;

    msg.innerHTML = `Deseja registrar a remoção do item <strong>${escapeHtml(sn)}</strong> da posição <strong>${escapeHtml(slotNome)}</strong>?`;
    modal.style.display = 'flex';

    const oldBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(oldBtn, btn);
    oldBtn.addEventListener('click', () => {
        removerEquipamento(instalacaoId);
    });
}

function fecharModalRemocao() {
    const modal = document.getElementById('modal-remocao');
    if(modal) modal.style.display = 'none';
}

window.fecharModal = fecharModal;
window.fecharModalRemocao = fecharModalRemocao;
window.loadInventario = loadInventario;

document.addEventListener('DOMContentLoaded', () => {
    loadAeronaves();
    
    const select = document.getElementById('aeronave-select');
    const filterNome = document.getElementById('filter-nome');
    
    if (select) {
        select.addEventListener('change', () => {
            const url = new URL(window.location);
            if (select.value) {
                url.searchParams.set('aeronave_id', select.value);
            } else {
                url.searchParams.delete('aeronave_id');
            }
            window.history.pushState({}, '', url);
            loadInventario();
        });
    }
    
    if (filterNome) {
        filterNome.addEventListener('input', loadInventario);
    }

    // Handlers para fechar modais (CSP compliant)
    document.getElementById('btn-cancelar-transferencia')?.addEventListener('click', fecharModal);
    document.getElementById('btn-cancelar-remocao')?.addEventListener('click', fecharModalRemocao);
});
