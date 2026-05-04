/**
 * Scripts para Detalhes e Execução de Tarefas de Inspeção
 */

let inspecaoAtual = null;

document.addEventListener("DOMContentLoaded", () => {
    const metaTag = document.querySelector('meta[name="inspecao-id"]');
    window.INSPECAO_ID = metaTag ? metaTag.content : null;

    if (!window.INSPECAO_ID) {
        window.location.href = '/inspecoes';
        return;
    }
    carregarDetalhesInspecao();

    document.getElementById('btn-close-modal-tarefa')?.addEventListener('click', closeModalTarefa);
    document.getElementById('btn-cancel-modal-tarefa')?.addEventListener('click', closeModalTarefa);
    document.getElementById('formExecutarTarefa')?.addEventListener('submit', salvarTarefa);

    document.getElementById('btn-open-modal-add-tarefa')?.addEventListener('click', openModalAddTarefa);
    document.getElementById('btn-close-modal-add-tarefa')?.addEventListener('click', closeModalAddTarefa);
    document.getElementById('btn-cancel-modal-add-tarefa')?.addEventListener('click', closeModalAddTarefa);
    document.getElementById('formAddTarefa')?.addEventListener('submit', salvarAddTarefa);
});

async function carregarDetalhesInspecao() {
    try {
        inspecaoAtual = await apiFetch(`/inspecoes/${window.INSPECAO_ID}`);
        renderizarCabecalho();
        renderizarTarefas();
    } catch(e) {
        showToast("Erro ao carregar detalhes da inspeção.", "error");
        document.getElementById('inspecao-header').innerHTML = '<p style="color: var(--status-danger);">Erro ao carregar. Volte e tente novamente.</p>';
    }
}


function renderizarLinhasDatas(inspecao) {
    const fmtData = (iso) => iso ? new Date(iso).toLocaleDateString('pt-BR') : '—';

    const dataInicio = inspecao.data_inicio ? fmtData(inspecao.data_inicio) : null;
    const dpe = inspecao.data_fim_prevista;

    let dpeLine = '';
    if (dpe) {
        const hoje = new Date();
        const dpeDt = new Date(dpe);
        const diffDias = Math.ceil((dpeDt - hoje) / (1000 * 60 * 60 * 24));

        let dpeColor = 'var(--text-secondary)';
        let dpeLabel = `DPE: ${fmtData(dpe)}`;
        if (inspecao.status !== 'CONCLUIDA' && inspecao.status !== 'CANCELADA') {
            if (diffDias < 0) {
                dpeColor = 'var(--status-danger)';
                dpeLabel += ` <span style="font-size:0.8rem; font-weight:600;">(VENCIDA há ${Math.abs(diffDias)}d)</span>`;
            } else if (diffDias <= 7) {
                dpeColor = 'var(--status-warning, #f39c12)';
                dpeLabel += ` <span style="font-size:0.8rem; font-weight:600;">(${diffDias}d restantes)</span>`;
            }
        }
        dpeLine = `<span style="color:${dpeColor};">${dpeLabel}</span>`;
    }

    const partes = [];
    if (dataInicio) partes.push(`<span>Início: <strong>${dataInicio}</strong></span>`);
    if (dpeLine)    partes.push(dpeLine);

    if (partes.length === 0) return '';
    return `<p style="margin: 0.25rem 0 0 0; font-size: 0.9rem; display: flex; gap: 1.5rem; flex-wrap: wrap;">${partes.join('')}</p>`;
}

