// app/web/static/js/mobile/tarefas_mobile.js
// Lógica de listagem e baixa/conclusão de tarefas/panes em 1 toque no celular

let aeronaveIdAtual = null;

document.addEventListener('DOMContentLoaded', () => {
    const contextEl = document.getElementById('context-aeronave-mobile');
    if (contextEl) {
        aeronaveIdAtual = contextEl.getAttribute('data-aeronave-id');
        carregarTarefasAeronave(aeronaveIdAtual);
    }
});

async function carregarTarefasAeronave(anvId) {
    const container = document.getElementById('container-tarefas-mobile');
    const anvTitleEl = document.getElementById('anv-title-mobile');
    const anvBadgeEl = document.getElementById('anv-status-badge');

    if (!container || !anvId) return;

    try {
        // Carrega dados da ANV via apiFetch (Garante Accept: application/json e cookie credentials)
        try {
            const anv = await apiFetch(`/aeronaves/${anvId}`);
            if (anv && anv.matricula) {
                if (anvTitleEl) anvTitleEl.textContent = `A-29 ${anv.matricula}`;
                if (anvBadgeEl) anvBadgeEl.textContent = anv.status;
            }
        } catch (e) {
            console.warn("Falha ao carregar detalhes da ANV:", e);
        }

        // Carrega Panes Abertas da ANV via apiFetch
        let panes = [];
        try {
            const resPanes = await apiFetch(`/panes/?aeronave_id=${anvId}&status=ABERTA`);
            panes = Array.isArray(resPanes) ? resPanes : [];
        } catch (e) {
            console.warn("Falha ao buscar panes da ANV:", e);
        }

        container.innerHTML = '';

        if (!panes || panes.length === 0) {
            container.innerHTML = `
                <div style="background: var(--mobile-card-bg); padding: 1.5rem; border-radius: 12px; text-align: center; border: 1px solid var(--mobile-card-border);">
                    <h3 style="margin: 0 0 0.5rem 0; color: var(--mobile-success-bright);">Tudo em Dia!</h3>
                    <p style="margin: 0; color: var(--mobile-text-muted); font-size: 0.9rem;">Nenhuma pane ou tarefa pendente para esta aeronave no momento.</p>
                </div>
            `;
            return;
        }

        // Renderiza cada pane como card de ação rápida
        panes.forEach(pane => {
            const card = document.createElement('div');
            card.className = 'mobile-task-card';
            card.style.cssText = 'background: var(--mobile-card-bg); border: 1px solid var(--mobile-card-border); border-radius: 12px; padding: 1rem; margin-bottom: 0.75rem;';

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                    <span style="background: var(--mobile-danger); color: #fff; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px;">PANE ABERTA</span>
                    <span style="font-size: 0.8rem; color: var(--mobile-text-muted);">${new Date(pane.data_abertura).toLocaleDateString()}</span>
                </div>
                <h4 style="margin: 0 0 0.5rem 0; font-size: 1.1rem; color: #fff;">${escapeHtml(pane.descricao || 'Pane de Linha de Voo')}</h4>
                <p style="margin: 0 0 1rem 0; font-size: 0.85rem; color: var(--mobile-text-muted);">Registrado por: <strong>${escapeHtml(pane.aberto_por_trigrama || 'MANT')}</strong></p>
                
                <div style="display: flex; gap: 0.5rem;">
                    <button class="btn-mobile-action btn-mobile-success btn-concluir-pane" data-pane-id="${pane.id}">
                        🟢 CONCLUIR PANE (1 TOQUE)
                    </button>
                </div>
            `;

            container.appendChild(card);
        });

        // Vincula ouvintes de evento nos botões de conclusão (Conformidade CSP)
        container.querySelectorAll('.btn-concluir-pane').forEach(btn => {
            btn.addEventListener('click', handleConcluirPaneMobile);
        });

    } catch (err) {
        console.error('Erro ao carregar tarefas da aeronave mobile:', err);
        container.innerHTML = '<div class="mobile-loading" style="color: var(--mobile-danger);">Erro ao carregar pendências da aeronave.</div>';
    }
}

async function handleConcluirPaneMobile(event) {
    const btn = event.currentTarget;
    const paneId = btn.getAttribute('data-pane-id');
    if (!paneId) return;

    btn.disabled = true;
    btn.textContent = 'Concluindo...';

    try {
        await apiFetch(`/panes/${paneId}/concluir`, {
            method: 'POST',
            body: { observacao_conclusao: "Concluído via SAA29 Mobile (1 toque)" }
        });

        showToast('Pane concluída com sucesso!', 'success');
        // Recarrega lista
        if (aeronaveIdAtual) carregarTarefasAeronave(aeronaveIdAtual);

    } catch (err) {
        console.error('Erro ao concluir pane no celular:', err);
        showToast(err.message || 'Erro ao concluir pane.', 'error');
        btn.disabled = false;
        btn.textContent = '🟢 CONCLUIR PANE (1 TOQUE)';
    }
}

function getCsrfTokenFromCookie() {
    const match = document.cookie.match(new RegExp('(^| )fastapi-csrf-token=([^;]+)'));
    return match ? match[2] : '';
}
