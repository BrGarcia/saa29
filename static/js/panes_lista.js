// Carregamento de Panes
async function loadPanes() {
    const body = document.getElementById('panes-table-body');
    if (!body) return;
    
    const filterText = document.getElementById('filter-text');
    const filterStatus = document.getElementById('filter-status');
    const txt = filterText ? filterText.value : '';
    const sts = filterStatus ? filterStatus.value : '';
    const aeronaveId = new URLSearchParams(window.location.search).get('aeronave_id');

    let query = `/panes/?limit=50`;
    if (txt) query += `&texto=${encodeURIComponent(txt)}`;
    if (aeronaveId) query += `&aeronave_id=${encodeURIComponent(aeronaveId)}`;
    
    if (sts === 'EXCLUIDAS') {
        query += `&excluidas=true`;
    } else if (sts) {
        query += `&status=${sts}`;
    }

    try {
        const panes = await apiFetch(query);
        body.innerHTML = '';
        
        const user = JSON.parse(localStorage.getItem("saa29_user") || '{}');
        const funcao = user.funcao || '';

        if (panes.length === 0) {
            body.innerHTML = `<tr><td colspan="5" style="padding: 2rem; text-align: center; color: var(--text-secondary);">Nenhum registro encontrado.</td></tr>`;
            return;
        }

        panes.forEach(pane => {
            let badgeClass = "badge-aberta";
            if(pane.status === "RESOLVIDA") badgeClass = "badge-resolvida";
            if(!pane.ativo) badgeClass = "badge-resolvida"; 
            
            const rawDate = pane.data_abertura ? pane.data_abertura : new Date().toISOString();
            const dObj = new Date(rawDate);
            const shortDate = dObj.toLocaleString('pt-BR', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'});
            
            const obsConclusao = pane.observacao_conclusao || "Sem ação corretiva registrada.";
            const statusName = pane.ativo ? pane.status.replace("_", " ") : "EXCLUIDA";
            const matriculaAeronave = pane.aeronave?.matricula || "59XX";
            const responsavelMantenedor = (pane.responsaveis || []).find(r => r.papel === "MANTENEDOR");
            const responsavelFallback = (pane.responsaveis || []).find(r => r.trigrama);
            const responsavelTrigrama = responsavelMantenedor?.trigrama || responsavelFallback?.trigrama || "--";
            
            const responsavelBadge = responsavelTrigrama === "--"
                ? "--"
                : `<span class="badge" style="background: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border-color); font-family: monospace; font-size: 0.75rem;">${escapeHtml(responsavelTrigrama)}</span>`;
            
            const showAdminActions = (funcao === 'ENCARREGADO' || funcao === 'ADMINISTRADOR');

            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid var(--border-color)";
            tr.dataset.id = pane.id;
            
            tr.innerHTML = `
                <td style="padding: 1rem; font-weight: 500;">${escapeHtml(matriculaAeronave)}</td>
                <td style="padding: 1rem; max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(pane.descricao)}</td>
                <td style="padding: 1rem;"><span class="badge ${badgeClass}" title="${escapeHtml(obsConclusao)}">${escapeHtml(statusName)}</span></td>
                <td style="padding: 1rem; color: var(--text-secondary); font-size: 0.85rem;">${responsavelBadge}</td>
                <td style="padding: 1rem; text-align: center; display: flex; gap: 0.5rem; justify-content: center;">
                    <button class="btn-icon btn-view" style="color: var(--primary-color);" title="Visualizar">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                    </button>
                    ${showAdminActions && pane.ativo ? `<button class="btn-icon btn-edit" style="color: var(--status-warning);" title="Editar"><svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg></button>` : ''}
                    ${showAdminActions && pane.ativo ? `<button class="btn-icon btn-delete" style="color: var(--status-danger);" title="Excluir"><svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg></button>` : ''}
                    ${showAdminActions && !pane.ativo ? `<button class="btn-icon btn-restore" style="color: var(--status-ok);" title="Restaurar"><svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg></button>` : ''}
                </td>
            `;
            
            tr.onclick = () => window.location.href = `/panes/${pane.id}/detalhes`;
            
            // Event listeners para botões internos para parar propagação
            const btnEdit = tr.querySelector('.btn-edit');
            if(btnEdit) btnEdit.onclick = (e) => { e.stopPropagation(); openEditPaneModal(pane.id); };
            
            const btnDelete = tr.querySelector('.btn-delete');
            if(btnDelete) btnDelete.onclick = (e) => { e.stopPropagation(); softDeletePane(pane.id); };
            
            const btnRestore = tr.querySelector('.btn-restore');
            if(btnRestore) btnRestore.onclick = (e) => { e.stopPropagation(); restorePane(pane.id); };

            body.appendChild(tr);
        });
    } catch (e) {
        console.error("Erro na busca de panes:", e);
        body.innerHTML = `<tr><td colspan="5" style="padding: 2rem; text-align: center; color: var(--status-danger);">Falha na comunicação com a API: ${e.message}</td></tr>`;
    }
}

async function openSelecaoAeronaveModal() {
    const modalSelecao = document.getElementById('modal-selecao-aeronave');
    const gridAeronaves = document.getElementById('grid-aeronaves');
    modalSelecao.style.display = 'flex';
    gridAeronaves.innerHTML = '<p style="grid-column: span 5; text-align: center; color: var(--text-secondary);">Carregando frota...</p>';
    try {
        const frota = await apiFetch("/aeronaves/?limit=100");
        const frotaAtiva = frota.filter(f => f.status !== 'INATIVA'); 
        
        gridAeronaves.innerHTML = '';
        frotaAtiva.forEach(f => {
            const isOperacional = f.status === 'OPERACIONAL';
            const colorVar = isOperacional ? 'var(--status-ok)' : 'var(--status-warning)';
            const bgVar = isOperacional ? 'rgba(46, 204, 113, 0.1)' : 'rgba(243, 156, 18, 0.1)';

            const btn = document.createElement("button");
            btn.className = "btn-icon";
            btn.style = `
                display: flex; flex-direction: column; align-items: center; justify-content: center;
                background: ${bgVar}; border: 2px solid ${colorVar};
                border-radius: var(--radius-md); padding: 1rem; width: 100%; aspect-ratio: 1/1;
                transition: all 0.2s; color: var(--text-primary);
            `;
            btn.innerHTML = `<span style="font-weight: 700; font-family: monospace; font-size: 1.1rem; color: ${colorVar}">${f.matricula}</span>`;
            
            btn.onmouseover = () => { 
                btn.style.transform = 'translateY(-3px)';
                btn.style.boxShadow = `0 4px 12px ${isOperacional ? 'rgba(46, 204, 113, 0.2)' : 'rgba(243, 156, 18, 0.2)'}`;
                btn.style.background = isOperacional ? 'rgba(46, 204, 113, 0.2)' : 'rgba(243, 156, 18, 0.2)';
            };
            btn.onmouseout = () => { 
                btn.style.transform = 'translateY(0)';
                btn.style.boxShadow = 'none';
                btn.style.background = bgVar;
            };
            
            btn.onclick = () => openNuevaPaneModal(f.id, f.matricula);
            gridAeronaves.appendChild(btn);
        });

        if (frotaAtiva.length === 0) {
            gridAeronaves.innerHTML = '<p style="grid-column: span 5; text-align: center; color: var(--text-secondary);">Nenhuma aeronave disponível.</p>';
        }

    } catch(e) { 
        console.error(e);
        gridAeronaves.innerHTML = '<p style="grid-column: span 5; text-align: center; color: var(--status-danger);">Falha ao carregar frota.</p>';
    }
}

function closeSelecaoAeronaveModal() {
    document.getElementById('modal-selecao-aeronave').style.display = 'none';
}

async function openNuevaPaneModal(aeronaveId, matricula) {
    closeSelecaoAeronaveModal();
    document.getElementById('modal-nova-pane').style.display = 'flex';
    const aeronaveSelect = document.getElementById('aeronaveSelect');
    const mantenedorResponsavelSelect = document.getElementById('mantenedorResponsavelSelect');
    
    // Hydrate aeronaves combo box (pre-select)
    try {
        const frota = await apiFetch("/aeronaves/?limit=100");
        aeronaveSelect.innerHTML = `<option value="">-- Selecionar Aeronave --</option>`;
        frota.forEach(f => {
            const opt = document.createElement("option");
            opt.value = f.id;
            opt.innerText = `${f.matricula} (S/N: ${f.serial_number})`;
            if(f.id === aeronaveId) opt.selected = true;
            aeronaveSelect.appendChild(opt);
        });
    } catch(e) { console.error(e) }

    // Hydrate Mantenedores
    try {
        const usuarios = await apiFetch("/auth/usuarios");
        const responsaveisPermitidos = usuarios.filter(u => ["MANTENEDOR", "ENCARREGADO"].includes(u.funcao));
        mantenedorResponsavelSelect.innerHTML = `<option value="">-- Não atribuir responsável --</option>`;
        responsaveisPermitidos.forEach(u => {
            const opt = document.createElement("option");
            opt.value = u.id;
            const designacao = [u.posto, u.nome].filter(Boolean).join(" ");
            const detalhe = u.trigrama ? ` - ${u.trigrama}` : "";
            opt.innerText = `${designacao}${detalhe}`;
            mantenedorResponsavelSelect.appendChild(opt);
        });
    } catch(e) { console.error(e) }
}

function closeNovaPaneModal() {
    document.getElementById('modal-nova-pane').style.display = 'none';
    document.getElementById('formNovaPane').reset();
}

async function openEditPaneModal(paneId) {
    try {
        const pane = await apiFetch(`/panes/${paneId}`);
        document.getElementById('editPaneId').value = pane.id;
        document.getElementById('editSistemaInput').value = pane.sistema_subsistema || "";
        document.getElementById('editDescricaoInput').value = pane.descricao || "";
        document.getElementById('modal-editar-pane').style.display = 'flex';
    } catch(e) {
        showToast("Falha ao buscar dados da pane.", "error");
    }
}

function closeEditPaneModal() {
    document.getElementById('modal-editar-pane').style.display = 'none';
    document.getElementById('formEditarPane').reset();
}

async function handleSalvarEdicao(e) {
    e.preventDefault();
    const paneId = document.getElementById('editPaneId').value;
    const btn = document.getElementById('btnAtualizarPane');
    
    const payload = {
        sistema_subsistema: document.getElementById('editSistemaInput').value.trim(),
        descricao: document.getElementById('editDescricaoInput').value.trim()
    };

    btn.disabled = true;
    btn.innerText = "Salvando...";

    try {
        await apiFetch(`/panes/${paneId}`, {
            method: "PUT",
            body: payload
        });
        showToast("Ocorrência atualizada!", "success");
        closeEditPaneModal();
        loadPanes();
    } catch(err) {
        // Erro já tratado no apiFetch
    } finally {
        btn.disabled = false;
        btn.innerText = "Salvar Alterações";
    }
}

async function handleCriarPane(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarPane');
    const aeronaveSelect = document.getElementById('aeronaveSelect');
    const mantenedorResponsavelSelect = document.getElementById('mantenedorResponsavelSelect');

    btn.disabled = true;
    btn.innerText = "Registrando...";

    let sistema = document.getElementById('sistemaInput').value.trim();
    let descricao = document.getElementById('descricaoInput').value.trim();
    if(!sistema) sistema = "A ser definido";
    if(!descricao) descricao = "Aguardando relato.";

    const payload = {
        aeronave_id: aeronaveSelect.value,
        sistema_subsistema: sistema,
        descricao: descricao
    };
    if (mantenedorResponsavelSelect.value) {
        payload.mantenedor_responsavel_id = mantenedorResponsavelSelect.value;
    }

    try {
        const pane = await apiFetch("/panes/", {
            method: "POST",
            body: payload
        });
        
        // Upload Foto se existir
        const fileInput = document.getElementById('fotoInput');
        if(fileInput && fileInput.files.length > 0) {
            const formData = new FormData();
            formData.append("arquivo", fileInput.files[0]);
            const uploadResp = await fetch(`/panes/${pane.id}/anexos`, {
                method: "POST",
                body: formData,
                credentials: "same-origin"
            });
            
            if (!uploadResp.ok) {
                let errMsg = "Erro no envio";
                try {
                    const errData = await uploadResp.json();
                    errMsg = errData.detail || errMsg;
                } catch(e) {}
                
                showToast(`Pane criada, mas o anexo falhou: ${errMsg}`, "warning");
                closeNovaPaneModal();
                loadPanes();
                return; 
            }
        }

        showToast("Relato de Pane Registrado!", "success");
        closeNovaPaneModal();
        loadPanes();
    } catch(err) {
        // Toast já mostrado via apiFetch
    } finally {
        btn.disabled = false;
        btn.innerText = "Cadastrar Pane";
    }
}

async function softDeletePane(id) {
    if(!confirm("Atenção: A pane será inativada e constará na lixeira de Excluídas. Deseja prosseguir?")) return;
    try {
        await apiFetch(`/panes/${id}`, { method: 'DELETE' });
        showToast("Pane removida com sucesso.", "success");
        loadPanes();
    } catch(e) {}
}

async function restorePane(id) {
    if(!confirm("Deseja restaurar esta pane para o estado ativo?")) return;
    try {
        await apiFetch(`/panes/${id}/restaurar`, { method: 'POST' });
        showToast("Pane restaurada com sucesso.", "success");
        loadPanes();
    } catch(e) {}
}

// Initialization and Event Listeners
document.addEventListener("DOMContentLoaded", () => {
    const filterText = document.getElementById('filter-text');
    const filterStatus = document.getElementById('filter-status');
    const btnRegistrar = document.querySelector('button.btn-primary');
    const formNovaPane = document.getElementById('formNovaPane');
    const formEditarPane = document.getElementById('formEditarPane');

    if (filterText) {
        let filtroTimeout;
        filterText.addEventListener("input", () => {
            clearTimeout(filtroTimeout);
            filtroTimeout = setTimeout(loadPanes, 250);
        });
    }
    if (filterStatus) {
        filterStatus.addEventListener("change", loadPanes);
    }
    if (btnRegistrar) {
        btnRegistrar.addEventListener('click', openSelecaoAeronaveModal);
    }
    if (formNovaPane) {
        formNovaPane.addEventListener('submit', handleCriarPane);
    }
    if (formEditarPane) {
        formEditarPane.addEventListener('submit', handleSalvarEdicao);
    }

    // Expose close functions for the Close buttons (since some are still using inline onclick for brevity, 
    // but in a strict CSP we ideally want all event listeners attached here)
    window.closeSelecaoAeronaveModal = closeSelecaoAeronaveModal;
    window.closeNovaPaneModal = closeNovaPaneModal;
    window.closeEditPaneModal = closeEditPaneModal;
    window.openEditPaneModal = openEditPaneModal;
    window.softDeletePane = softDeletePane;
    window.restorePane = restorePane;

    loadPanes();
});
