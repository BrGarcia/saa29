/**
 * vencimentos.js — Controle de Vencimentos da Frota
 * Layout moderno: cards por aeronave com chips de equipamento.
 */

let matrizGlobal = null;
let filtroStatusAtual = 'todos';

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Configurar Listeners Primeiro (Para que a UI responda mesmo durante o loading)
    
    // Filtro de texto
    const filtroTexto = document.getElementById('filtro-vencimentos');
    if (filtroTexto) {
        filtroTexto.addEventListener('input', (e) => aplicarFiltros());
    }

    // Delegação de eventos para os itens de controle (CSP compliant)
    const grid = document.getElementById('vencimentos-grid');
    if (grid) {
        grid.addEventListener('click', (e) => {
            const row = e.target.closest('.clickable-control');
            if (!row) return;

            const { vencId, infoLabel, isProrrogado, novaVenc, docProrrog } = row.dataset;
            if (vencId) {
                openModalExecutar(vencId, infoLabel, isProrrogado === 'true', novaVenc, docProrrog);
            }
        });
    }

    // Formulários
    const formExec = document.getElementById('formExecutarControle');
    if (formExec) formExec.addEventListener('submit', salvarExecucao);

    const formProrrog = document.getElementById('formProrrogarVencimento');
    if (formProrrog) formProrrog.addEventListener('submit', salvarProrrogacao);

    // Botões estáticos e filtros de status
    setupStaticListeners();

    // 2. Carregar os dados
    await carregarMatriz();
});

function setupStaticListeners() {
    const btnTodos = document.getElementById('btn-filtro-todos');
    if (btnTodos) btnTodos.addEventListener('click', () => filtrarStatus('todos'));
    
    const btnWarn = document.getElementById('btn-filtro-warn');
    if (btnWarn) btnWarn.addEventListener('click', () => filtrarStatus('warn'));
    
    const btnDanger = document.getElementById('btn-filtro-danger');
    if (btnDanger) btnDanger.addEventListener('click', () => filtrarStatus('danger'));

    const btnProrrogado = document.getElementById('btn-filtro-prorrogado');
    if (btnProrrogado) btnProrrogado.addEventListener('click', () => filtrarStatus('prorrogado'));

    // Botões de fechar/cancelar modais
    document.getElementById('btn-close-exec-modal')?.addEventListener('click', closeModalExecutar);
    document.getElementById('btn-cancelar-exec')?.addEventListener('click', closeModalExecutar);
    document.getElementById('btn-close-prorrog-modal')?.addEventListener('click', closeModalProrrogar);
    document.getElementById('btn-cancelar-prorrog')?.addEventListener('click', closeModalProrrogar);

    // Ações de modais
    document.getElementById('btn-abrir-prorrog-modal')?.addEventListener('click', openModalProrrogarFromExec);
    document.getElementById('btn-cancelar-prorrogacao')?.addEventListener('click', cancelarProrrogacao);
}

// ─────────────────────────────────────────────
// Carregamento de Dados
// ─────────────────────────────────────────────