function renderizarCabecalho() {
    const header = document.getElementById('inspecao-header');
    if (!inspecaoAtual) return;

    const pacotes = inspecaoAtual.tipos_aplicados.map(t => `${t.codigo} (${t.nome})`).join(' + ');
    const statusColor = getStatusColor(inspecaoAtual.status);
    
    // Calcula progresso
    const total = inspecaoAtual.tarefas.length;
    const concluidas = inspecaoAtual.tarefas.filter(t => t.status !== 'PENDENTE').length;
    const pct = total === 0 ? 0 : Math.round((concluidas / total) * 100);
    const todasObrigatoriasFeitas = inspecaoAtual.tarefas.filter(t => t.obrigatoria && t.status === 'PENDENTE').length === 0;
    const canAddTask = window.hasPermission('MANTENEDOR'); // Todos podem adicionar
    const canControlInspecao = window.hasPermission('ENCARREGADO') || window.hasPermission('INSPETOR');

    const containerBtnAdd = document.getElementById('container-btn-add-tarefa');
    if (containerBtnAdd) {
        if (canAddTask && (inspecaoAtual.status === 'ABERTA' || inspecaoAtual.status === 'EM_ANDAMENTO')) {
            containerBtnAdd.style.display = 'block';
        } else {
            containerBtnAdd.style.display = 'none';
        }
    }

    let botoesAcao = '';
    if (canControlInspecao && (inspecaoAtual.status === 'ABERTA' || inspecaoAtual.status === 'EM_ANDAMENTO')) {
        botoesAcao = `
            <div style="display: flex; gap: 1rem;">
                <button id="btn-cancelar-inspecao" class="btn btn-outline" style="color: var(--status-danger); border-color: var(--status-danger);">
                    Cancelar Inspeção
                </button>
                <button id="btn-concluir-inspecao" class="btn btn-inspecao" ${todasObrigatoriasFeitas && total > 0 ? '' : 'disabled style="opacity:0.5;" title="Conclua todas as tarefas obrigatórias"'} >
                    <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="vertical-align: middle; margin-right: 5px;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                    Concluir Inspeção
                </button>
            </div>
        `;
    }

    header.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
            <div>
                <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;">
                    <h2 style="margin: 0; font-size: 1.75rem;">A-29 ${inspecaoAtual.aeronave?.matricula || '---'}</h2>
                    <span style="font-size: 0.9rem; font-weight: 600; padding: 0.25rem 0.75rem; border-radius: 12px; background: ${statusColor}20; color: ${statusColor}; border: 1px solid ${statusColor};">
                        ${inspecaoAtual.status.replace('_', ' ')}
                    </span>
                </div>
                <p style="margin: 0; color: var(--text-secondary); font-size: 1rem;">
                    <strong>Pacote(s):</strong> ${pacotes}
                </p>
                <p style="margin: 0.25rem 0 0 0; color: var(--text-secondary); font-size: 0.9rem;">
                    Aberto em ${new Date(inspecaoAtual.data_abertura).toLocaleString()} por ${inspecaoAtual.aberto_por?.posto || ''} ${inspecaoAtual.aberto_por?.nome || 'Sistema'}${inspecaoAtual.aberto_por_trigrama ? ` <span style="font-family: monospace; font-size: 0.8rem; font-weight: 700; background: var(--bg-tertiary, rgba(0,0,0,0.08)); padding: 0.1rem 0.4rem; border-radius: 4px; letter-spacing: 0.05rem;">${escapeHtml(inspecaoAtual.aberto_por_trigrama)}</span>` : ''}
                </p>
                ${renderizarLinhasDatas(inspecaoAtual)}
                ${inspecaoAtual.observacoes ? `<p style="margin: 0.5rem 0 0 0; font-size: 0.9rem; background: rgba(0,0,0,0.05); padding: 0.5rem; border-radius: var(--radius-sm); border-left: 3px solid var(--primary-color);">Obs: ${escapeHtml(inspecaoAtual.observacoes)}</p>` : ''}
            </div>
            
            <div style="min-width: 200px;">
                ${botoesAcao}
            </div>
        </div>

        <div style="margin-top: 1rem;">
            <div style="display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 0.25rem; font-weight: 500;">
                <span>Progresso (${concluidas}/${total} tarefas concluídas)</span>
                <span>${pct}%</span>
            </div>
            <div style="width: 100%; height: 8px; background: var(--border-color); border-radius: 4px; overflow: hidden;">
                <div style="width: ${pct}%; height: 100%; background: ${pct === 100 ? 'var(--status-ok)' : 'var(--primary-color)'}; transition: width 0.3s ease;"></div>
            </div>
        </div>
    `;

    if (inspecaoAtual.status === 'ABERTA' || inspecaoAtual.status === 'EM_ANDAMENTO') {
        document.getElementById('btn-cancelar-inspecao')?.addEventListener('click', cancelarInspecao);
        document.getElementById('btn-concluir-inspecao')?.addEventListener('click', concluirInspecao);
    }
}

function renderizarTarefas() {
    const tbody = document.getElementById('tabela-tarefas-body');
    if (!inspecaoAtual || !inspecaoAtual.tarefas || inspecaoAtual.tarefas.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--text-secondary);">Nenhuma tarefa cadastrada nesta inspeção.</td></tr>';
        return;
    }

    tbody.innerHTML = '';
    
    // Ordena as tarefas por ordem
    const tarefas = [...inspecaoAtual.tarefas].sort((a,b) => a.ordem - b.ordem);

    tarefas.forEach(t => {
        const isClosed = (inspecaoAtual.status === 'CONCLUIDA' || inspecaoAtual.status === 'CANCELADA');
        const stColor = getTarefaStatusColor(t.status);
        
        let rastreabilidade = '<div style="color: var(--text-secondary); text-align: center;">—</div>';
        if (t.data_execucao && t.executado_por) {
            const date = new Date(t.data_execucao);
            const dia = String(date.getDate()).padStart(2, '0');
            const mes = String(date.getMonth() + 1).padStart(2, '0');
            const ano = String(date.getFullYear()).slice(-2);
            const hora = String(date.getHours()).padStart(2, '0');
            const min = String(date.getMinutes()).padStart(2, '0');
            
            rastreabilidade = `<div style="font-size: 0.8rem; text-align: center;">
                <div style="color: var(--text-secondary);">${dia}/${mes}/${ano} ${hora}:${min}</div>
                <div style="font-weight: 700; color: var(--primary-color);">${t.executado_por.trigrama || 'SYS'}</div>
            </div>`;
        }
        
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--border-color)';
        
        // Background leve se já estiver concluída
        if (t.status !== 'PENDENTE') {
            tr.style.background = 'rgba(46, 204, 113, 0.03)';
        }

        tr.innerHTML = `
            <td style="padding: 0.75rem; text-align: center; font-weight: 600; color: var(--text-secondary);">${t.ordem}</td>
            <td style="padding: 0.75rem; color: var(--text-secondary);">${escapeHtml(t.sistema || 'Geral')}</td>
            <td style="padding: 0.75rem;">
                <div style="font-weight: 500;">
                    ${!t.tarefa_catalogo_id ? `<span style="font-size: 0.65rem; background: var(--primary-color); color: white; padding: 2px 6px; border-radius: 4px; margin-right: 5px; font-weight: bold; vertical-align: middle;" title="Tarefa Adicionada Manualmente">${escapeHtml(inspecaoAtual.aberto_por?.trigrama || 'EXT')}</span>` : ''}
                    ${escapeHtml(t.titulo)}
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(t.descricao || '')}</div>
                ${t.observacao_execucao ? `<div style="font-size: 0.8rem; color: var(--text-color); margin-top: 4px; border-left: 2px solid ${stColor}; padding-left: 5px;"><i>Obs: ${escapeHtml(t.observacao_execucao)}</i></div>` : ''}
            </td>
            <td style="padding: 0.75rem; text-align: center;">
                <span style="display: inline-block; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; background: ${stColor}20; color: ${stColor}; border: 1px solid ${stColor};">
                    ${t.status}
                </span>
            </td>
            <td style="padding: 0.75rem;">
                ${rastreabilidade}
            </td>
            <td style="padding: 0.75rem; text-align: right;">
                <button type="button" class="btn-icon btn-executar" title="${isClosed ? 'Visualizar' : 'Atualizar Status'}" style="color: var(--primary-color);">
                    ${isClosed || t.status !== 'PENDENTE' ? 
                        '<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>' : 
                        '<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>'}
                </button>
            </td>
        `;
        
        tr.querySelector('.btn-executar').addEventListener('click', () => openModalTarefa(t.id));
        tbody.appendChild(tr);
    });
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

function getTarefaStatusColor(status) {
    const map = {
        'PENDENTE': '#f39c12',
        'CONCLUIDA': '#2ecc71',
        'N/A': '#95a5a6'
    };
    return map[status] || 'var(--text-secondary)';
}

function openModalTarefa(tarefaId) {
    const t = inspecaoAtual.tarefas.find(x => x.id === tarefaId);
    if (!t) return;

    document.getElementById('tarefaIdInput').value = t.id;
    document.getElementById('tarefaTituloDisplay').innerText = t.titulo;
    document.getElementById('tarefaDescDisplay').innerText = t.descricao || t.sistema || '';
    
    const statusSelect = document.getElementById('tarefaStatusInput');
    statusSelect.value = t.status === 'PENDENTE' ? 'CONCLUIDA' : t.status; // Default para concluída
    document.getElementById('tarefaObsInput').value = t.observacao_execucao || '';
    
    // Se inspeção já fechada, desabilita inputs
    const isClosed = (inspecaoAtual.status === 'CONCLUIDA' || inspecaoAtual.status === 'CANCELADA');
    statusSelect.disabled = isClosed;
    document.getElementById('tarefaObsInput').disabled = isClosed;
    document.getElementById('btnSalvarTarefa').style.display = isClosed ? 'none' : 'block';

    document.getElementById('modal-executar-tarefa').style.display = 'flex';
}

function closeModalTarefa() {
    document.getElementById('modal-executar-tarefa').style.display = 'none';
    document.getElementById('formExecutarTarefa').reset();
}

async function salvarTarefa(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarTarefa');
    btn.disabled = true;

    const tarefaId = document.getElementById('tarefaIdInput').value;
    const status = document.getElementById('tarefaStatusInput').value;
    const observacao_execucao = document.getElementById('tarefaObsInput').value.trim() || null;

    try {
        await apiFetch(`/inspecoes/tarefas/${tarefaId}`, {
            method: 'PUT',
            body: { status, observacao_execucao }
        });
        showToast("Tarefa atualizada!", "success");
        closeModalTarefa();
        carregarDetalhesInspecao();
    } catch(err) {
        showToast(err.message || "Erro ao atualizar tarefa.", "error");
    } finally {
        btn.disabled = false;
    }
}

async function concluirInspecao() {
    if(!confirm("Atenção: Deseja concluir esta inspeção? Nenhuma tarefa poderá ser alterada e a aeronave retornará para o status DISPONIVEL.")) return;

    try {
        await apiFetch(`/inspecoes/${inspecaoAtual.id}/concluir`, { method: 'POST' });
        showToast("Inspeção concluída com sucesso!", "success");
        carregarDetalhesInspecao();
    } catch(err) {
        showToast(err.message || "Erro ao concluir inspeção.", "error");
    }
}

async function cancelarInspecao() {
    if(!confirm("Atenção: Deseja cancelar esta inspeção? A aeronave retornará para o status DISPONIVEL.")) return;

    try {
        await apiFetch(`/inspecoes/${inspecaoAtual.id}/cancelar`, { method: 'POST' });
        showToast("Inspeção cancelada.", "info");
        carregarDetalhesInspecao();
    } catch(err) {
        showToast(err.message || "Erro ao cancelar inspeção.", "error");
    }
}

function openModalAddTarefa() {
    document.getElementById('modal-add-tarefa').style.display = 'flex';
    document.getElementById('addTarefaTituloInput').focus();
}

function closeModalAddTarefa() {
    document.getElementById('modal-add-tarefa').style.display = 'none';
    document.getElementById('formAddTarefa').reset();
}

async function salvarAddTarefa(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarAddTarefa');
    btn.disabled = true;

    const titulo = document.getElementById('addTarefaTituloInput').value.trim();
    const sistema = document.getElementById('addTarefaSistemaInput').value.trim() || null;
    const descricao = document.getElementById('addTarefaDescInput').value.trim() || null;
    const obrigatoria = document.getElementById('addTarefaObrigatoriaInput').checked;

    const tarefas = inspecaoAtual.tarefas || [];
    const ordens = tarefas.map(t => t.ordem).filter(o => !isNaN(o));
    const proximaOrdem = ordens.length > 0 ? Math.max(...ordens) + 1 : 1;

    try {
        await apiFetch(`/inspecoes/${inspecaoAtual.id}/tarefas`, {
            method: 'POST',
            body: {
                titulo,
                descricao,
                sistema,
                obrigatoria,
                ordem: proximaOrdem
            }
        });
        showToast("Tarefa extra adicionada!", "success");
        closeModalAddTarefa();
        carregarDetalhesInspecao();
    } catch(err) {
        showToast(err.message || "Erro ao adicionar tarefa.", "error");
    } finally {
        btn.disabled = false;
    }
}
