// app/web/static/js/mobile/frota_mobile.js
// Lógica da lista de frota mobile com contagem de pendências por ANV

document.addEventListener('DOMContentLoaded', () => {
    carregarFrotaMobile();
});

async function carregarFrotaMobile() {
    const container = document.getElementById('container-frota-mobile');
    if (!container) return;

    try {
        const aeronaves = await apiFetch('/aeronaves/');
        
        if (!aeronaves || aeronaves.length === 0) {
            container.innerHTML = '<div class="mobile-loading">Nenhuma aeronave cadastrada.</div>';
            return;
        }

        container.innerHTML = '';
        // Busca a contagem de pendências de panes para cada ANV em paralelo
        const frotaComDados = await Promise.all(
            aeronaves.map(async (anv) => {
                let pendenciasCount = 0;
                try {
                    const panes = await apiFetch(`/panes/?aeronave_id=${anv.id}&status=ABERTA`);
                    pendenciasCount = Array.isArray(panes) ? panes.length : 0;
                } catch (e) {
                    console.warn('Não foi possível obter panes da ANV:', anv.matricula);
                }
                return {
                    anv,
                    pendenciasCount,
                    prioridade: calcularPrioridadeOperacional(anv, pendenciasCount)
                };
            })
        );

        // Reordena por criticidade operacional:
        // 1. Aeronaves com panes abertas (prioridade 1)
        // 2. Aeronaves em inspeção (prioridade 2)
        // 3. Aeronaves disponíveis sem panes (prioridade 3)
        // Desempate: quantidade de panes desc (se P1) e matrícula asc
        frotaComDados.sort((a, b) => {
            if (a.prioridade !== b.prioridade) {
                return a.prioridade - b.prioridade;
            }
            if (a.prioridade === 1 && a.pendenciasCount !== b.pendenciasCount) {
                return b.pendenciasCount - a.pendenciasCount;
            }
            return (a.anv.matricula || '').localeCompare(b.anv.matricula || '', undefined, { numeric: true });
        });

        for (const item of frotaComDados) {
            const { anv, pendenciasCount } = item;
            const card = document.createElement('a');
            card.href = `/m/aeronave/${anv.id}`;
            card.className = 'mobile-anv-card';
            card.setAttribute('data-aeronave-id', anv.id);

            const countBadgeClass = pendenciasCount > 0 ? 'mobile-anv-badge-count' : 'mobile-anv-badge-count zero';
            const countText = pendenciasCount > 0 ? `${pendenciasCount} Pendência(s)` : '0 Pendências';

            card.innerHTML = `
                <div class="mobile-anv-info">
                    <h3>A-29 ${escapeHtml(anv.matricula)}</h3>
                    <p>Status: <strong>${escapeHtml(anv.status)}</strong></p>
                </div>
                <div class="${countBadgeClass}">
                    ${countText}
                </div>
            `;
            container.appendChild(card);
        }
    } catch (err) {
        console.error('Erro ao carregar frota mobile:', err);
        container.innerHTML = '<div class="mobile-loading" style="color: var(--mobile-danger);">Erro ao carregar frota. Verifique sua conexão.</div>';
    }
}

function calcularPrioridadeOperacional(anv, pendenciasCount) {
    // 1. aeronaves com panes abertas
    if (pendenciasCount > 0) {
        return 1;
    }
    // 2. aeronaves em inspeção
    const statusUpper = (anv.status || '').toUpperCase();
    if (statusUpper === 'INSPEÇÃO' || statusUpper === 'INSPECAO') {
        return 2;
    }
    // 3. aeronaves disponíveis sem panes
    return 3;
}
