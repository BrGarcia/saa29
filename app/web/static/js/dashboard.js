/**
 * app/web/static/js/dashboard.js
 * Lógica de controle para o Dashboard Central.
 * Consome o endpoint consolidado /dashboard/resumo.
 */

document.addEventListener('DOMContentLoaded', async () => {
    console.log("Dashboard inicializado.");
    await carregarDashboard();
    
    // Auto-refresh a cada 5 minutos
    setInterval(carregarDashboard, 5 * 60 * 1000);

    // Event Listeners para navegação e ações
    configurarEventos();
});

async function carregarDashboard() {
    try {
        const data = await apiFetch('/dashboard/resumo');
        
        if (!data) return;

        renderPanes(data.panes);
        renderVencimentos(data.vencimentos);
        renderInspecoes(data.inspecoes_ativas);
        renderInventario(data.movimentacoes_recentes);
        renderFrota(data.frota);

    } catch (error) {
        console.error("Erro ao carregar dashboard:", error);
    }
}

function configurarEventos() {
    // Botão Registrar Pane
    const btnRegistrar = document.getElementById('btn-registrar-pane');
    if (btnRegistrar) {
        btnRegistrar.addEventListener('click', (e) => {
            e.stopPropagation(); // Evita clique no card
            window.location.href = '/panes?action=new';
        });
    }

    // Cards Clicáveis (Navegação Direta)
    document.getElementById('stat-panes-abertas')?.addEventListener('click', () => window.location.href = '/panes');
    document.getElementById('stat-panes-resolvidas')?.addEventListener('click', () => window.location.href = '/panes');
    document.getElementById('card-vencimentos')?.addEventListener('click', () => window.location.href = '/vencimentos');
    document.getElementById('card-frota')?.addEventListener('click', () => window.location.href = '/frota');
}

/** 
 * Renderizadores 
 */

function renderPanes(data) {
    const valAbertas = document.getElementById('val-panes-abertas');
    const valResolvidas = document.getElementById('val-panes-resolvidas');
    const listContainer = document.getElementById('panes-criticas-list');

    // Remove skeleton-text classes
    if (valAbertas) {
        valAbertas.classList.remove('skeleton-text');
        valAbertas.textContent = data.total_abertas;
    }
    if (valResolvidas) {
        valResolvidas.classList.remove('skeleton-text');
        valResolvidas.textContent = data.total_resolvidas_mes;
    }

    if (!listContainer) return;

    if (!data.panes_criticas || data.panes_criticas.length === 0) {
        listContainer.innerHTML = '<div class="loading-placeholder">Nenhuma pane aberta pendente. Operação limpa.</div>';
        return;
    }

    listContainer.innerHTML = data.panes_criticas.map(pane => `
        <a href="/panes/${pane.id}/detalhes" class="list-item">
            <div class="item-main">
                <span class="item-tag">${escapeHtml(pane.matricula)}</span>
                <span class="item-desc">${escapeHtml(pane.sistema || 'Geral')}</span>
            </div>
            <span class="item-meta">${formatarDataRelativa(pane.data_abertura)}</span>
        </a>
    `).join('');
}

function renderVencimentos(data) {
    const elOk = document.getElementById('val-venc-ok');
    const elWarning = document.getElementById('val-venc-avencer');
    const elDanger = document.getElementById('val-venc-vencido');
    const elProrrogado = document.getElementById('val-venc-prorrogado');

    [elOk, elWarning, elDanger, elProrrogado].forEach(el => {
        if (el) {
            el.classList.remove('skeleton-text');
        }
    });

    if(elOk) elOk.textContent = data.ok || 0;
    if(elWarning) elWarning.textContent = data.vencendo || 0;
    if(elDanger) elDanger.textContent = data.vencido || 0;
    if(elProrrogado) elProrrogado.textContent = data.prorrogado || 0;
}

function renderInspecoes(inspecoes) {
    const list = document.getElementById('inspecoes-list');
    if (!list) return;

    if (!inspecoes || inspecoes.length === 0) {
        list.innerHTML = '<div class="loading-placeholder">Sem inspeções em andamento.</div>';
        return;
    }

    list.innerHTML = inspecoes.map(insp => {
        const tipos = (insp.tipos && insp.tipos.length > 0) ? insp.tipos.join(' + ') : 'Inspeção';
        const color = insp.status === 'EM_ANDAMENTO' ? 'var(--status-ok)' : 'var(--status-warning)';
        return `
            <a href="/inspecoes/${insp.inspecao_id}/detalhes" class="chip">
                <span class="chip-status" style="background: ${color}"></span>
                ${escapeHtml(insp.matricula)} — ${escapeHtml(tipos)}
            </a>
        `;
    }).join('');
}

function renderInventario(movimentacoes) {
    const list = document.getElementById('movimentacoes-list');
    if (!list) return;

    if (!movimentacoes || movimentacoes.length === 0) {
        list.innerHTML = '<div class="loading-placeholder">Nenhuma movimentação recente.</div>';
        return;
    }

    list.innerHTML = movimentacoes.map(mov => `
        <div class="feed-item">
            <span class="feed-icon">📥</span>
            <div class="feed-content">
                <span class="feed-title">
                    <strong>${escapeHtml(mov.aeronave_matricula || 'Item')}</strong>: ${escapeHtml(mov.descricao)}
                </span>
                <span class="feed-date">${formatarDataSimples(mov.data)}</span>
            </div>
        </div>
    `).join('');
}

function renderFrota(data) {
    const container = document.getElementById('frota-stats');
    if (!container) return;

    if (!data.aeronaves || data.aeronaves.length === 0) {
        container.innerHTML = '<div class="loading-placeholder">Sem aeronaves na frota.</div>';
        return;
    }

    const colorMap = {
        'DISPONIVEL': 'var(--status-ok)',
        'OPERACIONAL': 'var(--primary-color)',
        'INDISPONIVEL': 'var(--status-danger)',
        'INSPEÇÃO': '#1abc9c',
        'INSPECÃO': '#1abc9c',
        'INSPECAO': '#1abc9c',
        'ESTOCADA': '#95a5a6',
        'INATIVA': '#34495e'
    };

    container.innerHTML = data.aeronaves.map(a => {
        const color = colorMap[a.status.toUpperCase()] || 'var(--bg-tertiary)';
        return `
            <div class="f-pill" style="border-left: 3px solid ${color}" title="Status: ${a.status}">
                <span class="f-pill-dot" style="background: ${color}"></span>
                ${escapeHtml(a.matricula)}
            </div>
        `;
    }).join('');
}

/**
 * Utilitários de Formatação
 */

function formatarDataRelativa(isoString) {
    if (!isoString) return "";
    const data = new Date(isoString);
    const agora = new Date();
    const diffMs = agora - data;
    const diffDias = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDias === 0) return "Hoje";
    if (diffDias === 1) return "Ontem";
    return `Há ${diffDias} dias`;
}

function formatarDataSimples(isoString) {
    if (!isoString) return "";
    const data = new Date(isoString);
    return data.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}
