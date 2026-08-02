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

        // Reordena por criticidade operacional (INDISPONIVEL > INSPECAO > DISPONIVEL):
        // 1. Aeronaves INDISPONÍVEIS / com panes abertas (prioridade 1)
        // 2. Aeronaves em INSPEÇÃO (prioridade 2)
        // 3. Aeronaves DISPONÍVEIS sem panes (prioridade 3)
        // Desempate: quantidade de pendências desc e matrícula asc
        frotaComDados.sort((a, b) => {
            if (a.prioridade !== b.prioridade) {
                return a.prioridade - b.prioridade;
            }
            if (a.pendenciasCount !== b.pendenciasCount) {
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

            const statusUpper = (anv.status || '').toUpperCase();
            const isInspecao = statusUpper.includes('INSPEC') || statusUpper.includes('INSPEÇ');

            let countBadgeClass = 'mobile-anv-badge-count';
            if (isInspecao) {
                countBadgeClass += ' inspecao';
            } else if (pendenciasCount === 0) {
                countBadgeClass += ' zero';
            }

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
    const statusUpper = (anv.status || '').toUpperCase();

    // 1. Aeronaves INDISPONÍVEIS (status INDISPONIVEL ou INDISPONÍVEL)
    if (statusUpper.includes('INDISPONIVEL') || statusUpper.includes('INDISPONÍVEL')) {
        return 1;
    }
    // 2. Aeronaves em INSPEÇÃO (status INSPEÇÃO ou INSPECAO)
    if (statusUpper.includes('INSPEC') || statusUpper.includes('INSPEÇ')) {
        return 2;
    }
    // 3. Panes abertas fora de inspeção (se houver pendências e status não for de inspeção)
    if (pendenciasCount > 0) {
        return 1;
    }
    // 4. Aeronaves DISPONÍVEIS (status DISPONIVEL, OPERACIONAL ou outros sem pendências)
    return 3;
}
