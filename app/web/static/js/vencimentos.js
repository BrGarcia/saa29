/**
 * vencimentos.js — Visão Matricial de Vencimentos da Frota
 * 
 * Estrutura da tabela (seguindo o padrão do modelo real):
 * 
 *  Matrícula | EGIR              | ELT                   | V/UHF2      | VADR
 *            | SN  | TBO         | SN  | CRI   | TBV     | SN  | TBV   | SN  | TBV | RBA
 *  5902      | 110 | 29/03/2023  | 115 | 04/04 | 27/11   | ... | ...   | ... | ... | ...
 */

document.addEventListener("DOMContentLoaded", async () => {
    await carregarMatriz();

    const formExec = document.getElementById('formExecutarControle');
    if (formExec) formExec.addEventListener('submit', salvarExecucao);
});

let matrizGlobal = null;

async function carregarMatriz() {
    const loading = document.getElementById('vencimentos-loading');
    const container = document.getElementById('vencimentos-table-container');
    const empty = document.getElementById('vencimentos-empty');
    const error = document.getElementById('vencimentos-error');

    try {
        const dados = await apiFetch('/equipamentos/vencimentos/matriz');
        matrizGlobal = dados;

        if (!dados.aeronaves || dados.aeronaves.length === 0) {
            loading.style.display = 'none';
            empty.style.display = 'block';
            return;
        }

        renderizarMatriz(dados);

        loading.style.display = 'none';
        container.style.display = 'block';

    } catch (err) {
        console.error('Erro ao carregar matriz:', err);
        loading.style.display = 'none';
        error.style.display = 'block';
        error.innerText = `Erro ao carregar dados: ${err.message}`;
    }
}

function renderizarMatriz(dados) {
    const { cabecalho, aeronaves } = dados;

    // Sistemas na ordem recebida (mantém a ordem do backend)
    const sistemas = Object.keys(cabecalho);

    if (sistemas.length === 0) return;

    renderizarCabecalho(sistemas, cabecalho, aeronaves);
    renderizarLinhas(sistemas, cabecalho, aeronaves);
}

function renderizarCabecalho(sistemas, cabecalho, aeronaves) {
    const thead = document.getElementById('tabela-head');
    thead.innerHTML = '';

    // LINHA 1: Matrícula + grupos de sistema (com colspan)
    const tr1 = document.createElement('tr');

    // Célula "Matrícula" com rowspan=2
    const thMatricula = document.createElement('th');
    thMatricula.rowSpan = 2;
    thMatricula.className = 'col-matricula';
    thMatricula.innerText = 'Matrícula';
    thMatricula.style.verticalAlign = 'middle';
    tr1.appendChild(thMatricula);

    for (const sistema of sistemas) {
        const controles = cabecalho[sistema];
        // Cada grupo tem: 1 col SN + N cols de controle
        const colspan = 1 + controles.length;

        const th = document.createElement('th');
        th.colSpan = colspan;
        th.className = 'group-header';
        th.innerText = sistema;
        // Estilo de separação entre grupos
        th.style.borderLeft = '2px solid var(--primary-color)';
        tr1.appendChild(th);
    }
    thead.appendChild(tr1);

    // LINHA 2: "SN" + nome de cada controle para cada sistema
    const tr2 = document.createElement('tr');

    for (const sistema of sistemas) {
        const controles = cabecalho[sistema];

        // Col SN
        const thSn = document.createElement('th');
        thSn.innerText = 'S/N';
        thSn.style.borderLeft = '2px solid var(--primary-color)';
        thSn.style.minWidth = '65px';
        tr2.appendChild(thSn);

        // Cols de controle
        for (const c of controles) {
            const thC = document.createElement('th');
            thC.innerText = c;
            thC.style.minWidth = '85px';
            tr2.appendChild(thC);
        }
    }
    thead.appendChild(tr2);
}

