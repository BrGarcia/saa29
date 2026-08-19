// app/web/static/js/mobile/frota_mobile.js
// Lista de frota mobile — 1 única requisição (GET /dashboard/frota) para
// montar contadores de panes/inspeções/vencimentos de toda a frota (RF-M02).

document.addEventListener('DOMContentLoaded', () => {
    carregarFrotaMobile();
});

async function carregarFrotaMobile() {
    const container = document.getElementById('container-frota-mobile');
    if (!container) return;

    try {
        const frota = await apiFetch('/dashboard/frota');

        if (!frota || frota.length === 0) {
            container.innerHTML = '<div class="mobile-loading">Nenhuma aeronave cadastrada.</div>';
            return;
        }

        const frotaOrdenada = [...frota].sort((a, b) => {
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
    } catch (err) {
        console.error('Erro ao carregar frota mobile:', err);
        container.innerHTML = '<div class="mobile-loading" style="color: var(--mobile-danger);">Erro ao carregar frota. Verifique sua conexão.</div>';
    }
}

function montarCardAeronave(item) {
    const card = document.createElement('a');
    card.href = `/m/aeronave/${item.aeronave_id}`;
    card.className = 'mobile-anv-card';
    card.setAttribute('data-aeronave-id', item.aeronave_id);

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

function calcularPrioridadeOperacional(item) {
    const statusUpper = (item.status || '').toUpperCase();

    // Ordenação de criticidade operacional: INDISPONIVEL/pendência > INSPECAO > DISPONIVEL
    if (statusUpper.includes('INDISPONIVEL') || statusUpper.includes('INDISPONÍVEL')) {
        return 1;
    }
    if (totalPendencias(item) > 0) {
        return 1;
    }
    if (statusUpper.includes('INSPEC') || statusUpper.includes('INSPEÇ')) {
        return 2;
    }
    return 3;
}
