/**
 * vencimentos.js — Controle de Vencimentos da Frota
 * Layout moderno: cards por aeronave com chips de equipamento.
 */

let matrizGlobal = null;
let filtroStatusAtual = 'todos';

document.addEventListener("DOMContentLoaded", async () => {
    await carregarMatriz();

    document.getElementById('filtro-vencimentos').addEventListener('input', (e) => {
        aplicarFiltros();
    });

    const formExec = document.getElementById('formExecutarControle');
    if (formExec) formExec.addEventListener('submit', salvarExecucao);

    const formProrrog = document.getElementById('formProrrogarVencimento');
    if (formProrrog) formProrrog.addEventListener('submit', salvarProrrogacao);
});

// ─────────────────────────────────────────────
// Carregamento de Dados
// ─────────────────────────────────────────────

async function carregarMatriz() {
    const grid = document.getElementById('vencimentos-grid');
    try {
        const dados = await apiFetch('/equipamentos/vencimentos/matriz');
        matrizGlobal = dados;

        if (!dados.aeronaves || dados.aeronaves.length === 0) {
            grid.innerHTML = `
                <div class="card glass-panel" style="padding: 3rem; text-align: center; color: var(--text-secondary);">
                    Nenhum dado de vencimento configurado.
                    Acesse <a href="/configuracoes" style="color: var(--primary-color);">Configurações</a>
                    para cadastrar equipamentos e regras de controle.
                </div>`;
            return;
        }

        // Mostrar contadores
        document.getElementById('summary-cards').style.display = 'grid';
        atualizarContadores(dados.aeronaves);
        renderizarGrid(dados.aeronaves);

    } catch (err) {
        console.error(err);
        grid.innerHTML = `<div class="card glass-panel" style="padding: 2rem; text-align: center; color: var(--status-danger);">
            Erro ao carregar dados: ${err.message}
        </div>`;
    }
}

// ─────────────────────────────────────────────
// Renderização
// ─────────────────────────────────────────────

function renderizarGrid(aeronaves) {
    const grid = document.getElementById('vencimentos-grid');
    grid.innerHTML = '';

    if (aeronaves.length === 0) {
        grid.innerHTML = `<div class="card" style="padding: 2rem; text-align: center; color: var(--text-secondary);">
            Nenhuma aeronave encontrada com os filtros aplicados.
        </div>`;
        return;
    }

    aeronaves.forEach(aeronave => {
        const card = criarCardAeronave(aeronave);
        grid.appendChild(card);
    });
}

function criarCardAeronave(aeronave) {
    const wrapper = document.createElement('div');
    wrapper.className = 'acft-card';
    wrapper.dataset.matricula = aeronave.matricula;

    // Calcular totais de status para esta aeronave
    let ok = 0, warn = 0, danger = 0, pendente = 0, prorrog = 0, incompleto = 0;
    aeronave.slots.forEach(slot => {
        slot.controles.forEach(ctrl => {
            const s = (ctrl.status || '').toUpperCase();
            if (s === 'OK') ok++;
            else if (s === 'VENCENDO') warn++;
            else if (s === 'VENCIDO') danger++;
            else if (s === 'PRORROGADO') prorrog++;
            else if (s === 'FALTANTE') incompleto++;
            else pendente++;
        });
    });

    // Pills de resumo da aeronave
    let pillsHtml = '';
    if (danger > 0) pillsHtml += `<span class="pill pill-danger">● ${danger} Vencido${danger > 1 ? 's' : ''}</span>`;
    if (warn > 0) pillsHtml += `<span class="pill pill-warn">● ${warn} A Vencer</span>`;
    if (incompleto > 0) pillsHtml += `<span class="pill pill-incompleta">● ${incompleto} Faltante${incompleto > 1 ? 's' : ''}</span>`;
    if (prorrog > 0) pillsHtml += `<span class="pill pill-prorrogado">● ${prorrog} Prorrogado${prorrog > 1 ? 's' : ''}</span>`;
    if (ok > 0 && danger === 0 && warn === 0 && prorrog === 0 && incompleto === 0) pillsHtml += `<span class="pill pill-ok">✓ Em Dia</span>`;

    // Header do card
    const header = document.createElement('div');
    header.className = 'acft-card-header';
    header.innerHTML = `
        <span class="acft-matricula">${aeronave.matricula}</span>
        <div class="acft-status-pills">${pillsHtml || '<span style="font-size:0.8rem;color:var(--text-secondary);">Sem controles</span>'}</div>
        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color: var(--text-secondary); transition: transform 0.2s;" class="chevron"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
    `;

    // Body com chips de equipamentos
    const body = document.createElement('div');
    body.className = 'acft-card-body';

    aeronave.slots.forEach(slot => {
        const chip = criarChipEquipamento(slot, aeronave);
        body.appendChild(chip);
    });

    // Toggle collapse — inicia recolhido
    body.style.display = 'none';
    header.querySelector('.chevron').style.transform = 'rotate(-90deg)';

    header.addEventListener('click', () => {
        const isOpen = body.style.display !== 'none';
        body.style.display = isOpen ? 'none' : 'flex';
        header.querySelector('.chevron').style.transform = isOpen ? 'rotate(-90deg)' : '';
    });

    wrapper.appendChild(header);
    wrapper.appendChild(body);
    return wrapper;
}

