// @ts-check

/**
 * Scripts para Listagem de Inspeções
 */

/**
 * @typedef {Object} InspecaoListDTO
 * @property {string} id
 * @property {string} status
 * @property {number} [progresso_percentual]
 * @property {number} [total_tarefas]
 * @property {number} [tarefas_concluidas]
 * @property {string} data_abertura
 * @property {string} [data_fim_prevista]
 * @property {string} [aberto_por_trigrama]
 * @property {{ matricula: string }} [aeronave]
 * @property {{ codigo: string }[]} tipos_aplicados
 */

document.addEventListener("DOMContentLoaded", () => {
    carregarFiltros();
    carregarInspecoes();

    document.getElementById('filtroAeronave')?.addEventListener('change', carregarInspecoes);
    document.getElementById('filtroStatus')?.addEventListener('change', carregarInspecoes);

    document.getElementById('btn-nova-inspecao')?.addEventListener('click', openModalNovaInspecao);
    document.getElementById('btn-close-modal-nova')?.addEventListener('click', closeModalNovaInspecao);
    document.getElementById('btn-cancel-modal-nova')?.addEventListener('click', closeModalNovaInspecao);
    document.getElementById('formNovaInspecao')?.addEventListener('submit', salvarNovaInspecao);

    // Recalcular DPE ao mudar tipos ou data de início
    document.getElementById('novaInspecaoTipos')?.addEventListener('change', recalcularDPE);
    document.getElementById('novaInspecaoDataInicio')?.addEventListener('change', recalcularDPE);
});

/**
 * @returns {Promise<void>}
 */
async function carregarFiltros() {
    /** @type {HTMLSelectElement | null} */
    const selectAeronave = document.querySelector('#filtroAeronave');
    /** @type {HTMLSelectElement | null} */
    const selectNovaAeronave = document.querySelector('#novaInspecaoAeronave');
    
    if (!selectAeronave || !selectNovaAeronave) return;

    try {
        const [aeronaves, tipos] = await Promise.all([
            // @ts-ignore
            apiFetch('/aeronaves/'),
            // @ts-ignore
            apiFetch('/inspecoes/tipos')
        ]);
        
        // @ts-ignore
        aeronaves.sort((a,b) => a.matricula.localeCompare(b.matricula)).forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.id;
            opt.text = a.matricula;
            selectAeronave.appendChild(opt.cloneNode(true));
            
            if(a.status !== 'INATIVA' && a.status !== 'ESTOCADA') {
                selectNovaAeronave.appendChild(opt);
            }
        });

        /** @type {HTMLSelectElement | null} */
        const selectTipos = document.querySelector('#novaInspecaoTipos');
        if (selectTipos) {
            selectTipos.innerHTML = '';
            // @ts-ignore
            tipos.filter(t => t.ativo).forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.text = `${t.codigo} - ${t.nome}${t.duracao_dias > 0 ? ` (${t.duracao_dias}d)` : ''}`;
                opt.dataset.duracao = String(t.duracao_dias || 0);
                selectTipos.appendChild(opt);
            });
        }
        
    } catch(e) {
        // @ts-ignore
        showToast("Erro ao carregar filtros.", "error");
    }
}

/**
 * @returns {Promise<void>}
 */