function renderizarLinhas(sistemas, cabecalho, aeronaves) {
    const tbody = document.getElementById('tabela-body');
    tbody.innerHTML = '';

    // Indexar slots de cada aeronave por sistema
    for (const aeronave of aeronaves) {
        const tr = document.createElement('tr');

        // Col matrícula
        const tdMat = document.createElement('td');
        tdMat.className = 'col-matricula';
        tdMat.innerText = aeronave.matricula;
        tr.appendChild(tdMat);

        // Agrupar slots por sistema
        const slotsPorSistema = {};
        for (const slot of aeronave.slots) {
            if (!slotsPorSistema[slot.sistema]) slotsPorSistema[slot.sistema] = [];
            slotsPorSistema[slot.sistema].push(slot);
        }

        for (const sistema of sistemas) {
            const controles = cabecalho[sistema];
            const slotsDoSistema = slotsPorSistema[sistema] || [];

            if (slotsDoSistema.length === 0) {
                // Sem slot configurado para este sistema: células vazias
                const tdSn = document.createElement('td');
                tdSn.style.borderLeft = '2px solid var(--primary-color)';
                tr.appendChild(tdSn);
                for (let i = 0; i < controles.length; i++) {
                    tr.appendChild(document.createElement('td'));
                }
                continue;
            }

            // Por enquanto usamos o primeiro slot do sistema (ex: EGIR1)
            // Futuramente, se houver EGIR1 e EGIR2, poderão ser linhas separadas
            const slot = slotsDoSistema[0];

            // Col SN instalado
            const tdSn = document.createElement('td');
            tdSn.className = 'cell-sn';
            tdSn.style.borderLeft = '2px solid var(--primary-color)';
            tdSn.innerText = slot.numero_serie || '—';
            if (!slot.numero_serie) tdSn.style.color = 'var(--text-secondary)';
            tr.appendChild(tdSn);

            // Indexar controles do slot por nome
            const ctrlMap = {};
            for (const c of slot.controles) ctrlMap[c.tipo_controle_nome] = c;

            // Cols de cada tipo de controle
            for (const tipoNome of controles) {
                const ctrl = ctrlMap[tipoNome];
                const td = document.createElement('td');
                td.className = 'cell-venc';

                if (!slot.numero_serie) {
                    // Slot vazio: sem dados
                    td.innerText = '—';
                    td.classList.add('status-pendente');
                } else if (!ctrl || !ctrl.data_vencimento) {
                    // Item instalado mas sem execução registrada
                    td.innerText = 'Pendente';
                    td.classList.add('status-pendente');
                    if (ctrl && ctrl.vencimento_id) {
                        td.title = 'Clique para registrar execução';
                        td.onclick = () => openModalExecutar(
                            ctrl.vencimento_id,
                            `${aeronave.matricula} — ${slot.nome_posicao} — ${tipoNome}`
                        );
                    }
                } else {
                    const statusCls = mapStatus(ctrl.status);
                    td.classList.add(statusCls);
                    td.innerText = formatarData(ctrl.data_vencimento);
                    td.title = `Última exec: ${ctrl.data_ultima_exec ? formatarData(ctrl.data_ultima_exec) : '---'} — Clique para atualizar`;
                    if (ctrl.vencimento_id) {
                        td.onclick = () => openModalExecutar(
                            ctrl.vencimento_id,
                            `${aeronave.matricula} — ${slot.nome_posicao} — ${tipoNome}`
                        );
                    }
                }

                tr.appendChild(td);
            }
        }

        tbody.appendChild(tr);
    }
}

function mapStatus(status) {
    if (!status) return 'status-pendente';
    switch (status.toUpperCase()) {
        case 'OK': return 'status-ok';
        case 'VENCENDO': return 'status-vencendo';
        case 'VENCIDO': return 'status-vencido';
        default: return 'status-pendente';
    }
}

function formatarData(dataStr) {
    if (!dataStr) return '---';
    const [y, m, d] = dataStr.split('-');
    return `${d}/${m}/${y}`;
}

function openModalExecutar(vencimentoId, info) {
    document.getElementById('exec-vencimento-id').value = vencimentoId;
    document.getElementById('exec-info-label').innerText = info;
    document.getElementById('exec-data-input').value = new Date().toISOString().split('T')[0];
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

    if (!id) {
        showToast('Nenhum controle selecionado.', 'error');
        return;
    }

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
