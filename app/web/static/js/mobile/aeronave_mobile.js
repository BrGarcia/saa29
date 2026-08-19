// app/web/static/js/mobile/aeronave_mobile.js
// Hub da aeronave: cabeçalho + controle das 4 abas (Panes, Inspeções,
// Vencimentos, Inventário), cada uma carregada sob demanda na primeira
// abertura (RF-M10).

let aeronaveIdAtual = null;

document.addEventListener('DOMContentLoaded', () => {
    const contextEl = document.getElementById('context-aeronave-mobile');
    if (!contextEl) return;

    aeronaveIdAtual = contextEl.getAttribute('data-aeronave-id');
    carregarCabecalhoAeronave(aeronaveIdAtual);
    inicializarAbas();
});

async function carregarCabecalhoAeronave(anvId) {
    const tituloEl = document.getElementById('anv-title-mobile');
    const badgeEl = document.getElementById('anv-status-badge');
    if (!anvId) return;

    try {
        const anv = await apiFetch(`/aeronaves/${anvId}`);
        if (anv && anv.matricula) {
            if (tituloEl) tituloEl.textContent = abreviarMatriculaAeronave(anv.matricula);
            if (badgeEl) {
                badgeEl.textContent = anv.status;
                badgeEl.className = `badge-status ${classeStatusAeronave(anv.status)}`;
            }
        }
    } catch (e) {
        console.warn('Falha ao carregar cabeçalho da aeronave:', e);
    }
}

function abreviarMatriculaAeronave(matricula) {
    if (!matricula) return '----';
    const digitos = matricula.replace(/\D/g, '');
    return digitos.length >= 4 ? digitos.slice(-4) : matricula;
}

function classeStatusAeronave(status) {
    const s = (status || '').toUpperCase();
    if (s.includes('INDISPON')) return 'status-indisponivel';
    if (s.includes('INSPEC') || s.includes('INSPEÇ')) return 'status-inspecao';
    if (s.includes('DISPONIVEL') || s.includes('DISPONÍVEL') || s.includes('OPERACIONAL')) return 'status-disponivel';
    return 'status-desinstalado';
}

function inicializarAbas() {
    const botoes = document.querySelectorAll('.mobile-tab-btn');
    botoes.forEach((btn) => {
        btn.addEventListener('click', () => ativarAba(btn.getAttribute('data-tab')));
    });

    // A aba Panes abre por padrão (é o que costuma motivar a indisponibilidade).
    ativarAba('panes');
}

function ativarAba(nomeAba) {
    document.querySelectorAll('.mobile-tab-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === nomeAba);
    });
    document.querySelectorAll('.mobile-tab-panel').forEach((panel) => {
        panel.hidden = panel.id !== `tab-${nomeAba}`;
    });

    const painel = document.getElementById(`tab-${nomeAba}`);
    if (!painel || painel.dataset.loaded === 'true') return;
    painel.dataset.loaded = 'true';
    carregarConteudoAba(nomeAba, painel);
}

// Mapa de carregadores por aba — cada módulo (panes_mobile.js hoje;
// inspecoes/vencimentos/inventario_mobile.js em etapas futuras) expõe sua
// própria função `carregarAba<X>(aeronaveId, container)` no escopo global.
const CARREGADORES_ABA = {
    panes: () => window.carregarAbaPanes,
    inspecoes: () => window.carregarAbaInspecoes,
    vencimentos: () => window.carregarAbaVencimentos,
    inventario: () => window.carregarAbaInventario,
};

function carregarConteudoAba(nomeAba, container) {
    const obterCarregador = CARREGADORES_ABA[nomeAba];
    const carregador = obterCarregador ? obterCarregador() : null;

    if (typeof carregador === 'function') {
        carregador(aeronaveIdAtual, container);
        return;
    }

    container.innerHTML = '<div class="mobile-loading">Esta aba ainda está em desenvolvimento.</div>';
}
