// app/web/static/js/mobile/frota_mobile.js
// Lista de frota mobile — 1 única requisição (GET /dashboard/frota) para
// montar contadores de panes/inspeções/vencimentos de toda a frota (RF-M02).
// Revisão v2: busca, cartões de estatística e pílulas de filtro — tudo
// client-side sobre a mesma lista já carregada, sem nova requisição.

let frotaCompleta = [];
let frotaFiltroAtivo = 'todas';
let frotaBuscaTexto = '';

const FROTA_FILTROS = [
    { chave: 'todas', label: 'Todas' },
    { chave: 'acao', label: 'Ação necessária' },
    { chave: 'inspecao', label: 'Em inspeção' },
    { chave: 'disponivel', label: 'Disponíveis' },
];

document.addEventListener('DOMContentLoaded', () => {
    carregarFrotaMobile();
});

async function carregarFrotaMobile() {
    const container = document.getElementById('container-frota-mobile');
    if (!container) return;

    try {
        const frota = await apiFetch('/dashboard/frota');
        frotaCompleta = Array.isArray(frota) ? frota : [];

        if (frotaCompleta.length === 0) {
            container.innerHTML = '<div class="mobile-loading">Nenhuma aeronave cadastrada.</div>';
            return;
        }

        montarStats(frotaCompleta);
        montarFiltros();
        inicializarBusca();
        renderizarFrotaFiltrada();
    } catch (err) {
        console.error('Erro ao carregar frota mobile:', err);
        container.innerHTML = '<div class="mobile-loading" style="color: var(--mobile-status-vencido);">Erro ao carregar frota. Verifique sua conexão.</div>';
    }
}

function classificarStatusFrota(item) {
    const statusUpper = (item.status || '').toUpperCase();
    if (statusUpper.includes('INDISPONIVEL') || statusUpper.includes('INDISPONÍVEL')) return 'indisponivel';
    if (statusUpper.includes('INSPEC') || statusUpper.includes('INSPEÇ')) return 'inspecao';
    return 'disponivel';
}

function montarStats(frota) {
    const el = document.getElementById('frota-stats');
    if (!el) return;

    const contagem = { disponivel: 0, inspecao: 0, indisponivel: 0 };
    frota.forEach((item) => { contagem[classificarStatusFrota(item)] += 1; });

    el.innerHTML = `
        <div class="mobile-stat mobile-stat--ok"><b>${contagem.disponivel}</b><span>Disponíveis</span></div>
        <div class="mobile-stat mobile-stat--warn"><b>${contagem.inspecao}</b><span>Em inspeção</span></div>
        <div class="mobile-stat mobile-stat--danger"><b>${contagem.indisponivel}</b><span>Indisponível</span></div>
    `;
    el.hidden = false;
}

function montarFiltros() {
    const el = document.getElementById('frota-filtros');
    if (!el) return;

    el.innerHTML = '';
    FROTA_FILTROS.forEach((f) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'mobile-filter-pill' + (f.chave === frotaFiltroAtivo ? ' active' : '');
        btn.textContent = f.label;
        btn.addEventListener('click', () => {
            frotaFiltroAtivo = f.chave;
            el.querySelectorAll('.mobile-filter-pill').forEach((b) => b.classList.remove('active'));
            btn.classList.add('active');
            renderizarFrotaFiltrada();
        });
        el.appendChild(btn);
    });
    el.hidden = false;
}

function inicializarBusca() {
    const input = document.getElementById('frota-busca-input');
    if (!input) return;
    input.addEventListener('input', () => {
        frotaBuscaTexto = input.value.trim().toLowerCase();
        renderizarFrotaFiltrada();
    });
}

function aeronaveCorrespondeFiltro(item) {
    if (frotaFiltroAtivo === 'todas') return true;
    if (frotaFiltroAtivo === 'acao') return classificarStatusFrota(item) === 'indisponivel' || totalPendencias(item) > 0;
    if (frotaFiltroAtivo === 'inspecao') return classificarStatusFrota(item) === 'inspecao';
    if (frotaFiltroAtivo === 'disponivel') return classificarStatusFrota(item) === 'disponivel';
    return true;
}

function aeronaveCorrespondeBusca(item) {
    if (!frotaBuscaTexto) return true;
    return (item.matricula || '').toLowerCase().includes(frotaBuscaTexto);
}

