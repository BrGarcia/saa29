let editingAeronaveId = null;

async function loadFrota() {
    const body = document.getElementById('frota-table-body');
    const searchInput = document.getElementById('filter-text');
    if(!body || !searchInput) return;
    
    const search = searchInput.value;

    try {
        const data = await apiFetch(`/aeronaves/?limit=100&incluir_inativas=true`);
        body.innerHTML = '';
        
        const filtered = data.filter(d => d.matricula.includes(search));

        if (filtered.length === 0) {
            body.innerHTML = `<tr><td colspan="4" style="padding: 2rem; text-align: center; color: var(--text-secondary);">Nenhuma aeronave encontrada.</td></tr>`;
            return;
        }

        filtered.forEach(acft => {
            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid var(--border-color)";
            tr.innerHTML = `
                <td style="padding: 1rem; font-weight: 600; font-size: 1.1rem; color: var(--primary-color)">${acft.matricula}</td>
                <td style="padding: 1rem;">${acft.serial_number}</td>
                <td style="padding: 1rem;">
                    <span class="badge ${mapStatusAcftBadge(acft.status)}" style="border: 1px solid rgba(255,255,255,0.1)">${acft.status}</span>
                </td>
                <td style="padding: 1rem; display: flex; gap: 0.5rem; align-items: center;">
                    <button class="btn-icon btn-ver-panes" style="color: var(--primary-color); display: flex; justify-content: center; align-items: center; cursor: pointer; background: transparent; border: none; padding: 0.25rem;" title="Ver Panes">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                    </button>
                    <button class="btn-icon btn-editar-aeronave" style="color: var(--status-warning); display: flex; justify-content: center; align-items: center; cursor: pointer; background: transparent; border: none; padding: 0.25rem;" title="Editar Aeronave">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    </button>

                </td>
            `;
            
            tr.querySelector('.btn-ver-panes').addEventListener('click', () => verPanes(acft.id));
            tr.querySelector('.btn-editar-aeronave').addEventListener('click', () => openEditarAeronave(acft));

            
            body.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
        if(body) body.innerHTML = `<tr><td colspan="4" style="padding: 2rem; text-align: center; color: var(--status-danger);">Falha ao acessar registros.</td></tr>`;
    }
}

function openModalFrota() {
    editingAeronaveId = null;
    document.querySelector("#modal-aeronave h3").innerText = "Nova Aeronave";
    document.getElementById("btnSalvarAcft").innerText = "Registrar";
    document.getElementById("statusInput").value = "DISPONIVEL";
    document.getElementById("statusInput").disabled = false;
    document.getElementById("modal-aeronave").style.display = "flex";
}

function openEditarAeronave(acft) {
    editingAeronaveId = acft.id;
    document.querySelector("#modal-aeronave h3").innerText = "Editar Aeronave";
    document.getElementById("btnSalvarAcft").innerText = "Salvar";
    document.getElementById("matriculaInput").value = acft.matricula || "";
    document.getElementById("snInput").value = acft.serial_number || "";
    document.getElementById("statusInput").value = acft.status || "DISPONIVEL";
    document.getElementById("statusInput").disabled = acft.status === "INATIVA";
    document.getElementById("modal-aeronave").style.display = "flex";
}

function closeModalFrota() {
    editingAeronaveId = null;
    document.getElementById("modal-aeronave").style.display = "none";
    document.querySelector("#modal-aeronave h3").innerText = "Nova Aeronave";
    document.getElementById("btnSalvarAcft").innerText = "Registrar";
    document.getElementById("statusInput").disabled = false;
    document.getElementById("formAeronave").reset();
}

async function criarAeronave(e) {
    e.preventDefault();
    const btn = document.getElementById("btnSalvarAcft");
    btn.disabled = true;
    
    try {
        await apiFetch(editingAeronaveId ? `/aeronaves/${editingAeronaveId}` : "/aeronaves/", {
            method: editingAeronaveId ? "PUT" : "POST",
            body: {
                matricula: document.getElementById("matriculaInput").value,
                serial_number: document.getElementById("snInput").value,
                status: document.getElementById("statusInput").value
            }
        });
        showToast(editingAeronaveId ? "Aeronave atualizada." : "Aeronave baseada no esquadrão!", "success");
        closeModalFrota();
        loadFrota();
    } catch(err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

function verPanes(aeronaveId) {
    window.location.href = `/panes?aeronave_id=${aeronaveId}`;
}

async function alternarStatusAeronave(aeronaveId, matricula, statusAtual) {
    const acao = statusAtual === "INATIVA" ? "reativar" : "desativar";
    if (!confirm(`${acao.charAt(0).toUpperCase() + acao.slice(1)} aeronave ${matricula}?`)) return;
    try {
        const aeronave = await apiFetch(`/aeronaves/${aeronaveId}/toggle-status`, { method: "POST" });
        showToast(
            aeronave.status === "INATIVA" ? "Aeronave desativada." : "Aeronave reativada.",
            "success"
        );
        loadFrota();
    } catch (e) {}
}

function mapStatusAcftBadge(status) {
    if (!status) return '';
    switch (status.toUpperCase()) {
        case 'DISPONIVEL':
        case 'OPERACIONAL': return 'badge-resolvida'; // Verde
        case 'INDISPONIVEL': return 'badge-pesquisa'; // Amarelo/Laranja
        case 'INSPEÇÃO': return 'badge-inspecao';    // Azul
        case 'ESTOCADA': return 'badge-estocada'; // Cinza
        case 'INATIVA': return 'badge-aberta';       // Vermelho
        default: return '';
    }
}

window.openModalFrota = openModalFrota;
window.closeModalFrota = closeModalFrota;
window.loadFrota = loadFrota;

document.addEventListener("DOMContentLoaded", () => {
    loadFrota();
    const form = document.getElementById('formAeronave');
    if(form) form.addEventListener('submit', criarAeronave);

    const btnSearch = document.getElementById('btn-search-frota');
    if(btnSearch) btnSearch.addEventListener('click', loadFrota);
    
    const btnNova = document.getElementById('btn-nova-aeronave');
    if(btnNova) btnNova.addEventListener('click', openModalFrota);

    // Handlers para fechar modais (CSP compliant)
    document.getElementById('btn-close-modal-frota')?.addEventListener('click', closeModalFrota);
    document.getElementById('btn-cancelar-modal-frota')?.addEventListener('click', closeModalFrota);
});