async function carregarInspecoes() {
    const container = document.getElementById('lista-inspecoes');
    if (!container) return;
    
    container.innerHTML = '<p style="color: var(--text-secondary); text-align: center; grid-column: 1 / -1;">Carregando inspeções...</p>';
    
    /** @type {HTMLSelectElement | null} */
    const filtroAeronaveEl = document.querySelector('#filtroAeronave');
    const aeronaveId = filtroAeronaveEl ? filtroAeronaveEl.value : "";
    
    /** @type {HTMLSelectElement | null} */
    const filtroStatusEl = document.querySelector('#filtroStatus');
    const status = filtroStatusEl ? filtroStatusEl.value : "";
    
    let url = '/inspecoes/?limit=50';
    if(aeronaveId) url += `&aeronave_id=${aeronaveId}`;
    if(status) url += `&status=${status}`;

    try {
        /** @type {InspecaoListDTO[]} */
        // @ts-ignore
        const inspecoes = await apiFetch(url);
        container.innerHTML = '';
        
        if(inspecoes.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); text-align: center; grid-column: 1 / -1; padding: 2rem;">Nenhuma inspeção encontrada com os filtros atuais.</p>';
            return;
        }

        inspecoes.forEach(i => {
            const pct = i.progresso_percentual || 0;
            const statusColor = getStatusColor(i.status);
            
            const card = document.createElement('a');
            card.href = `/inspecoes/${i.id}/detalhes`;
            card.className = 'card hover-float';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            card.style.gap = '1rem';
            card.style.cursor = 'pointer';
            card.style.textDecoration = 'none';
            card.style.color = 'inherit';
            
            const pacotes = (i.tipos_aplicados || []).map(t => t.codigo).join(' + ');

            // @ts-ignore
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; font-size: 1.25rem;">A-29 ${i.aeronave?.matricula || '---'}</h3>
                    <span style="font-size: 0.8rem; font-weight: 600; padding: 0.25rem 0.5rem; border-radius: 12px; background: ${statusColor}20; color: ${statusColor};">
                        ${i.status.replace('_', ' ')}
                    </span>
                </div>
                
                <div>
                    <div style="font-weight: 500; color: var(--text-color); margin-bottom: 0.25rem;">Pacote(s): ${pacotes}</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary); display: flex; gap: 1rem; flex-wrap: wrap; align-items: center;">
                        <span>Abertura: ${new Date(i.data_abertura).toLocaleDateString()}</span>
                        ${i.data_fim_prevista ? `<span style="color: ${_dpeCardColor(i)};">DPE: ${new Date(i.data_fim_prevista).toLocaleDateString('pt-BR')}</span>` : ''}
                        ${i.aberto_por_trigrama ? `<span style="font-family: monospace; font-size: 0.8rem; font-weight: 700; background: var(--bg-tertiary, rgba(0,0,0,0.08)); padding: 0.1rem 0.4rem; border-radius: 4px;" title="Aberto por">${escapeHtml(i.aberto_por_trigrama)}</span>` : ''}
                    </div>
                </div>

                <div style="margin-top: auto;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem; font-weight: 500;">
                        <span>Progresso</span>
                        <span>${i.tarefas_concluidas || 0}/${i.total_tarefas || 0} (${pct}%)</span>
                    </div>
                    <div style="width: 100%; height: 6px; background: var(--border-color); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${pct}%; height: 100%; background: ${pct === 100 ? 'var(--status-ok)' : 'var(--primary-color)'}; transition: width 0.3s ease;"></div>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
        
    } catch(err) {
        container.innerHTML = '<p style="color: var(--status-danger); text-align: center; grid-column: 1 / -1;">Erro ao carregar inspeções.</p>';
    }
}

/**
 * @param {string} status
 * @returns {string}
 */
function getStatusColor(status) {
    /** @type {Record<string, string>} */
    const map = {
        'ABERTA': '#f39c12',
        'EM_ANDAMENTO': '#3498db',
        'CONCLUIDA': '#2ecc71',
        'CANCELADA': '#e74c3c'
    };
    return map[status] || 'var(--text-secondary)';
}

/**
 * @param {InspecaoListDTO} inspecao
 * @returns {string}
 */
