/**
 * Scripts para Listagem de Inspeções
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

async function carregarFiltros() {
    const selectAeronave = document.getElementById('filtroAeronave');
    const selectNovaAeronave = document.getElementById('novaInspecaoAeronave');
    
    try {
        const [aeronaves, tipos] = await Promise.all([
            apiFetch('/aeronaves/'),
            apiFetch('/inspecoes/tipos')
        ]);
        
        aeronaves.sort((a,b) => a.matricula.localeCompare(b.matricula)).forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.id;
            opt.text = a.matricula;
            selectAeronave.appendChild(opt.cloneNode(true));
            
            if(a.status !== 'INATIVA' && a.status !== 'ESTOCADA') {
                selectNovaAeronave.appendChild(opt);
            }
        });

        const selectTipos = document.getElementById('novaInspecaoTipos');
        selectTipos.innerHTML = '';
        tipos.filter(t => t.ativo).forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.text = `${t.codigo} - ${t.nome}${t.duracao_dias > 0 ? ` (${t.duracao_dias}d)` : ''}`;
            opt.dataset.duracao = t.duracao_dias || 0;
            selectTipos.appendChild(opt);
        });
        
    } catch(e) {
        showToast("Erro ao carregar filtros.", "error");
    }
}

async function carregarInspecoes() {
    const container = document.getElementById('lista-inspecoes');
    container.innerHTML = '<p style="color: var(--text-secondary); text-align: center; grid-column: 1 / -1;">Carregando inspeções...</p>';
    
    const aeronaveId = document.getElementById('filtroAeronave').value;
    const status = document.getElementById('filtroStatus').value;
    
    let url = '/inspecoes/?limit=50';
    if(aeronaveId) url += `&aeronave_id=${aeronaveId}`;
    if(status) url += `&status=${status}`;

    try {
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
            
            const pacotes = i.tipos_aplicados.map(t => t.codigo).join(' + ');

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; font-size: 1.25rem;">A-29 ${i.aeronave?.matricula || '---'}</h3>
                    <span style="font-size: 0.8rem; font-weight: 600; padding: 0.25rem 0.5rem; border-radius: 12px; background: ${statusColor}20; color: ${statusColor};">
                        ${i.status.replace('_', ' ')}
                    </span>
                </div>
                
                <div>
                    <div style="font-weight: 500; color: var(--text-color); margin-bottom: 0.25rem;">Pacote(s): ${pacotes}</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">
                        Abertura: ${new Date(i.data_abertura).toLocaleDateString()}
                    </div>
                </div>

                <div style="margin-top: auto;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem; font-weight: 500;">
                        <span>Progresso</span>
                        <span>${i.tarefas_concluidas}/${i.total_tarefas} (${pct}%)</span>
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

function getStatusColor(status) {
    const map = {
        'ABERTA': '#f39c12',
        'EM_ANDAMENTO': '#3498db',
        'CONCLUIDA': '#2ecc71',
        'CANCELADA': '#e74c3c'
    };
    return map[status] || 'var(--text-secondary)';
}

function openModalNovaInspecao() {
    document.getElementById('modal-nova-inspecao').style.display = 'flex';
    document.getElementById('novaInspecaoAeronave').value = '';
    document.getElementById('novaInspecaoTipos').selectedIndex = -1;
    document.getElementById('novaInspecaoObs').value = '';

    // Preencher data de início com hoje
    const hoje = new Date().toISOString().split('T')[0];
    document.getElementById('novaInspecaoDataInicio').value = hoje;
    document.getElementById('novaInspecaoDPE').value = '';
}

function closeModalNovaInspecao() {
    document.getElementById('modal-nova-inspecao').style.display = 'none';
}

function recalcularDPE() {
    const selectTipos = document.getElementById('novaInspecaoTipos');
    const dataInicioInput = document.getElementById('novaInspecaoDataInicio');
    const dpeInput = document.getElementById('novaInspecaoDPE');

    const selectedOptions = Array.from(selectTipos.selectedOptions);
    if (selectedOptions.length === 0 || !dataInicioInput.value) {
        dpeInput.value = '';
        return;
    }

    const maxDuracao = Math.max(...selectedOptions.map(o => parseInt(o.dataset.duracao, 10) || 0));
    if (maxDuracao === 0) {
        dpeInput.value = 'Sem duração cadastrada';
        dpeInput.style.color = 'var(--status-danger)';
        return;
    }

    const dataInicio = new Date(dataInicioInput.value + 'T00:00:00');
    const dpe = new Date(dataInicio);
    dpe.setDate(dpe.getDate() + maxDuracao);
    dpeInput.value = dpe.toLocaleDateString('pt-BR');
    dpeInput.style.color = 'var(--text-secondary)';
}

async function salvarNovaInspecao(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarInspecao');
    btn.disabled = true;

    const aeronave_id = document.getElementById('novaInspecaoAeronave').value;
    const tiposSelect = document.getElementById('novaInspecaoTipos');
    const tipos_inspecao_ids = Array.from(tiposSelect.selectedOptions).map(o => o.value);
    const observacoes = document.getElementById('novaInspecaoObs').value.trim() || null;
    const dataInicioRaw = document.getElementById('novaInspecaoDataInicio').value;
    // Converter yyyy-MM-dd -> ISO 8601 com horário local em UTC (meio-dia para evitar drift de fuso)
    const data_inicio = dataInicioRaw ? new Date(dataInicioRaw + 'T12:00:00').toISOString() : null;

    if (!aeronave_id || tipos_inspecao_ids.length === 0) {
        showToast("Selecione a aeronave e pelo menos 1 tipo de inspeção.", "error");
        btn.disabled = false;
        return;
    }

    try {
        const resp = await apiFetch('/inspecoes/', {
            method: 'POST',
            body: { aeronave_id, tipos_inspecao_ids, observacoes, data_inicio }
        });
        showToast("Inspeção aberta com sucesso!", "success");
        closeModalNovaInspecao();
        
        // Redireciona para detalhes
        setTimeout(() => {
            window.location.href = `/inspecoes/${resp.id}/detalhes`;
        }, 1000);
        
    } catch(err) {
        showToast(err.message || "Erro ao abrir inspeção.", "error");
        btn.disabled = false;
    }
}
