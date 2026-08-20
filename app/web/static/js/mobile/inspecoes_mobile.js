// app/web/static/js/mobile/inspecoes_mobile.js
// Módulo Inspeções do SAA29 Mobile (Etapa 4): aba do hub + checklist com
// execução de tarefa (folha de ação) e tarefa avulsa.

// ============================================================================
// Aba "Inspeções" do hub da aeronave
// ============================================================================

window.carregarAbaInspecoes = async function carregarAbaInspecoes(aeronaveId, container) {
    container.innerHTML = '<div class="mobile-loading">Buscando inspeções da aeronave...</div>';

    try {
        // Endpoint aceita um único `status` por chamada — duas chamadas em
        // paralelo custam menos rede do que buscar tudo e filtrar no cliente.
        const [abertas, emAndamento] = await Promise.all([
            apiFetch(`/inspecoes/?aeronave_id=${aeronaveId}&status=ABERTA`),
            apiFetch(`/inspecoes/?aeronave_id=${aeronaveId}&status=EM_ANDAMENTO`),
        ]);
        const inspecoes = [...(Array.isArray(abertas) ? abertas : []), ...(Array.isArray(emAndamento) ? emAndamento : [])];
        renderizarListaInspecoes(inspecoes, container);
    } catch (err) {
        console.error('Erro ao carregar inspeções da aeronave:', err);
        container.innerHTML = '<div class="mobile-loading" style="color: var(--mobile-status-vencido);">Erro ao carregar inspeções.</div>';
    }
};

function classificarDpe(dataFimPrevista) {
    if (!dataFimPrevista) return { tag: null, tone: null };
    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);
    const dpe = new Date(dataFimPrevista);
    dpe.setHours(0, 0, 0, 0);
    const diffDias = Math.round((dpe - hoje) / 86400000);

    if (diffDias < 0) return { tag: `DPE atrasada ${Math.abs(diffDias)}d`, tone: 'vencido' };
    if (diffDias === 0) return { tag: 'DPE hoje', tone: 'vencendo' };
    if (diffDias <= 7) return { tag: `DPE em ${diffDias}d`, tone: 'vencendo' };
    return { tag: `DPE ${dpe.toLocaleDateString()}`, tone: 'ok' };
}

function renderizarListaInspecoes(inspecoes, container) {
    container.innerHTML = '';

    if (inspecoes.length === 0) {
        container.innerHTML = `
            <div class="mobile-card" style="text-align:center;">
                <p style="margin:0; color: var(--mobile-status-ok); font-weight:700;">Nenhuma inspeção ativa.</p>
                <p style="margin:0.35rem 0 0; color: var(--mobile-text-muted); font-size:0.85rem;">Esta aeronave não tem inspeção aberta ou em andamento no momento.</p>
            </div>
        `;
        return;
    }

    const lista = document.createElement('div');
    lista.className = 'mobile-task-list';
    inspecoes.forEach((insp) => lista.appendChild(montarCardInspecao(insp)));
    container.appendChild(lista);
}

function montarCardInspecao(insp) {
    const card = document.createElement('a');
    card.href = `/m/inspecao/${insp.id}`;
    card.className = 'mobile-task-card';

    const nomeTipos = (insp.tipos_aplicados || []).map((t) => t.codigo || t.nome).join(' + ') || 'Inspeção';
    const dpe = classificarDpe(insp.data_fim_prevista);

    card.innerHTML = `
        <div class="mobile-task-card-top">
            <span class="mobile-pill">${escapeHtml(insp.status)} · ${insp.progresso_percentual}%</span>
            ${dpe.tag ? `<span class="badge-status status-${dpe.tone}">${escapeHtml(dpe.tag)}</span>` : ''}
        </div>
        <p class="mobile-task-card-title">${escapeHtml(nomeTipos)}</p>
        <p class="mobile-task-card-meta">${insp.tarefas_concluidas}/${insp.total_tarefas} tarefas${insp.aberto_por_trigrama ? ` · aberta por ${escapeHtml(insp.aberto_por_trigrama)}` : ''}</p>
    `;
    return card;
}

// ============================================================================
// Checklist — /m/inspecao/{id}
// ============================================================================

let inspecaoIdAtual = null;
let inspecaoAtual = null;
let filtroTarefaAtivo = 'pendentes';
let tarefaSheetAtiva = null;

document.addEventListener('DOMContentLoaded', () => {
    const contexto = document.getElementById('context-checklist');
    if (!contexto) return;
    inspecaoIdAtual = contexto.getAttribute('data-inspecao-id');
    inicializarChecklist();
});

