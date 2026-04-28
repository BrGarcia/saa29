/**
 * Scripts para a página de configurações.
 * Por enquanto serve de stub para as funcionalidades futuras.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Verificação extra de segurança no frontend
    const userJson = localStorage.getItem("saa29_user");
    if (userJson) {
        try {
            const user = JSON.parse(userJson);
            const funcao = user.funcao ? user.funcao.toUpperCase() : '';
            if (funcao !== 'ADMINISTRADOR' && funcao !== 'ENCARREGADO') {
                showToast("Acesso Negado: Apenas administradores e encarregados podem acessar esta área.", "error");
                setTimeout(() => {
                    window.location.href = "/panes";
                }, 2000);
            }
        } catch (e) {
            window.location.href = "/panes";
        }
    } else {
        window.location.href = "/login";
    }

    const btnNova = document.getElementById('btn-nova-aeronave');
    if(btnNova) btnNova.addEventListener('click', openModalConfig);
    
    const form = document.getElementById('formAeronave');
    if(form) form.addEventListener('submit', criarAeronave);

    const btnAlterarStatus = document.getElementById('btn-alterar-status-aeronave');
    if(btnAlterarStatus) btnAlterarStatus.addEventListener('click', openModalStatus);
    
    const formStatus = document.getElementById('formAlterarStatusAeronave');
    if(formStatus) formStatus.addEventListener('submit', alterarStatusAeronave);

    const btnTiposControle = document.getElementById('btn-tipos-controle');
    if(btnTiposControle) btnTiposControle.addEventListener('click', openModalTipoControle);

    const formTipoControle = document.getElementById('formTipoControle');
    if(formTipoControle) formTipoControle.addEventListener('submit', salvarTipoControle);

    const btnEditarTipo = document.getElementById('btn-editar-tipo-controle');
    if(btnEditarTipo) btnEditarTipo.addEventListener('click', openModalEditarTipo);

    const formEditarTipo = document.getElementById('formEditarTipoControle');
    if(formEditarTipo) formEditarTipo.addEventListener('submit', salvarEditarTipo);

    const btnEquipamentoControle = document.getElementById('btn-equipamento-controle');
    if(btnEquipamentoControle) btnEquipamentoControle.addEventListener('click', openModalRegras);

    const formNovaRegra = document.getElementById('formNovaRegra');
    if(formNovaRegra) formNovaRegra.addEventListener('submit', salvarNovaRegra);

    const btnPN = document.getElementById('btn-gerenciar-catalogo');
    if(btnPN) btnPN.addEventListener('click', openModalCatalogo);

    const btnNovoPN = document.getElementById('btn-novo-pn');
    if(btnNovoPN) btnNovoPN.addEventListener('click', openModalNovoPN);

    const formNovoPN = document.getElementById('formNovoPN');
    if(formNovoPN) formNovoPN.addEventListener('submit', salvarNovoPN);

    const formEditarPN = document.getElementById('formEditarPN');
    if(formEditarPN) formEditarPN.addEventListener('submit', salvarEditarPN);

    // Navegação Efetivo
    const btnEfetivo = document.getElementById('btn-config-efetivo');
    if (btnEfetivo) {
        btnEfetivo.addEventListener('click', () => {
            window.location.href = '/efetivo';
        });
    }

    // Handlers para fechar modais (CSP compliant)
    document.getElementById('btn-close-modal-aeronave')?.addEventListener('click', closeModalConfig);
    document.getElementById('btn-cancel-modal-aeronave')?.addEventListener('click', closeModalConfig);
    
    document.getElementById('btn-close-modal-status')?.addEventListener('click', closeModalStatus);
    document.getElementById('btn-cancel-modal-status')?.addEventListener('click', closeModalStatus);
    
    document.getElementById('btn-close-modal-tipo-controle')?.addEventListener('click', closeModalTipoControle);
    document.getElementById('btn-cancel-modal-tipo-controle')?.addEventListener('click', closeModalTipoControle);
    
    document.getElementById('btn-close-modal-editar-tipo')?.addEventListener('click', closeModalEditarTipo);
    document.getElementById('btn-cancel-modal-editar-tipo')?.addEventListener('click', closeModalEditarTipo);
    
    document.getElementById('btn-close-modal-catalogo')?.addEventListener('click', closeModalCatalogo);
    document.getElementById('btn-close-catalogo')?.addEventListener('click', closeModalCatalogo);

    document.getElementById('btn-close-modal-novo-pn')?.addEventListener('click', closeModalNovoPN);
    document.getElementById('btn-cancel-modal-novo-pn')?.addEventListener('click', closeModalNovoPN);

    document.getElementById('btn-close-modal-editar-pn')?.addEventListener('click', closeModalEditarPN);
    document.getElementById('btn-cancel-modal-editar-pn')?.addEventListener('click', closeModalEditarPN);
    
    document.getElementById('btn-close-modal-regras')?.addEventListener('click', closeModalRegras);
    document.getElementById('btn-close-regras')?.addEventListener('click', closeModalRegras);
});

function openModalConfig() {
    document.querySelector("#modal-aeronave h3").innerText = "Nova Aeronave";
    document.getElementById("btnSalvarAcft").innerText = "Registrar";
    document.getElementById("statusInput").value = "DISPONIVEL";
    document.getElementById("statusInput").disabled = false;
    document.getElementById("modal-aeronave").style.display = "flex";
}

function closeModalConfig() {
    document.getElementById("modal-aeronave").style.display = "none";
    document.getElementById("formAeronave").reset();
}

async function criarAeronave(e) {
    e.preventDefault();
    const btn = document.getElementById("btnSalvarAcft");
    btn.disabled = true;
    
    const matricula = document.getElementById("matriculaInput").value.trim().toUpperCase();
    const sn = document.getElementById("snInput").value.trim();
    const status = document.getElementById("statusInput").value;

    try {
        await apiFetch("/aeronaves/", {
            method: "POST",
            body: {
                matricula: matricula,
                serial_number: sn,
                status: status
            }
        });
        showToast("Aeronave cadastrada com sucesso!", "success");
        closeModalConfig();
    } catch(err) {
        showToast(err.message || "Erro ao cadastrar aeronave.", "error");
    } finally {
        btn.disabled = false;
    }
}

window.openModalConfig = openModalConfig;
window.closeModalConfig = closeModalConfig;

async function openModalStatus() {
    document.getElementById("modal-alterar-status-aeronave").style.display = "flex";
    const select = document.getElementById("aeronaveStatusSelect");
    select.innerHTML = '<option value="" disabled selected>Carregando aeronaves...</option>';
    
    try {
        const aeronaves = await apiFetch(`/aeronaves/?limit=1000&incluir_inativas=true`);
        
        if (aeronaves.length === 0) {
            select.innerHTML = '<option value="" disabled selected>Nenhuma aeronave encontrada.</option>';
        } else {
            select.innerHTML = '<option value="" disabled selected>Selecione uma matrícula</option>';
            aeronaves.sort((a,b) => a.matricula.localeCompare(b.matricula)).forEach(a => {
                const opt = document.createElement("option");
                opt.value = a.id;
                opt.text = `${a.matricula} (Status: ${a.status})`;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        select.innerHTML = '<option value="" disabled selected>Erro ao carregar aeronaves</option>';
    }
}

function closeModalStatus() {
    document.getElementById("modal-alterar-status-aeronave").style.display = "none";
    document.getElementById("formAlterarStatusAeronave").reset();
}

async function alterarStatusAeronave(e) {
    e.preventDefault();
    const btn = document.getElementById("btnConfirmarStatus");
    const select = document.getElementById("aeronaveStatusSelect");
    const novoStatus = document.getElementById("novoStatusInput").value;
    const aeronaveId = select.value;
    
    if (!aeronaveId) {
        showToast("Selecione uma aeronave.", "error");
        return;
    }

    const optText = select.options[select.selectedIndex].text;
    const matricula = optText.split(' ')[0];
    const statusAtualMatch = optText.match(/Status:\s*([^)]+)/);
    const statusAtual = statusAtualMatch ? statusAtualMatch[1] : null;
    
    if (!confirm(`Deseja alterar o status da aeronave ${matricula} para ${novoStatus}?`)) {
        return;
    }
    
    btn.disabled = true;
    
    try {
        if (novoStatus === statusAtual) {
            showToast("A aeronave já está nesse status.", "info");
            closeModalStatus();
            return;
        }

        // Regra de Negócio: Se for inativar ou reativar (sair de INATIVA), precisa usar o endpoint toggle
        if (statusAtual === 'INATIVA' || novoStatus === 'INATIVA') {
            await apiFetch(`/aeronaves/${aeronaveId}/toggle-status`, { method: "POST" });
            
            // Se estava inativa, o toggle mudou para DISPONIVEL. 
            // Se o usuário pediu outro status (ex: ESTOCADA), precisa de um PUT complementar.
            if (statusAtual === 'INATIVA' && novoStatus !== 'DISPONIVEL' && novoStatus !== 'INATIVA') {
                await apiFetch(`/aeronaves/${aeronaveId}`, { 
                    method: "PUT",
                    body: { status: novoStatus }
                });
            }
        } else {
            // Transições comuns (DISPONIVEL <-> ESTOCADA, etc.)
            await apiFetch(`/aeronaves/${aeronaveId}`, { 
                method: "PUT",
                body: { status: novoStatus }
            });
        }

        showToast(`Status da aeronave ${matricula} alterado para ${novoStatus}!`, "success");
        closeModalStatus();
    } catch(err) {
        showToast(err.message || "Erro ao alterar status.", "error");
    } finally {
        btn.disabled = false;
    }
}

window.openModalStatus = openModalStatus;
window.closeModalStatus = closeModalStatus;

// ==========================================
// Módulo de Controles de Vencimento
// ==========================================

function openModalTipoControle() {
    const modal = document.getElementById('modal-tipo-controle');
    if(modal) modal.style.display = 'flex';
}

function closeModalTipoControle() {
    const modal = document.getElementById('modal-tipo-controle');
    if(modal) modal.style.display = 'none';
    const form = document.getElementById('formTipoControle');
    if(form) form.reset();
}

async function salvarTipoControle(e) {
    e.preventDefault();
    const btn = document.getElementById("btnSalvarTipoControle");
    btn.disabled = true;

    const nome = document.getElementById("codigoControleInput").value.trim().toUpperCase();
    const descricao = document.getElementById("descControleInput").value.trim();

    try {
        await apiFetch("/vencimentos/tipos-controle", {
            method: "POST",
            body: {
                nome: nome,
                descricao: descricao
            }
        });
        showToast("Tipo de controle cadastrado com sucesso!", "success");
        closeModalTipoControle();
    } catch(err) {
        showToast(err.message || "Erro ao cadastrar tipo de controle.", "error");
    } finally {
        btn.disabled = false;
    }
}

window.openModalTipoControle = openModalTipoControle;
window.closeModalTipoControle = closeModalTipoControle;

// ---- Editar Tipo de Controle ----

let tiposControleCache = [];

async function openModalEditarTipo() {
    const modal = document.getElementById('modal-editar-tipo-controle');
    modal.style.display = 'flex';
    const select = document.getElementById('editarTipoSelect');
    select.innerHTML = '<option value="" disabled selected>Carregando...</option>';
    document.getElementById('editarCodigoInput').value = '';
    document.getElementById('editarDescInput').value = '';

    try {
        tiposControleCache = await apiFetch('/vencimentos/tipos-controle');
        if (tiposControleCache.length === 0) {
            select.innerHTML = '<option value="" disabled selected>Nenhum tipo cadastrado</option>';
        } else {
            select.innerHTML = '<option value="" disabled selected>Selecione um tipo</option>';
            tiposControleCache.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.text = `${t.nome}${t.descricao ? ' — ' + t.descricao : ''}`;
                select.appendChild(opt);
            });
        }
    } catch(e) {
        select.innerHTML = '<option value="" disabled selected>Erro ao carregar</option>';
    }

    select.addEventListener('change', function() {
        const tipo = tiposControleCache.find(t => t.id === this.value);
        if(tipo) {
            document.getElementById('editarCodigoInput').value = tipo.nome;
            document.getElementById('editarDescInput').value = tipo.descricao || '';
        }
    });
}

function closeModalEditarTipo() {
    const modal = document.getElementById('modal-editar-tipo-controle');
    if(modal) modal.style.display = 'none';
    const form = document.getElementById('formEditarTipoControle');
    if(form) form.reset();
}

async function salvarEditarTipo(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarEditarTipo');
    const select = document.getElementById('editarTipoSelect');
    const tipoId = select.value;

    if(!tipoId) {
        showToast('Selecione um tipo de controle.', 'error');
        return;
    }

    btn.disabled = true;
    const nome = document.getElementById('editarCodigoInput').value.trim().toUpperCase();
    const descricao = document.getElementById('editarDescInput').value.trim();

    try {
        await apiFetch(`/vencimentos/tipos-controle/${tipoId}`, {
            method: 'PUT',
            body: { nome, descricao }
        });
        showToast('Tipo de controle atualizado com sucesso!', 'success');
        closeModalEditarTipo();
    } catch(err) {
        showToast(err.message || 'Erro ao atualizar tipo de controle.', 'error');
    } finally {
        btn.disabled = false;
    }
}

window.openModalEditarTipo = openModalEditarTipo;
window.closeModalEditarTipo = closeModalEditarTipo;

// ---- Regras por Equipamento (Vencimentos) ----

async function openModalRegras() {
    const modal = document.getElementById('modal-regras-equipamento');
    modal.style.display = 'flex';
    await carregarOptionsRegras();
    await carregarListaRegras();
}

function closeModalRegras() {
    const modal = document.getElementById('modal-regras-equipamento');
    if(modal) modal.style.display = 'none';
    const form = document.getElementById('formNovaRegra');
    if(form) form.reset();
}

async function carregarOptionsRegras() {
    const selectEquip = document.getElementById('regraEquipamentoSelect');
    const selectTipo = document.getElementById('regraTipoSelect');
    
    selectEquip.innerHTML = '<option value="">Carregando...</option>';
    selectTipo.innerHTML = '<option value="">Carregando...</option>';

    try {
        const [equipamentos, tipos] = await Promise.all([
            apiFetch('/equipamentos/'),
            apiFetch('/vencimentos/tipos-controle')
        ]);

        selectEquip.innerHTML = '<option value="">Selecione o PN...</option>';
        equipamentos.forEach(e => {
            const opt = document.createElement('option');
            opt.value = e.id;
            opt.text = `${e.part_number} — ${e.nome_generico}`;
            selectEquip.appendChild(opt);
        });

        selectTipo.innerHTML = '<option value="">Selecione o Controle...</option>';
        tipos.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.text = t.nome;
            selectTipo.appendChild(opt);
        });
    } catch(e) {
        showToast("Erro ao carregar opções para regras.", "error");
    }
}

async function carregarListaRegras() {
    const tbody = document.getElementById('lista-regras-body');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem;">Carregando regras...</td></tr>';

    try {
        const regras = await apiFetch('/vencimentos/regras');
        tbody.innerHTML = '';
        
        if(regras.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhuma regra configurada.</td></tr>';
            return;
        }

        regras.forEach(r => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-color)';
            tr.innerHTML = `
                <td style="padding: 0.75rem;">${escapeHtml(r.pn) || '---'}</td>
                <td style="padding: 0.75rem; text-align: center;"><strong>${escapeHtml(r.tipo_nome) || '---'}</strong></td>
                <td style="padding: 0.75rem; text-align: center;">${r.periodicidade_meses} meses</td>
                <td style="padding: 0.75rem; text-align: right;">
                    <button type="button" 
                            class="btn-icon btn-remover-regra" 
                            style="color: var(--status-danger);"
                            data-modelo="${r.modelo_id}"
                            data-tipo="${r.tipo_controle_id}">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="pointer-events: none;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                </td>
            `;
            const btnRemove = tr.querySelector('.btn-remover-regra');
            if (btnRemove) {
                btnRemove.addEventListener('click', (e) => {
                    const mid = e.currentTarget.getAttribute('data-modelo');
                    const tid = e.currentTarget.getAttribute('data-tipo');
                    removerRegra(mid, tid);
                });
            }
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar lista.</td></tr>';
    }
}

async function salvarNovaRegra(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;

    const modelo_id = document.getElementById('regraEquipamentoSelect').value;
    const tipo_controle_id = document.getElementById('regraTipoSelect').value;
    const periodicidade_meses = parseInt(document.getElementById('regraMesesInput').value);

    try {
        await apiFetch('/vencimentos/regras', {
            method: 'POST',
            body: { modelo_id, tipo_controle_id, periodicidade_meses }
        });
        showToast("Regra cadastrada/atualizada com sucesso!", "success");
        await carregarListaRegras();
    } catch(err) {
        showToast(err.message || "Erro ao salvar regra.", "error");
    } finally {
        btn.disabled = false;
    }
}

async function removerRegra(modeloId, tipoId) {
    console.log("INÍCIO: removerRegra", {modeloId, tipoId});
    
    if(!confirm("Tem certeza que deseja remover esta regra de periodicidade?")) {
        console.log("CANCELADO: Usuário desistiu");
        return;
    }

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    console.log("CSRF Token encontrado:", csrfToken ? "Sim" : "Não");

    try {
        console.log("DISPARANDO: fetch DELETE...");
        const response = await fetch(`/vencimentos/regras/${modeloId}/${tipoId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRF-Token': csrfToken || '',
                'Content-Type': 'application/json'
            }
        });

        console.log("RESPOSTA RECEBIDA: Status", response.status);

        if (response.ok) {
            let data = null;
            if (response.status !== 204) {
                data = await response.json().catch(() => ({}));
            }
            console.log("DADOS RECEBIDOS:", data);
            showToast("Regra removida com sucesso!", "success");
            await carregarListaRegras();
        } else {
            const error = await response.json().catch(() => ({ detail: "Erro desconhecido" }));
            console.error("ERRO NA API:", response.status, error);
            showToast(error.detail || "Erro ao excluir.", "error");
        }
    } catch(err) {
        console.error("ERRO FATAL (Network/JS):", err);
        showToast("Falha de conexão ao excluir regra.", "error");
    }
}

window.openModalRegras = openModalRegras;
window.closeModalRegras = closeModalRegras;
window.removerRegra = removerRegra;

// ==========================================
// Módulo de Catálogo (Part Numbers)
// ==========================================

function openModalCatalogo() {
    const modal = document.getElementById('modal-catalogo');
    modal.style.display = 'flex';
    carregarListaCatalogo();
}

function closeModalCatalogo() {
    const modal = document.getElementById('modal-catalogo');
    if(modal) modal.style.display = 'none';
}

function openModalNovoPN() {
    document.getElementById('modal-novo-pn').style.display = 'flex';
}

function closeModalNovoPN() {
    document.getElementById('modal-novo-pn').style.display = 'none';
    document.getElementById('formNovoPN').reset();
}

let catalogoCache = [];

async function carregarListaCatalogo() {
    const tbody = document.getElementById('lista-catalogo-body');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem;">Carregando catálogo...</td></tr>';

    try {
        catalogoCache = await apiFetch('/equipamentos/');
        tbody.innerHTML = '';
        
        if(catalogoCache.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhum equipamento cadastrado.</td></tr>';
            return;
        }

        catalogoCache.forEach(m => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-color)';
            tr.innerHTML = `
                <td style="padding: 0.75rem;"><strong>${escapeHtml(m.part_number)}</strong></td>
                <td style="padding: 0.75rem;">${escapeHtml(m.nome_generico)}</td>
                <td style="padding: 0.75rem; color: var(--text-secondary); font-size: 0.85rem;">${escapeHtml(m.descricao) || '---'}</td>
                <td style="padding: 0.75rem; text-align: right; display: flex; gap: 0.5rem; justify-content: flex-end;">
                    <button type="button" class="btn-icon btn-editar-pn" data-id="${m.id}" style="color: var(--primary-color);">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    </button>
                    <button type="button" class="btn-icon btn-remover-pn" data-id="${m.id}" style="color: var(--status-danger);">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                </td>
            `;
            
            tr.querySelector('.btn-editar-pn').addEventListener('click', () => openModalEditarPN(m.id));
            tr.querySelector('.btn-remover-pn').addEventListener('click', () => removerPN(m.id, m.part_number));
            
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar catálogo.</td></tr>';
    }
}

async function salvarNovoPN(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarPN');
    btn.disabled = true;

    const part_number = document.getElementById('pnInput').value.trim().toUpperCase();
    const nome_generico = document.getElementById('nomePnInput').value.trim();
    const descricao = document.getElementById('descPnInput').value.trim();

    try {
        await apiFetch('/equipamentos/', {
            method: 'POST',
            body: { part_number, nome_generico, descricao }
        });
        showToast("Part Number cadastrado com sucesso!", "success");
        closeModalNovoPN();
        if (document.getElementById('modal-catalogo').style.display === 'flex') {
            carregarListaCatalogo();
        }
    } catch(err) {
        showToast(err.message || "Erro ao cadastrar PN.", "error");
    } finally {
        btn.disabled = false;
    }
}

function openModalEditarPN(id) {
    const pn = catalogoCache.find(m => m.id === id);
    if (!pn) return;

    document.getElementById('editarPnId').value = pn.id;
    document.getElementById('editarPnInput').value = pn.part_number;
    document.getElementById('editarNomePnInput').value = pn.nome_generico;
    document.getElementById('editarDescPnInput').value = pn.descricao || '';
    
    document.getElementById('modal-editar-pn').style.display = 'flex';
}

function closeModalEditarPN() {
    document.getElementById('modal-editar-pn').style.display = 'none';
    document.getElementById('formEditarPN').reset();
}

async function salvarEditarPN(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarEditarPN');
    const id = document.getElementById('editarPnId').value;
    
    btn.disabled = true;
    const part_number = document.getElementById('editarPnInput').value.trim().toUpperCase();
    const nome_generico = document.getElementById('editarNomePnInput').value.trim();
    const descricao = document.getElementById('editarDescPnInput').value.trim();

    try {
        await apiFetch(`/equipamentos/${id}`, {
            method: 'PATCH',
            body: { part_number, nome_generico, descricao }
        });
        showToast("Part Number atualizado com sucesso!", "success");
        closeModalEditarPN();
        carregarListaCatalogo();
    } catch(err) {
        showToast(err.message || "Erro ao atualizar PN.", "error");
    } finally {
        btn.disabled = false;
    }
}

async function removerPN(id, pn) {
    if (!confirm(`Tem certeza que deseja remover o PN ${pn}? Esta ação pode afetar itens vinculados.`)) {
        return;
    }

    try {
        await apiFetch(`/equipamentos/${id}`, { method: 'DELETE' });
        showToast("Part Number removido com sucesso!", "success");
        carregarListaCatalogo();
    } catch(err) {
        showToast(err.message || "Erro ao remover PN.", "error");
    }
}

window.openModalCatalogo = openModalCatalogo;
window.closeModalCatalogo = closeModalCatalogo;
window.openModalNovoPN = openModalNovoPN;
window.closeModalNovoPN = closeModalNovoPN;
window.salvarNovoPN = salvarNovoPN;
window.openModalEditarPN = openModalEditarPN;
window.closeModalEditarPN = closeModalEditarPN;
window.salvarEditarPN = salvarEditarPN;
window.removerPN = removerPN;