function criarChipEquipamento(slot, aeronave) {
    const chip = document.createElement('div');
    chip.className = 'equip-chip';

    const snClass = slot.numero_serie ? '' : 'empty';
    const snText = slot.numero_serie || '— vazio —';

    let controlesHtml = '';
    slot.controles.forEach(ctrl => {
        const statusCls = mapStatusCls(ctrl.status);
        const dataVenc = (ctrl.status === 'PRORROGADO') ? ctrl.data_nova_vencimento : ctrl.data_vencimento;
        const dataText = dataVenc ? formatarData(dataVenc) : (ctrl.status === 'FALTANTE' ? 'NÃO INSTALADO' : '---');
        const vencId = ctrl.vencimento_id || '';
        const infoLabel = `${aeronave.matricula} / ${slot.sistema} / ${ctrl.tipo_controle_nome}`;

        const isProrrogado = ctrl.status === 'PRORROGADO';
        const isFaltante = ctrl.status === 'FALTANTE';

        let titleText = isProrrogado 
            ? `PRORROGADO (Engenharia) Doc: ${ctrl.numero_documento_prorrogacao || 'N/A'}\nNova Data: ${dataText}\nVenc. Original: ${formatarData(ctrl.data_vencimento)}`
            : (ctrl.data_vencimento ? 'Vence: ' + formatarData(ctrl.data_vencimento) : 'Sem execução registrada');
        
        if (isFaltante) titleText = "EQUIPAMENTO NÃO INSTALADO NO SLOT";

        controlesHtml += `
            <div class="ctrl-row ${statusCls}" 
                 title="${titleText}"
                 ${vencId && slot.numero_serie ? `onclick="openModalExecutar('${vencId}', '${infoLabel}', ${isProrrogado}, '${ctrl.data_nova_vencimento}', '${ctrl.numero_documento_prorrogacao || ''}')"` : ''}>
                <span class="ctrl-nome">${ctrl.tipo_controle_nome}${isProrrogado ? '*' : ''}</span>
                <span class="ctrl-data">${dataText}</span>
            </div>
        `;
    });

    chip.innerHTML = `
        <div class="equip-chip-name">${slot.sistema}</div>
        <div class="equip-chip-sn ${snClass}">${snText}</div>
        <div class="equip-chip-controls">${controlesHtml}</div>
    `;

    return chip;
}

// ─────────────────────────────────────────────
// Contadores e Filtros
// ─────────────────────────────────────────────

function atualizarContadores(aeronaves) {
    let ok = 0, warn = 0, danger = 0, pendente = 0, prorrog = 0, incompleto = 0;
    aeronaves.forEach(a => {
        a.slots.forEach(s => {
            s.controles.forEach(c => {
                const st = (c.status || '').toUpperCase();
                if (st === 'OK') ok++;
                else if (st === 'VENCENDO') warn++;
                else if (st === 'VENCIDO') danger++;
                else if (st === 'PRORROGADO') prorrog++;
                else if (st === 'FALTANTE') incompleto++;
                else pendente++;
            });
        });
    });
    document.getElementById('cnt-ok').innerText = ok;
    document.getElementById('cnt-warn').innerText = warn;
    document.getElementById('cnt-danger').innerText = danger;
    document.getElementById('cnt-pendente').innerText = pendente;
    document.getElementById('cnt-prorrogado').innerText = prorrog;
    document.getElementById('cnt-incompleta').innerText = incompleto;
}

function filtrarStatus(tipo) {
    filtroStatusAtual = tipo;
    aplicarFiltros();
}

function aplicarFiltros() {
    if (!matrizGlobal) return;

    const termo = document.getElementById('filtro-vencimentos').value.toLowerCase();

    let aeronaves = matrizGlobal.aeronaves.filter(a => {
        // Filtro por texto
        if (termo) {
            const matchMatricula = a.matricula.toLowerCase().includes(termo);
            const matchSlot = a.slots.some(s => s.sistema.toLowerCase().includes(termo));
            if (!matchMatricula && !matchSlot) return false;
        }
        // Filtro por status
        if (filtroStatusAtual !== 'todos') {
            const temProblema = a.slots.some(s =>
                s.controles.some(c => {
                    const st = (c.status || '').toUpperCase();
                    if (filtroStatusAtual === 'warn') return st === 'VENCENDO';
                    if (filtroStatusAtual === 'danger') return st === 'VENCIDO';
                    if (filtroStatusAtual === 'prorrogado') return st === 'PRORROGADO';
                    if (filtroStatusAtual === 'incompleta') return st === 'FALTANTE';
                    return false;
                })
            );
            if (!temProblema) return false;
        }
        return true;
    });

    renderizarGrid(aeronaves);
}

// ─────────────────────────────────────────────
// Utilitários
// ─────────────────────────────────────────────