async function inicializarChecklist() {
    document.querySelectorAll('.mobile-tab-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            filtroTarefaAtivo = btn.getAttribute('data-filtro');
            document.querySelectorAll('.mobile-tab-btn').forEach((b) => b.classList.toggle('active', b === btn));
            renderizarTarefas();
        });
    });

    const btnExtra = document.getElementById('btn-checklist-tarefa-extra');
    const formExtraWrap = document.getElementById('checklist-form-extra');
    if (btnExtra && formExtraWrap) {
        btnExtra.addEventListener('click', () => {
            formExtraWrap.hidden = !formExtraWrap.hidden;
        });
    }

    const formExtra = document.getElementById('form-tarefa-extra');
    if (formExtra) formExtra.addEventListener('submit', handleAdicionarTarefaExtra);

    document.querySelectorAll('#checklist-sheet .mobile-sheet-btn').forEach((btn) => {
        btn.addEventListener('click', () => handleDefinirStatusTarefa(btn.getAttribute('data-status')));
    });
    const btnFecharSheet = document.getElementById('btn-sheet-fechar');
    const backdrop = document.getElementById('checklist-sheet-backdrop');
    if (btnFecharSheet) btnFecharSheet.addEventListener('click', fecharSheet);
    if (backdrop) backdrop.addEventListener('click', fecharSheet);

    await carregarInspecao();
}

async function carregarInspecao() {
    try {
        inspecaoAtual = await apiFetch(`/inspecoes/${inspecaoIdAtual}`);
        renderizarCabecalhoInspecao();
        renderizarTarefas();
    } catch (err) {
        console.error('Erro ao carregar inspeção:', err);
        showToast('Erro ao carregar a inspeção.', 'error');
    }
}

function classeStatusDpe(tone) {
    return { vencido: 'status-vencido', vencendo: 'status-vencendo', ok: 'status-ok' }[tone] || '';
}

function renderizarCabecalhoInspecao() {
    const insp = inspecaoAtual;
    if (!insp) return;

    const linkVoltar = document.getElementById('checklist-voltar');
    if (linkVoltar && insp.aeronave_id) {
        linkVoltar.href = `/m/aeronave/${insp.aeronave_id}`;
        linkVoltar.textContent = `← ${insp.aeronave && insp.aeronave.matricula ? abreviarMatriculaChecklist(insp.aeronave.matricula) : 'Voltar'}`;
    }

    const tituloEl = document.getElementById('checklist-titulo');
    if (tituloEl) {
        const nomeTipos = (insp.tipos_aplicados || []).map((t) => t.codigo || t.nome).join(' + ');
        tituloEl.textContent = nomeTipos || 'Inspeção';
    }

    const dpeBadge = document.getElementById('checklist-dpe-badge');
    if (dpeBadge) {
        const emAndamento = insp.status === 'ABERTA' || insp.status === 'EM_ANDAMENTO';
        const dpe = classificarDpe(insp.data_fim_prevista);
        if (emAndamento && dpe.tag) {
            dpeBadge.textContent = dpe.tag;
            dpeBadge.className = `badge-status ${classeStatusDpe(dpe.tone)}`;
            dpeBadge.hidden = false;
        } else {
            dpeBadge.hidden = true;
        }
    }

    renderizarAnelProgresso();
}

function renderizarAnelProgresso() {
    const tarefas = (inspecaoAtual && inspecaoAtual.tarefas) || [];
    const total = tarefas.length;
    const concluidas = tarefas.filter((t) => t.status === 'CONCLUIDA').length;
    const pct = total ? concluidas / total : 0;

    const ringEl = document.getElementById('checklist-ring');
    if (ringEl) {
        const r = 24, circ = 2 * Math.PI * r;
        const offset = circ * (1 - pct);
        ringEl.innerHTML = `
            <svg width="56" height="56" viewBox="0 0 56 56">
                <circle cx="28" cy="28" r="${r}" fill="none" stroke="var(--mobile-card-border)" stroke-width="5"></circle>
                <circle cx="28" cy="28" r="${r}" fill="none" stroke="var(--mobile-status-ok)" stroke-width="5" stroke-linecap="round" stroke-dasharray="${circ.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}"></circle>
            </svg>
            <span class="mobile-ring__pct">${Math.round(pct * 100)}%</span>
        `;
    }

    const textoEl = document.getElementById('checklist-progresso-texto');
    if (textoEl) {
        const responsaveis = [...new Set(tarefas.filter((t) => t.executado_por && t.executado_por.trigrama).map((t) => t.executado_por.trigrama))];
        textoEl.textContent = `${concluidas} de ${total} tarefas` + (responsaveis.length ? ` · ${responsaveis.join(', ')}` : '');
    }
}

function abreviarMatriculaChecklist(matricula) {
    if (!matricula) return '----';
    const digitos = matricula.replace(/\D/g, '');
    return digitos.length >= 4 ? digitos.slice(-4) : matricula;
}

const TAREFA_ICONE = {
    CONCLUIDA: { classe: 'is-concluida', char: '✓' },
    'N/A': { classe: 'is-na', char: '—' },
    PENDENTE: { classe: 'is-pendente', char: '' },
};