async function carregarMatriz() {
    const grid = document.getElementById('vencimentos-grid');
    try {
        const dados = await apiFetch('/vencimentos/matriz');
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
        document.getElementById('secao-cronograma').style.display = 'block';
        atualizarContadores(dados.aeronaves);
        renderizarGrid(dados.aeronaves);
        renderizarCronograma(dados.aeronaves);

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

    // Pills de resumo da aeronave (Apenas números com tooltip)
    let pillsHtml = '';
    if (danger > 0) pillsHtml += `<span class="pill pill-danger" title="${danger} Vencido(s)">${danger}</span>`;
    if (warn > 0) pillsHtml += `<span class="pill pill-warn" title="${warn} A Vencer">${warn}</span>`;
    if (prorrog > 0) pillsHtml += `<span class="pill pill-prorrogado" title="${prorrog} Prorrogado(s)">${prorrog}</span>`;

    const isVencido = danger > 0 || aeronave.status_vencimento === 'VENCIDO';
    wrapper.className = `acft-card ${isVencido ? 'vencida' : ''}`;
    wrapper.dataset.matricula = aeronave.matricula;

    // Header do card
    const header = document.createElement('div');
    const isAllOk = !isVencido && incompleto === 0 && (ok > 0 || warn > 0);
    const temControles = (ok + danger + warn + prorrog + incompleto + pendente) > 0;
    
    header.className = `acft-card-header ${isAllOk ? 'status-all-ok' : ''}`;
    
    // Status operacional da aeronave (Sincronizado com Frota)
    const statusAnv = (aeronave.status_aeronave || 'DISPONIVEL').toUpperCase();
    let statusAnvCls = 'badge-resolvida'; // Default DISPONIVEL/OPERACIONAL
    if (statusAnv === 'INDISPONIVEL') statusAnvCls = 'badge-pesquisa';
    else if (statusAnv === 'INSPEÇÃO') statusAnvCls = 'badge-inspecao';
    else if (statusAnv === 'ESTOCADA') statusAnvCls = 'badge-estocada';
    else if (statusAnv === 'INATIVA') statusAnvCls = 'badge-aberta';
    else if (statusAnv === 'OPERACIONAL') statusAnvCls = 'badge-resolvida';

    header.innerHTML = `
        <div style="display: flex; align-items: center; gap: 1rem;">
            <span class="acft-matricula">${escapeHtml(aeronave.matricula)}</span>
            <div class="acft-status-pills">
                ${pillsHtml || (temControles ? '' : '<span style="font-size:0.8rem;color:var(--text-secondary);">Sem controles</span>')}
            </div>
        </div>
        <span class="badge ${statusAnvCls}" style="font-size: 0.65rem; padding: 0.2rem 0.6rem; border: 1px solid rgba(255,255,255,0.1)">${statusAnv}</span>
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

    header.addEventListener('click', () => {
        const isOpen = body.style.display !== 'none';
        body.style.display = isOpen ? 'none' : 'flex';
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
            <div class="ctrl-row ${statusCls} ${vencId && slot.numero_serie ? 'clickable-control' : ''}" 
                 title="${titleText}"
                 data-venc-id="${vencId || ''}"
                 data-info-label="${escapeHtml(infoLabel)}"
                 data-is-prorrogado="${isProrrogado}"
                 data-nova-venc="${ctrl.data_nova_vencimento || ''}"
                 data-doc-prorrog="${escapeHtml(ctrl.numero_documento_prorrogacao || '')}">
                <span class="ctrl-nome">${ctrl.tipo_controle_nome}${isProrrogado ? '*' : ''}</span>
                <span class="ctrl-data">${dataText}</span>
            </div>
        `;
    });

    chip.innerHTML = `
        <div class="equip-chip-name">${escapeHtml(slot.sistema)}</div>
        <div class="equip-chip-sn ${snClass}">${escapeHtml(snText)}</div>
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
                else if (st === 'PENDENTE') pendente++;
                else pendente++; // Fallback
            });
        });
    });
    document.getElementById('cnt-ok').innerText = ok;
    document.getElementById('cnt-warn').innerText = warn;
    document.getElementById('cnt-danger').innerText = danger;
    document.getElementById('cnt-prorrogado').innerText = prorrog;
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
                    return false;
                })
            );
            if (!temProblema) return false;
        }
        return true;
    });

    renderizarGrid(aeronaves);
}
 
function renderizarCronograma(aeronaves) {
    const body = document.getElementById('cronograma-body');
    const containerVazio = document.getElementById('cronograma-vazio');
    const tabela = document.getElementById('tabela-cronograma');
    
    body.innerHTML = '';
    
    // 1. Coletar todos os controles com data
    const itens = [];
    const hoje = new Date();
    const limite = new Date();
    limite.setMonth(hoje.getMonth() + 6);
 
    aeronaves.forEach(acft => {
        acft.slots.forEach(slot => {
            slot.controles.forEach(ctrl => {
                const dataStr = ctrl.data_nova_vencimento || ctrl.data_vencimento;
                if (!dataStr) return;
 
                const dataVenc = new Date(dataStr + 'T12:00:00'); // Evitar problemas de timezone
                if (dataVenc >= hoje && dataVenc <= limite) {
                    itens.push({
                        aeronave: acft.matricula,
                        sistema: slot.sistema,
                        controle: ctrl.tipo_controle_nome,
                        vencimento: dataVenc,
                        vencimentoStr: dataStr,
                        status: ctrl.status
                    });
                }
            });
        });
    });
 
    if (itens.length === 0) {
        tabela.style.display = 'none';
        containerVazio.style.display = 'block';
        return;
    }
 
    tabela.style.display = 'table';
    containerVazio.style.display = 'none';
 
    // 2. Ordenar por data
    itens.sort((a, b) => a.vencimento - b.vencimento);
 
    // 3. Renderizar
    itens.forEach(it => {
        const tr = document.createElement('tr');
        const statusCls = mapStatusCls(it.status);
        const statusLabel = (it.status === 'VENCENDO') ? 'A VENCER' : (it.status || 'OK');
 
        tr.innerHTML = `
            <td><span style="font-weight:600; color:var(--text-primary);">${escapeHtml(it.sistema)}</span></td>
            <td><span class="cron-acft">${escapeHtml(it.aeronave)}</span></td>
            <td>${escapeHtml(it.controle)}</td>
            <td><span class="cron-date">${formatarData(it.vencimentoStr)}</span></td>
            <td><span class="badge ${statusCls.replace('status-', 'badge-')}" style="font-size:0.65rem;">${statusLabel}</span></td>
        `;
        body.appendChild(tr);
    });
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
        await apiFetch(`/vencimentos/${id}/executar`, {
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
        await apiFetch(`/vencimentos/${id}/prorrogar`, {
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
        await apiFetch(`/vencimentos/${id}/prorrogar`, {
            method: 'DELETE'
        });
        showToast('Prorrogação cancelada.', 'success');
        closeModalExecutar();
        await carregarMatriz();
    } catch (err) {
        showToast(err.message || 'Erro ao cancelar prorrogação.', 'error');
    }
}