function mapStatusCls(status) {
    if (!status) return 'status-pendente';
    switch (status.toUpperCase()) {
        case 'OK': return 'status-ok';
        case 'VENCENDO': return 'status-vencendo';
        case 'VENCIDO': return 'status-vencido';
        case 'PRORROGADO': return 'status-prorrogado';
        case 'FALTANTE': return 'status-incompleta';
        default: return 'status-pendente';
    }
}

function formatarData(dataStr) {
    if (!dataStr) return '---';
    const [y, m, d] = dataStr.split('-');
    return `${d}/${m}/${y}`;
}

// ─────────────────────────────────────────────
// Modal de Execução
// ─────────────────────────────────────────────

function openModalExecutar(vencimentoId, info, prorrogado = false, dataNova = '', doc = '') {
    document.getElementById('exec-vencimento-id').value = vencimentoId;
    document.getElementById('exec-info-label').innerText = info;
    document.getElementById('exec-data-input').value = new Date().toISOString().split('T')[0];
    
    // Alerta de Prorrogação
    const alert = document.getElementById('exec-prorrog-alert');
    if (prorrogado) {
        document.getElementById('exec-prorrog-desc').innerText = `Até ${formatarData(dataNova)} (Doc: ${doc || 'N/A'})`;
        alert.style.display = 'block';
    } else {
        alert.style.display = 'none';
    }

    document.getElementById('modal-executar-controle').style.display = 'flex';
}

function closeModalExecutar() {
    document.getElementById('modal-executar-controle').style.display = 'none';
    document.getElementById('formExecutarControle').reset();
}

async function salvarExecucao(e) {
    e.preventDefault();
    const id = document.getElementById('exec-vencimento-id').value;
    const data = document.getElementById('exec-data-input').value;
    const btn = document.getElementById('btnConfirmarExec');

    if (!id) { showToast('Nenhum controle selecionado.', 'error'); return; }

    btn.disabled = true;
    try {
        await apiFetch(`/equipamentos/vencimentos/${id}/executar`, {
            method: 'PATCH',
            body: { data_ultima_exec: data }
        });
        showToast('Execução registrada com sucesso!', 'success');
        closeModalExecutar();
        await carregarMatriz();
    } catch (err) {
        showToast(err.message || 'Erro ao registrar execução.', 'error');
    } finally {
        btn.disabled = false;
    }
}

window.openModalExecutar = openModalExecutar;
window.closeModalExecutar = closeModalExecutar;
window.openModalProrrogarFromExec = openModalProrrogarFromExec;
window.closeModalProrrogar = closeModalProrrogar;
window.cancelarProrrogacao = cancelarProrrogacao;
window.filtrarStatus = filtrarStatus;


// ─────────────────────────────────────────────
// Modal de Prorrogação
// ─────────────────────────────────────────────

function openModalProrrogarFromExec() {
    const vencId = document.getElementById('exec-vencimento-id').value;
    const info = document.getElementById('exec-info-label').innerText;
    
    closeModalExecutar();
    
    document.getElementById('prorrog-vencimento-id').value = vencId;
    document.getElementById('prorrog-info-label').innerText = info;
    document.getElementById('prorrog-data-input').value = new Date().toISOString().split('T')[0];
    document.getElementById('modal-prorrogacao-vencimento').style.display = 'flex';
}

function closeModalProrrogar() {
    document.getElementById('modal-prorrogacao-vencimento').style.display = 'none';
    document.getElementById('formProrrogarVencimento').reset();
}

async function salvarProrrogacao(e) {
    e.preventDefault();
    const id = document.getElementById('prorrog-vencimento-id').value;
    const doc = document.getElementById('prorrog-doc-input').value;
    const data = document.getElementById('prorrog-data-input').value;
    const dias = document.getElementById('prorrog-dias-input').value;
    const motivo = document.getElementById('prorrog-motivo-input').value;
    const btn = document.getElementById('btnConfirmarProrrog');

    btn.disabled = true;
    try {
        await apiFetch(`/equipamentos/vencimentos/${id}/prorrogar`, {
            method: 'POST',
            body: {
                numero_documento: doc,
                data_concessao: data,
                dias_adicionais: parseInt(dias),
                motivo: motivo
            }
        });
        showToast('Prorrogação concedida com sucesso!', 'success');
        closeModalProrrogar();
        await carregarMatriz();
    } catch (err) {
        showToast(err.message || 'Erro ao registrar prorrogação.', 'error');
    } finally {
        btn.disabled = false;
    }
}

async function cancelarProrrogacao() {
    const id = document.getElementById('exec-vencimento-id').value;
    if (!id) return;
    
    if (!confirm('Deseja realmente CANCELAR a prorrogação deste item? O status voltará ao real imediatamente.')) return;
    
    try {
        await apiFetch(`/equipamentos/vencimentos/${id}/prorrogar`, {
            method: 'DELETE'
        });
        showToast('Prorrogação cancelada.', 'success');
        closeModalExecutar();
        await carregarMatriz();
    } catch (err) {
        showToast(err.message || 'Erro ao cancelar prorrogação.', 'error');
    }
}