function renderizarFrotaFiltrada() {
    const container = document.getElementById('container-frota-mobile');
    if (!container) return;

    const filtrada = frotaCompleta.filter((item) => aeronaveCorrespondeFiltro(item) && aeronaveCorrespondeBusca(item));

    if (filtrada.length === 0) {
        container.innerHTML = '<div class="mobile-loading">Nenhuma aeronave corresponde à busca/filtro.</div>';
        return;
    }

    const frotaOrdenada = [...filtrada].sort((a, b) => {
        const prioA = calcularPrioridadeOperacional(a);
        const prioB = calcularPrioridadeOperacional(b);
        if (prioA !== prioB) return prioA - prioB;

        const pendA = totalPendencias(a);
        const pendB = totalPendencias(b);
        if (pendA !== pendB) return pendB - pendA;

        return (a.matricula || '').localeCompare(b.matricula || '', undefined, { numeric: true });
    });

    container.innerHTML = '';
    for (const item of frotaOrdenada) {
        container.appendChild(montarCardAeronave(item));
    }
}

const FROTA_STRIPE_COR = {
    indisponivel: 'var(--mobile-status-vencido)',
    inspecao: 'var(--mobile-status-vencendo)',
    disponivel: 'var(--mobile-status-ok)',
};

function montarCardAeronave(item) {
    const card = document.createElement('a');
    card.href = `/m/aeronave/${item.aeronave_id}`;
    card.className = 'mobile-anv-card';
    card.setAttribute('data-aeronave-id', item.aeronave_id);
    card.style.borderLeftColor = FROTA_STRIPE_COR[classificarStatusFrota(item)];

    // RF-M04: só os 4 últimos dígitos da matrícula na camada de apresentação
    // mobile — o valor completo (FAB-XXXX) continua intacto no backend/API.
    const matriculaAbreviada = abreviarMatricula(item.matricula);

    const badges = [];
    if (item.panes_abertas > 0) {
        badges.push(`<span class="mobile-anv-badge-count">${item.panes_abertas} pane(s)</span>`);
    }
    if (item.vencimentos_vencidos > 0) {
        badges.push(`<span class="mobile-anv-badge-count">${item.vencimentos_vencidos} venc. vencido(s)</span>`);
    }
    if (item.vencimentos_vencendo > 0) {
        badges.push(`<span class="mobile-anv-badge-count inspecao">${item.vencimentos_vencendo} venc. vencendo</span>`);
    }
    if (item.inspecoes_ativas > 0) {
        badges.push(`<span class="mobile-anv-badge-count inspecao">${item.tarefas_pendentes} tarefa(s)</span>`);
    }
    if (badges.length === 0) {
        badges.push('<span class="mobile-anv-badge-count zero">Tudo em dia</span>');
    }

    card.innerHTML = `
        <div class="mobile-anv-info">
            <h3>${escapeHtml(matriculaAbreviada)}</h3>
            <p>Status: <strong>${escapeHtml(item.status)}</strong></p>
        </div>
        <div style="display:flex; flex-direction:column; align-items:flex-end; gap:0.35rem;">
            ${badges.join('')}
        </div>
    `;
    return card;
}

function abreviarMatricula(matricula) {
    if (!matricula) return '----';
    const digitos = matricula.replace(/\D/g, '');
    return digitos.length >= 4 ? digitos.slice(-4) : matricula;
}

function totalPendencias(item) {
    return (item.panes_abertas || 0) + (item.vencimentos_vencidos || 0) + (item.vencimentos_vencendo || 0);
}

const FROTA_PRIORIDADE_STATUS = { indisponivel: 1, inspecao: 2, disponivel: 3 };

function calcularPrioridadeOperacional(item) {
    // Ordenação de criticidade operacional estrita por status: INDISPONÍVEL
    // sempre na frente de tudo, depois EM INSPEÇÃO, depois DISPONÍVEL — uma
    // pendência (pane/vencimento) isolada não deve furar a fila à frente de
    // uma aeronave indisponível ou em inspeção; ela só desempata dentro do
    // mesmo status (ver abaixo).
    return FROTA_PRIORIDADE_STATUS[classificarStatusFrota(item)];
}
