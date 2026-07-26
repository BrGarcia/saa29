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
        for (const anv of aeronaves) {
            // Busca contagem de pendências de panes para esta ANV
            let pendenciasCount = 0;
            try {
                const panes = await apiFetch(`/panes/?aeronave_id=${anv.id}&status=ABERTA`);
                pendenciasCount = Array.isArray(panes) ? panes.length : 0;
            } catch (e) {
                console.warn('Não foi possível obter panes da ANV:', anv.matricula);
            }

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