function _dpeCardColor(inspecao) {
    if (!inspecao.data_fim_prevista || inspecao.status === 'CONCLUIDA' || inspecao.status === 'CANCELADA') {
        return 'var(--text-secondary)';
    }
    const diff = Math.ceil((new Date(inspecao.data_fim_prevista).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
    if (diff < 0)  return 'var(--status-danger, #e74c3c)';
    if (diff <= 7) return '#f39c12';
    return 'var(--text-secondary)';
}

/**
 * @returns {void}
 */
function openModalNovaInspecao() {
    const modal = document.getElementById('modal-nova-inspecao');
    if (modal) modal.style.display = 'flex';
    
    /** @type {HTMLSelectElement | null} */
    const anvSelect = document.querySelector('#novaInspecaoAeronave');
    if (anvSelect) anvSelect.value = '';
    
    /** @type {HTMLSelectElement | null} */
    const tiposSelect = document.querySelector('#novaInspecaoTipos');
    if (tiposSelect) tiposSelect.selectedIndex = -1;
    
    /** @type {HTMLInputElement | null} */
    const obsInput = document.querySelector('#novaInspecaoObs');
    if (obsInput) obsInput.value = '';

    // Preencher data de início com hoje
    const hoje = new Date().toISOString().split('T')[0];
    
    /** @type {HTMLInputElement | null} */
    const startInput = document.querySelector('#novaInspecaoDataInicio');
    if (startInput) startInput.value = hoje;
    
    /** @type {HTMLInputElement | null} */
    const dpeInput = document.querySelector('#novaInspecaoDPE');
    if (dpeInput) {
        dpeInput.value = '';
        dpeInput.style.color = 'var(--text-color)';
    }
}

/**
 * @returns {void}
 */
function closeModalNovaInspecao() {
    const modal = document.getElementById('modal-nova-inspecao');
    if (modal) modal.style.display = 'none';
}

/**
 * @returns {void}
 */
function recalcularDPE() {
    /** @type {HTMLSelectElement | null} */
    const selectTipos = document.querySelector('#novaInspecaoTipos');
    /** @type {HTMLInputElement | null} */
    const dataInicioInput = document.querySelector('#novaInspecaoDataInicio');
    /** @type {HTMLInputElement | null} */
    const dpeInput = document.querySelector('#novaInspecaoDPE');

    if (!selectTipos || !dataInicioInput || !dpeInput) return;

    const selectedOptions = Array.from(selectTipos.selectedOptions);
    if (selectedOptions.length === 0 || !dataInicioInput.value) {
        dpeInput.value = '';
        return;
    }

    const maxDuracao = Math.max(...selectedOptions.map(o => parseInt(o.dataset.duracao || '0', 10) || 0));
    if (maxDuracao === 0) {
        dpeInput.value = 'Sem duração cadastrada';
        dpeInput.style.color = 'var(--status-danger)';
        return;
    }

    const dataInicio = new Date(dataInicioInput.value + 'T00:00:00');
    const dpe = new Date(dataInicio);
    dpe.setDate(dpe.getDate() + maxDuracao);
    
    // Formato yyyy-mm-dd para input type="date"
    dpeInput.value = dpe.toISOString().split('T')[0];
    dpeInput.style.color = 'var(--text-color)';
}

/**
 * @param {Event} e
 * @returns {Promise<void>}
 */
async function salvarNovaInspecao(e) {
    e.preventDefault();
    /** @type {HTMLButtonElement | null} */
    const btn = document.querySelector('#btnSalvarInspecao');
    if (btn) btn.disabled = true;

    /** @type {HTMLSelectElement | null} */
    const anvSelect = document.querySelector('#novaInspecaoAeronave');
    const aeronave_id = anvSelect ? anvSelect.value : "";
    
    /** @type {HTMLSelectElement | null} */
    const tiposSelect = document.querySelector('#novaInspecaoTipos');
    const tipos_inspecao_ids = tiposSelect ? Array.from(tiposSelect.selectedOptions).map(o => o.value) : [];
    
    /** @type {HTMLInputElement | null} */
    const obsInput = document.querySelector('#novaInspecaoObs');
    const observacoes = obsInput ? (obsInput.value.trim() || null) : null;
    
    /** @type {HTMLInputElement | null} */
    const dataInicioInput = document.querySelector('#novaInspecaoDataInicio');
    const dataInicioRaw = dataInicioInput ? dataInicioInput.value : "";
    
    /** @type {HTMLInputElement | null} */
    const dpeInput = document.querySelector('#novaInspecaoDPE');
    const dataDPERaw = dpeInput ? dpeInput.value : "";

    // Converter yyyy-MM-dd -> ISO 8601 com horário local em UTC (meio-dia para evitar drift de fuso)
    const data_inicio = dataInicioRaw ? new Date(dataInicioRaw + 'T12:00:00').toISOString() : null;
    const data_fim_prevista = dataDPERaw ? new Date(dataDPERaw + 'T12:00:00').toISOString() : null;

    if (!aeronave_id || tipos_inspecao_ids.length === 0) {
        // @ts-ignore
        showToast("Selecione a aeronave e pelo menos 1 tipo de inspeção.", "error");
        if (btn) btn.disabled = false;
        return;
    }

    try {
        // @ts-ignore
        const resp = await apiFetch('/inspecoes/', {
            method: 'POST',
            body: { aeronave_id, tipos_inspecao_ids, observacoes, data_inicio, data_fim_prevista }
        });
        // @ts-ignore
        showToast("Inspeção aberta com sucesso!", "success");
        closeModalNovaInspecao();
        
        // Redireciona para detalhes
        setTimeout(() => {
            window.location.href = `/inspecoes/${resp.id}/detalhes`;
        }, 1000);
        
    } catch(err) {
        // @ts-ignore
        showToast(err.message || "Erro ao abrir inspeção.", "error");
        if (btn) btn.disabled = false;
    }
}