function renderizarTarefas() {
    const container = document.getElementById('checklist-lista');
    if (!container || !inspecaoAtual) return;

    const todas = inspecaoAtual.tarefas || [];
    const tarefas = filtroTarefaAtivo === 'pendentes' ? todas.filter((t) => t.status === 'PENDENTE') : todas;

    container.innerHTML = '';

    if (tarefas.length === 0) {
        container.innerHTML = `<div class="mobile-loading">${filtroTarefaAtivo === 'pendentes' ? 'Nenhuma tarefa pendente.' : 'Nenhuma tarefa cadastrada.'}</div>`;
        return;
    }

    tarefas.forEach((tarefa) => container.appendChild(montarLinhaTarefa(tarefa)));
}

function montarLinhaTarefa(tarefa) {
    const row = document.createElement('div');
    row.className = 'mobile-task-row';
    row.setAttribute('data-tarefa-id', tarefa.id);

    const icone = TAREFA_ICONE[tarefa.status] || TAREFA_ICONE.PENDENTE;
    const metaPartes = [];
    if (tarefa.status === 'CONCLUIDA' && tarefa.executado_por) {
        metaPartes.push(`CONCLUÍDA · ${tarefa.executado_por.trigrama || '—'}`);
    } else if (tarefa.status === 'N/A') {
        metaPartes.push('N/A');
    } else {
        metaPartes.push('PENDENTE');
    }
    if (tarefa.observacao_execucao) metaPartes.push(tarefa.observacao_execucao);
    else if (!tarefa.obrigatoria) metaPartes.push('não obrigatória');

    row.innerHTML = `
        <span class="mobile-task-row__icon ${icone.classe}">${icone.char}</span>
        <div class="mobile-task-row__body">
            <p class="mobile-task-row__title${tarefa.status === 'CONCLUIDA' ? ' is-done' : ''}">${escapeHtml(tarefa.titulo)}</p>
            <p class="mobile-task-row__meta">${escapeHtml(metaPartes.join(' · '))}</p>
        </div>
    `;
    row.addEventListener('click', () => abrirSheet(tarefa));
    return row;
}

function abrirSheet(tarefa) {
    tarefaSheetAtiva = tarefa;

    const titulo = document.getElementById('sheet-tarefa-titulo');
    const meta = document.getElementById('sheet-tarefa-meta');
    const observacao = document.getElementById('sheet-observacao');
    if (titulo) titulo.textContent = tarefa.titulo;
    if (meta) meta.textContent = [tarefa.sistema, tarefa.manual, tarefa.codigo_tarefa].filter(Boolean).join(' · ') || 'Sem referência cadastrada';
    if (observacao) observacao.value = tarefa.observacao_execucao || '';

    document.querySelectorAll('#checklist-sheet .mobile-sheet-btn').forEach((btn) => {
        const status = btn.getAttribute('data-status');
        const classeAtiva = status === 'N/A' ? 'is-off' : status === 'PENDENTE' ? 'is-pendente' : 'is-concluida';
        btn.classList.toggle(classeAtiva, status === tarefa.status);
    });

    document.getElementById('checklist-sheet-backdrop').hidden = false;
    document.getElementById('checklist-sheet').hidden = false;
}

function fecharSheet() {
    tarefaSheetAtiva = null;
    document.getElementById('checklist-sheet-backdrop').hidden = true;
    document.getElementById('checklist-sheet').hidden = true;
}

async function handleDefinirStatusTarefa(novoStatus) {
    if (!tarefaSheetAtiva) return;
    const observacao = document.getElementById('sheet-observacao');

    try {
        await apiFetch(`/inspecoes/tarefas/${tarefaSheetAtiva.id}`, {
            method: 'PUT',
            body: {
                status: novoStatus,
                observacao_execucao: observacao ? (observacao.value.trim() || null) : null,
            },
        });
        showToast('Tarefa atualizada.', 'success');
        fecharSheet();
        await carregarInspecao();
    } catch (err) {
        console.error('Erro ao atualizar tarefa:', err);
    }
}

async function handleAdicionarTarefaExtra(ev) {
    ev.preventDefault();
    const btn = document.getElementById('btn-tarefa-extra-salvar');
    if (btn) { btn.disabled = true; btn.textContent = 'Adicionando...'; }

    try {
        const titulo = document.getElementById('extra-titulo').value.trim();
        const payload = {
            titulo,
            sistema: valorOpcional('extra-sistema'),
            manual: valorOpcional('extra-manual'),
            codigo_tarefa: valorOpcional('extra-codigo'),
            descricao: valorOpcional('extra-descricao'),
            obrigatoria: document.getElementById('extra-obrigatoria').checked,
        };
        await apiFetch(`/inspecoes/${inspecaoIdAtual}/tarefas`, { method: 'POST', body: payload });
        showToast('Tarefa adicionada.', 'success');
        document.getElementById('form-tarefa-extra').reset();
        document.getElementById('checklist-form-extra').hidden = true;
        filtroTarefaAtivo = 'todas';
        document.querySelectorAll('.mobile-tab-btn').forEach((b) => b.classList.toggle('active', b.getAttribute('data-filtro') === 'todas'));
        await carregarInspecao();
    } catch (err) {
        console.error('Erro ao adicionar tarefa avulsa:', err);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Adicionar tarefa'; }
    }
}

function valorOpcional(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    const v = el.value.trim();
    return v || null;
}
