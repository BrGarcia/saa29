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
                    window.location.href = "/dashboard";
                }, 2000);
            }
        } catch (e) {
            window.location.href = "/dashboard";
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

    // Inspeções
    document.getElementById('btn-config-inspecoes')?.addEventListener('click', openModalTiposInspecao);
    document.getElementById('btn-gerenciar-catalogo-tarefas')?.addEventListener('click', openModalCatalogoTarefas);
    document.getElementById('btn-criar-inspecao')?.addEventListener('click', () => {
        window.location.href = '/inspecoes';
    });

    document.getElementById('btn-close-modal-inspecoes')?.addEventListener('click', closeModalTiposInspecao);
    document.getElementById('btn-close-inspecoes')?.addEventListener('click', closeModalTiposInspecao);
    
    document.getElementById('btn-novo-tipo-inspecao')?.addEventListener('click', () => openModalFormTipoInspecao());
    document.getElementById('btn-close-form-tipo-inspecao')?.addEventListener('click', closeModalFormTipoInspecao);
    document.getElementById('btn-cancel-form-tipo-inspecao')?.addEventListener('click', closeModalFormTipoInspecao);
    document.getElementById('formTipoInspecao')?.addEventListener('submit', salvarTipoInspecao);

    document.getElementById('btn-close-modal-tarefas')?.addEventListener('click', closeModalTarefasTemplate);
    document.getElementById('btn-close-tarefas')?.addEventListener('click', closeModalTarefasTemplate);
    document.getElementById('formNovaTarefa')?.addEventListener('submit', salvarTarefaTemplate);

    // Catálogo de Tarefas
    document.getElementById('btn-close-modal-catalogo-tarefas')?.addEventListener('click', closeModalCatalogoTarefas);
    document.getElementById('btn-close-catalogo-tarefas')?.addEventListener('click', closeModalCatalogoTarefas);
    document.getElementById('btn-nova-tarefa-catalogo')?.addEventListener('click', () => openModalFormTarefaCatalogo());
    document.getElementById('btn-close-form-tarefa-catalogo')?.addEventListener('click', closeModalFormTarefaCatalogo);
    document.getElementById('btn-cancel-form-tarefa-catalogo')?.addEventListener('click', closeModalFormTarefaCatalogo);
    document.getElementById('formTarefaCatalogo')?.addEventListener('submit', salvarTarefaCatalogo);

    // Calendário
    document.getElementById('btn-config-calendario-tipos')?.addEventListener('click', openModalCalendarioTipos);
    document.getElementById('btn-close-modal-calendario-tipos')?.addEventListener('click', closeModalCalendarioTipos);
    document.getElementById('btn-close-calendario-tipos')?.addEventListener('click', closeModalCalendarioTipos);
    
    document.getElementById('btn-novo-tipo-evento')?.addEventListener('click', () => openModalFormTipoEvento());
    document.getElementById('btn-close-form-tipo-evento')?.addEventListener('click', closeModalFormTipoEvento);
    document.getElementById('btn-cancel-form-tipo-evento')?.addEventListener('click', closeModalFormTipoEvento);
    document.getElementById('formTipoEvento')?.addEventListener('submit', salvarTipoEvento);
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

    try {
        console.log("DISPARANDO: apiFetch DELETE...");
        const data = await apiFetch(`/vencimentos/regras/${modeloId}/${tipoId}`, {
            method: 'DELETE'
        });

        console.log("SUCESSO: Regra removida");
        showToast("Regra removida com sucesso!", "success");
        await carregarListaRegras();
    } catch(err) {
        console.error("ERRO FATAL (Network/JS):", err);
        // apiFetch já mostra o toast se falhar, mas mantemos o log
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
window.openModalEditarPN = openModalEditarPN;
window.closeModalEditarPN = closeModalEditarPN;
window.salvarEditarPN = salvarEditarPN;
window.removerPN = removerPN;

// ==========================================
// Módulo de Inspeções (Tipos e Tarefas)
// ==========================================

let tiposInspecaoCache = [];
let tarefasTemplateCache = [];

function openModalTiposInspecao() {
    const modal = document.getElementById('modal-inspecoes-tipos');
    modal.style.display = 'flex';
    carregarListaTiposInspecao();
}

function closeModalTiposInspecao() {
    const modal = document.getElementById('modal-inspecoes-tipos');
    if(modal) modal.style.display = 'none';
}

async function carregarListaTiposInspecao() {
    const tbody = document.getElementById('lista-tipos-inspecao-body');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem;">Carregando...</td></tr>';

    try {
        tiposInspecaoCache = await apiFetch('/inspecoes/tipos?incluir_inativos=true');
        tbody.innerHTML = '';
        
        if(tiposInspecaoCache.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhum tipo de inspeção cadastrado.</td></tr>';
            return;
        }

        tiposInspecaoCache.forEach(t => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-color)';
            tr.innerHTML = `
                <td style="padding: 0.75rem;"><strong>${escapeHtml(t.codigo)}</strong></td>
                <td style="padding: 0.75rem;">
                    <div style="font-weight: 500;">${escapeHtml(t.nome)}</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(t.descricao || '')}</div>
                </td>
                <td style="padding: 0.75rem; text-align: center; font-size: 0.9rem;">
                    ${t.duracao_dias > 0 ? `<span title="Duração">${t.duracao_dias}d</span>` : '<span style="color:var(--text-secondary)">—</span>'}
                </td>
                <td style="padding: 0.75rem; text-align: center;">
                    <span style="display: inline-block; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; background: ${t.ativo ? 'rgba(46, 204, 113, 0.1)' : 'rgba(231, 76, 60, 0.1)'}; color: ${t.ativo ? 'var(--status-ok)' : 'var(--status-danger)'};">${t.ativo ? 'Ativo' : 'Inativo'}</span>
                </td>
                <td style="padding: 0.75rem; text-align: right; display: flex; gap: 0.5rem; justify-content: flex-end;">
                    <button type="button" class="btn-icon btn-tarefas-tipo" data-id="${t.id}" title="Gerenciar Tarefas" style="color: var(--primary-color);">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>
                    </button>
                    <button type="button" class="btn-icon btn-editar-tipo-insp" data-id="${t.id}" title="Editar Tipo" style="color: var(--text-color);">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    </button>
                </td>
            `;
            
            tr.querySelector('.btn-tarefas-tipo').addEventListener('click', () => openModalTarefasTemplate(t.id));
            tr.querySelector('.btn-editar-tipo-insp').addEventListener('click', () => openModalFormTipoInspecao(t.id));
            
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar tipos de inspeção.</td></tr>';
    }
}

function openModalFormTipoInspecao(id = null) {
    document.getElementById('modal-form-tipo-inspecao').style.display = 'flex';
    document.getElementById('formTipoInspecao').reset();
    
    if (id) {
        const t = tiposInspecaoCache.find(x => x.id === id);
        if (t) {
            document.getElementById('titulo-form-tipo-inspecao').innerText = 'Editar Tipo de Inspeção';
            document.getElementById('tipoInspecaoId').value = t.id;
            document.getElementById('codigoTipoInspecaoInput').value = t.codigo;
            document.getElementById('nomeTipoInspecaoInput').value = t.nome;
            document.getElementById('descTipoInspecaoInput').value = t.descricao || '';
            document.getElementById('duracaoTipoInspecaoInput').value = t.duracao_dias ?? 0;
            document.getElementById('container-status-tipo-inspecao').style.display = 'block';
            document.getElementById('ativoTipoInspecaoInput').value = t.ativo ? 'true' : 'false';
        }
    } else {
        document.getElementById('titulo-form-tipo-inspecao').innerText = 'Novo Tipo de Inspeção';
        document.getElementById('tipoInspecaoId').value = '';
        document.getElementById('container-status-tipo-inspecao').style.display = 'none';
    }
}

function closeModalFormTipoInspecao() {
    document.getElementById('modal-form-tipo-inspecao').style.display = 'none';
    document.getElementById('formTipoInspecao').reset();
}

async function salvarTipoInspecao(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarTipoInspecao');
    btn.disabled = true;

    const id = document.getElementById('tipoInspecaoId').value;
    const codigo = document.getElementById('codigoTipoInspecaoInput').value.trim().toUpperCase();
    const nome = document.getElementById('nomeTipoInspecaoInput').value.trim();
    const descricao = document.getElementById('descTipoInspecaoInput').value.trim();
    const duracao_dias = parseInt(document.getElementById('duracaoTipoInspecaoInput').value, 10) || 0;
    
    try {
        if (id) {
            const ativo = document.getElementById('ativoTipoInspecaoInput').value === 'true';
            await apiFetch(`/inspecoes/tipos/${id}`, {
                method: 'PATCH',
                body: { codigo, nome, descricao, duracao_dias, ativo }
            });
            showToast("Tipo atualizado com sucesso!", "success");
        } else {
            await apiFetch('/inspecoes/tipos', {
                method: 'POST',
                body: { codigo, nome, descricao, duracao_dias }
            });
            showToast("Tipo criado com sucesso!", "success");
        }
        closeModalFormTipoInspecao();
        carregarListaTiposInspecao();
    } catch(err) {
        showToast(err.message || "Erro ao salvar.", "error");
    } finally {
        btn.disabled = false;
    }
}

// ---- Tarefas do Template ----

let tipoInspecaoAtualId = null;

function openModalTarefasTemplate(tipoId) {
    tipoInspecaoAtualId = tipoId;
    const tipo = tiposInspecaoCache.find(x => x.id === tipoId);
    if(tipo) {
        document.getElementById('titulo-modal-tarefas').innerText = `Tarefas: ${tipo.codigo} - ${tipo.nome}`;
    }
    
    document.getElementById('tarefaTipoInspecaoId').value = tipoId;
    document.getElementById('modal-tarefas-template').style.display = 'flex';
    
    carregarListaTarefasTemplate();
    carregarOpcoesCatalogoTarefas();
}

function closeModalTarefasTemplate() {
    document.getElementById('modal-tarefas-template').style.display = 'none';
    document.getElementById('formNovaTarefa').reset();
    tipoInspecaoAtualId = null;
}

async function carregarListaTarefasTemplate() {
    if (!tipoInspecaoAtualId) return;
    
    const tbody = document.getElementById('lista-tarefas-template-body');
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 1rem;">Carregando...</td></tr>';

    try {
        tarefasTemplateCache = await apiFetch(`/inspecoes/tipos/${tipoInspecaoAtualId}/tarefas`);
        tbody.innerHTML = '';
        
        if(tarefasTemplateCache.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhuma tarefa cadastrada para este tipo.</td></tr>';
            // Sugere a ordem 1
            document.getElementById('tarefaOrdemInput').value = 1;
            return;
        }

        // Sugere a próxima ordem
        const maxOrdem = Math.max(...tarefasTemplateCache.map(t => t.ordem));
        document.getElementById('tarefaOrdemInput').value = maxOrdem + 1;

        tarefasTemplateCache.forEach(t => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-color)';
            tr.innerHTML = `
                <td style="padding: 0.75rem; text-align: center; font-weight: 600;">${t.ordem}</td>
                <td style="padding: 0.75rem;">${escapeHtml(t.tarefa_catalogo?.sistema || '---')}</td>
                <td style="padding: 0.75rem;">
                    <div style="font-weight: 500;">${escapeHtml(t.tarefa_catalogo?.titulo || '')}</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(t.tarefa_catalogo?.descricao || '')}</div>
                </td>
                <td style="padding: 0.75rem; text-align: center;">
                    ${t.obrigatoria ? '<span style="color:var(--status-danger); font-weight:bold;">Sim</span>' : '<span style="color:var(--text-secondary);">Não</span>'}
                </td>
                <td style="padding: 0.75rem; text-align: right;">
                    <button type="button" class="btn-icon btn-remover-tarefa" data-id="${t.id}" title="Remover" style="color: var(--status-danger);">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                </td>
            `;
            
            tr.querySelector('.btn-remover-tarefa').addEventListener('click', () => removerTarefaTemplate(t.id));
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar tarefas.</td></tr>';
    }
}

async function salvarTarefaTemplate(e) {
    e.preventDefault();
    if (!tipoInspecaoAtualId) return;
    
    const btn = document.getElementById('btnSalvarTarefaTemplate');
    btn.disabled = true;

    const ordem = parseInt(document.getElementById('tarefaOrdemInput').value);
    const tarefa_catalogo_id = document.getElementById('tarefaCatalogoSelect').value;
    const obrigatoria = document.getElementById('tarefaObrigatoriaInput').checked;

    if (!tarefa_catalogo_id) {
        showToast("Selecione uma tarefa do catálogo.", "error");
        btn.disabled = false;
        return;
    }

    try {
        await apiFetch(`/inspecoes/tipos/${tipoInspecaoAtualId}/tarefas`, {
            method: 'POST',
            body: { ordem, tarefa_catalogo_id, obrigatoria }
        });
        showToast("Tarefa adicionada!", "success");
        document.getElementById('formNovaTarefa').reset();
        carregarListaTarefasTemplate();
        // Manter a checkbox obrigatoria como true apos o reset
        document.getElementById('tarefaObrigatoriaInput').checked = true;
    } catch(err) {
        showToast(err.message || "Erro ao adicionar tarefa.", "error");
    } finally {
        btn.disabled = false;
    }
}

async function removerTarefaTemplate(tarefaId) {
    if (!tipoInspecaoAtualId) return;
    if (!confirm("Remover esta tarefa? O histórico de inspeções já abertas não será afetado.")) return;

    try {
        await apiFetch(`/inspecoes/tarefas-template/${tarefaId}`, {
            method: 'DELETE'
        });
        showToast("Tarefa removida.", "success");
        carregarListaTarefasTemplate();
    } catch(err) {
        showToast(err.message || "Erro ao remover.", "error");
    }
}

// ==========================================
// Módulo do Catálogo Global de Tarefas
// ==========================================

let tarefasCatalogoGeralCache = [];

function openModalCatalogoTarefas() {
    document.getElementById('modal-catalogo-tarefas').style.display = 'flex';
    carregarListaCatalogoTarefas();
}

function closeModalCatalogoTarefas() {
    document.getElementById('modal-catalogo-tarefas').style.display = 'none';
}

async function carregarListaCatalogoTarefas() {
    const tbody = document.getElementById('lista-tarefas-catalogo-body');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem;">Carregando...</td></tr>';

    try {
        tarefasCatalogoGeralCache = await apiFetch('/inspecoes/tarefas-catalogo?incluir_inativos=true');
        tbody.innerHTML = '';
        
        if(tarefasCatalogoGeralCache.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhuma tarefa cadastrada no catálogo.</td></tr>';
            return;
        }

        tarefasCatalogoGeralCache.forEach(t => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-color)';
            tr.innerHTML = `
                <td style="padding: 0.75rem;">${escapeHtml(t.sistema || '---')}</td>
                <td style="padding: 0.75rem;">
                    <div style="font-weight: 500;">${escapeHtml(t.titulo)}</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(t.descricao || '')}</div>
                </td>
                <td style="padding: 0.75rem; text-align: center;">
                    <span style="display: inline-block; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; background: ${t.ativa ? 'rgba(46, 204, 113, 0.1)' : 'rgba(231, 76, 60, 0.1)'}; color: ${t.ativa ? 'var(--status-ok)' : 'var(--status-danger)'};">${t.ativa ? 'Ativa' : 'Inativa'}</span>
                </td>
                <td style="padding: 0.75rem; text-align: right; display: flex; gap: 0.5rem; justify-content: flex-end;">
                    <button type="button" class="btn-icon btn-editar-tarefa-catalogo" data-id="${t.id}" title="Editar Tarefa" style="color: var(--text-color);">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    </button>
                    ${t.ativa ? `
                    <button type="button" class="btn-icon btn-desativar-tarefa-catalogo" data-id="${t.id}" title="Desativar Tarefa" style="color: var(--status-danger);">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                    ` : ''}
                </td>
            `;
            
            tr.querySelector('.btn-editar-tarefa-catalogo').addEventListener('click', () => openModalFormTarefaCatalogo(t.id));
            const btnDesativar = tr.querySelector('.btn-desativar-tarefa-catalogo');
            if (btnDesativar) {
                btnDesativar.addEventListener('click', () => desativarTarefaCatalogo(t.id));
            }
            
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar catálogo.</td></tr>';
    }
}

function openModalFormTarefaCatalogo(id = null) {
    document.getElementById('modal-form-tarefa-catalogo').style.display = 'flex';
    document.getElementById('formTarefaCatalogo').reset();
    
    if (id) {
        const t = tarefasCatalogoGeralCache.find(x => x.id === id);
        if (t) {
            document.getElementById('titulo-form-tarefa-catalogo').innerText = 'Editar Tarefa no Catálogo';
            document.getElementById('tarefaCatalogoId').value = t.id;
            document.getElementById('tituloTarefaCatalogoInput').value = t.titulo;
            document.getElementById('sistemaTarefaCatalogoInput').value = t.sistema || '';
            document.getElementById('descTarefaCatalogoInput').value = t.descricao || '';
            document.getElementById('container-status-tarefa-catalogo').style.display = 'block';
            document.getElementById('ativoTarefaCatalogoInput').value = t.ativa ? 'true' : 'false';
        }
    } else {
        document.getElementById('titulo-form-tarefa-catalogo').innerText = 'Nova Tarefa no Catálogo';
        document.getElementById('tarefaCatalogoId').value = '';
        document.getElementById('container-status-tarefa-catalogo').style.display = 'none';
    }
}

function closeModalFormTarefaCatalogo() {
    document.getElementById('modal-form-tarefa-catalogo').style.display = 'none';
    document.getElementById('formTarefaCatalogo').reset();
}

async function salvarTarefaCatalogo(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarTarefaCatalogo');
    btn.disabled = true;

    const id = document.getElementById('tarefaCatalogoId').value;
    const isEdit = !!id;

    const body = {
        titulo: document.getElementById('tituloTarefaCatalogoInput').value.trim(),
        sistema: document.getElementById('sistemaTarefaCatalogoInput').value.trim() || null,
        descricao: document.getElementById('descTarefaCatalogoInput').value.trim() || null
    };

    if (isEdit) {
        body.ativa = document.getElementById('ativoTarefaCatalogoInput').value === 'true';
    }

    try {
        await apiFetch(isEdit ? `/inspecoes/tarefas-catalogo/${id}` : '/inspecoes/tarefas-catalogo', {
            method: isEdit ? 'PUT' : 'POST',
            body: body
        });
        showToast(isEdit ? "Tarefa atualizada!" : "Tarefa criada!", "success");
        closeModalFormTarefaCatalogo();
        carregarListaCatalogoTarefas();
    } catch(err) {
        showToast(err.message || "Erro ao salvar tarefa.", "error");
    } finally {
        btn.disabled = false;
    }
}

// ==========================================
// Módulo de Calendário (Tipos de Evento)
// ==========================================

let tiposEventoCache = [];

function openModalCalendarioTipos() {
    const modal = document.getElementById('modal-calendario-tipos');
    modal.style.display = 'flex';
    carregarListaTiposEvento();
}

function closeModalCalendarioTipos() {
    const modal = document.getElementById('modal-calendario-tipos');
    if(modal) modal.style.display = 'none';
}

async function carregarListaTiposEvento() {
    const tbody = document.getElementById('lista-tipos-evento-body');
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 1rem;">Carregando categorias...</td></tr>';

    try {
        tiposEventoCache = await apiFetch('/api/v1/calendario/tipos?only_active=false');
        tbody.innerHTML = '';
        
        if(tiposEventoCache.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhuma categoria cadastrada.</td></tr>';
            return;
        }

        tiposEventoCache.forEach(t => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-color)';
            tr.innerHTML = `
                <td style="padding: 0.75rem;"><strong>${escapeHtml(t.name)}</strong></td>
                <td style="padding: 0.75rem; text-align: center; font-size: 1.25rem;">${escapeHtml(t.icon)}</td>
                <td style="padding: 0.75rem; text-align: center;">
                    <span style="font-size: 0.8rem; font-weight: 600; color: ${t.visibility_type === 'private' ? 'var(--status-warning)' : 'var(--status-ok)'};">
                        ${t.visibility_type === 'private' ? 'Sigiloso' : 'Público'}
                    </span>
                </td>
                <td style="padding: 0.75rem; text-align: center;">
                    <div style="width: 24px; height: 24px; border-radius: 4px; background: ${t.color}; margin: 0 auto; border: 1px solid rgba(0,0,0,0.1);" title="${t.color}"></div>
                </td>
                <td style="padding: 0.75rem; text-align: center;">
                    <span style="display: inline-block; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; background: ${t.active ? 'rgba(46, 204, 113, 0.1)' : 'rgba(231, 76, 60, 0.1)'}; color: ${t.active ? 'var(--status-ok)' : 'var(--status-danger)'}; cursor: pointer;" class="badge-status-evento" data-id="${t.id}">
                        ${t.active ? 'Ativo' : 'Inativo'}
                    </span>
                </td>
                <td style="padding: 0.75rem; text-align: right; display: flex; gap: 0.5rem; justify-content: flex-end;">
                    <button type="button" class="btn-icon btn-editar-tipo-evento" data-id="${t.id}" title="Editar Categoria" style="color: var(--primary-color);">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    </button>
                </td>
            `;
            
            tr.querySelector('.btn-editar-tipo-evento').addEventListener('click', () => openModalFormTipoEvento(t.id));
            tr.querySelector('.badge-status-evento').addEventListener('click', () => toggleStatusTipoEvento(t.id, t.active));
            
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar categorias.</td></tr>';
    }
}

function openModalFormTipoEvento(id = null) {
    document.getElementById('modal-form-tipo-evento').style.display = 'flex';
    document.getElementById('formTipoEvento').reset();
    
    if (id) {
        const t = tiposEventoCache.find(x => x.id === id);
        if (t) {
            document.getElementById('titulo-form-tipo-evento').innerText = 'Editar Categoria';
            document.getElementById('tipoEventoId').value = t.id;
            document.getElementById('nomeTipoEventoInput').value = t.name;
            document.getElementById('iconTipoEventoInput').value = t.icon;
            document.getElementById('sigiloTipoEventoInput').value = t.visibility_type;
            document.getElementById('colorTipoEventoInput').value = t.color;
            document.getElementById('privateColorTipoEventoInput').value = t.private_color || '#94a3b8';
            document.getElementById('container-status-tipo-evento').style.display = 'block';
            document.getElementById('ativoTipoEventoInput').value = t.active ? 'true' : 'false';
        }
    } else {
        document.getElementById('titulo-form-tipo-evento').innerText = 'Nova Categoria de Evento';
        document.getElementById('tipoEventoId').value = '';
        document.getElementById('container-status-tipo-evento').style.display = 'none';
        document.getElementById('colorTipoEventoInput').value = '#3b82f6';
        document.getElementById('privateColorTipoEventoInput').value = '#94a3b8';
    }
}

function closeModalFormTipoEvento() {
    document.getElementById('modal-form-tipo-evento').style.display = 'none';
}

async function salvarTipoEvento(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarTipoEvento');
    btn.disabled = true;

    const id = document.getElementById('tipoEventoId').value;
    const isEdit = !!id;

    const body = {
        name: document.getElementById('nomeTipoEventoInput').value.trim(),
        icon: document.getElementById('iconTipoEventoInput').value.trim(),
        visibility_type: document.getElementById('sigiloTipoEventoInput').value,
        color: document.getElementById('colorTipoEventoInput').value,
        private_color: document.getElementById('privateColorTipoEventoInput').value
    };

    if (isEdit) {
        body.active = document.getElementById('ativoTipoEventoInput').value === 'true';
    }

    try {
        await apiFetch(isEdit ? `/api/v1/calendario/tipos/${id}` : '/api/v1/calendario/tipos', {
            method: isEdit ? 'PUT' : 'POST',
            body: body
        });
        showToast(isEdit ? "Categoria atualizada!" : "Categoria criada com sucesso!", "success");
        closeModalFormTipoEvento();
        carregarListaTiposEvento();
    } catch(err) {
        showToast(err.message || "Erro ao salvar categoria.", "error");
    } finally {
        btn.disabled = false;
    }
}

async function toggleStatusTipoEvento(id, currentStatus) {
    if (!confirm(`Deseja ${currentStatus ? 'desativar' : 'ativar'} esta categoria?`)) return;
    
    try {
        await apiFetch(`/api/v1/calendario/tipos/${id}`, {
            method: 'PUT',
            body: { active: !currentStatus }
        });
        showToast(`Categoria ${currentStatus ? 'desativada' : 'ativada'}!`, "success");
        carregarListaTiposEvento();
    } catch(err) {
        showToast(err.message || "Erro ao alterar status.", "error");
    }
}

async function desativarTarefaCatalogo(id) {
    if (!confirm("Tem certeza que deseja inativar esta tarefa do catálogo global?")) return;

    try {
        await apiFetch(`/inspecoes/tarefas-catalogo/${id}`, { method: 'DELETE' });
        showToast("Tarefa inativada com sucesso!", "success");
        carregarListaCatalogoTarefas();
    } catch(err) {
        showToast(err.message || "Erro ao inativar tarefa.", "error");
    }
}

async function carregarOpcoesCatalogoTarefas() {
    const select = document.getElementById('tarefaCatalogoSelect');
    select.innerHTML = '<option value="">Carregando...</option>';

    try {
        const tarefas = await apiFetch('/inspecoes/tarefas-catalogo');
        select.innerHTML = '<option value="" disabled selected>Selecione uma tarefa ativa</option>';
        
        tarefas.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.text = `[${t.sistema || 'Geral'}] ${t.titulo}`;
            select.appendChild(opt);
        });
    } catch(e) {
        select.innerHTML = '<option value="" disabled selected>Erro ao carregar catálogo</option>';
    }
}

// ============================================================
// Upload XLSX Inventário
// ============================================================
(function () {
    const btnUpload = document.getElementById('btn-upload-xlsx');
    const modal = document.getElementById('modal-upload-xlsx');
    const btnClose = document.getElementById('btn-close-modal-xlsx');
    const btnCancel = document.getElementById('btn-cancel-modal-xlsx');
    const form = document.getElementById('formUploadXlsx');
    const fileInput = document.getElementById('xlsxFileInput');
    const resultadoDiv = document.getElementById('xlsx-resultado');
    const btnPrevia = document.getElementById('btnPreviaXlsx');
    const btnEnviar = document.getElementById('btnEnviarXlsx');

    let previewData = null;

    if (!btnUpload || !modal) return;

    function abrirModal() {
        modal.style.display = 'flex';
        form.reset();
        resultadoDiv.style.display = 'none';
        resultadoDiv.innerHTML = '';
        btnPrevia.style.display = 'inline-block';
        btnPrevia.disabled = false;
        btnPrevia.textContent = 'Carregar';
        btnEnviar.style.display = 'none';
        btnEnviar.disabled = false;
        btnEnviar.textContent = 'Enviar e Processar';
        previewData = null;
    }

    function fecharModal() {
        modal.style.display = 'none';
    }

    // Resetar estado se o usuário trocar o arquivo
    fileInput.addEventListener('change', () => {
        btnPrevia.style.display = 'inline-block';
        btnPrevia.disabled = false;
        btnPrevia.textContent = 'Carregar';
        btnEnviar.style.display = 'none';
        resultadoDiv.style.display = 'none';
        previewData = null;
    });

    btnUpload.addEventListener('click', abrirModal);
    btnClose.addEventListener('click', fecharModal);
    btnCancel.addEventListener('click', fecharModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) fecharModal();
    });

    // Passo 1: Carregar Prévia
    btnPrevia.addEventListener('click', async () => {
        const file = fileInput.files[0];
        if (!file) {
            showToast('Selecione um arquivo .xlsx.', 'error');
            return;
        }

        if (!file.name.toLowerCase().endsWith('.xlsx')) {
            showToast('Selecione um arquivo .xlsx válido.', 'error');
            return;
        }

        btnPrevia.disabled = true;
        btnPrevia.textContent = 'Lendo...';
        resultadoDiv.style.display = 'block';
        resultadoDiv.innerHTML = '<p>⏳ Analisando arquivo...</p>';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const data = await apiFetch('/equipamentos/inventario/upload-xlsx/preview', {
                method: 'POST',
                body: formData,
            });

            if (data.erros && data.erros.length > 0) {
                resultadoDiv.innerHTML = `<div style="color: var(--status-danger);">
                    <strong>Erros encontrados:</strong><br>
                    ${data.erros.map(e => `• ${e}`).join('<br>')}
                </div>`;
                btnPrevia.disabled = false;
                btnPrevia.textContent = 'Carregar';
                return;
            }

            previewData = data;

            // Montar relatório de prévia
            let html = `
                <h4 style="margin: 0 0 0.75rem;">Pré-visualização — Aeronave ${data.matricula}</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 1rem; background: rgba(0,0,0,0.05); padding: 0.75rem; border-radius: 4px;">
                    <div><strong>Total Slots:</strong> ${data.total_linhas}</div>
                    <div><strong>No XLSX:</strong> ${data.pns_encontrados}</div>
                    <div><strong>Não no XLSX:</strong> ${data.pns_ignorados}</div>
                </div>
                <div style="font-size: 0.8rem; border: 1px solid var(--border-color); border-radius: 4px; overflow: hidden;">
                    <!-- Cabeçalho Fixo -->
                    <table style="width: 100%; border-collapse: collapse; background: var(--bg-tertiary);">
                        <thead>
                            <tr style="border-bottom: 1px solid var(--border-color);">
                                <th style="padding: 8px 4px; text-align: left; width: 40%; font-weight: bold;">Posição</th>
                                <th style="padding: 8px 4px; text-align: left; width: 60%; font-weight: bold;">SN Encontrado</th>
                            </tr>
                        </thead>
                    </table>
                    <!-- Corpo Scrollable -->
                    <div style="max-height: 180px; overflow-y: auto;">
                        <table style="width: 100%; border-collapse: collapse; table-layout: fixed;">
                            <tbody>
                                ${data.itens.map(item => `
                                    <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                                        <td style="padding: 6px 4px; width: 40%; word-break: break-word;">${item.nome_posicao}</td>
                                        <td style="padding: 6px 4px; width: 60%; word-break: break-word; color: ${item.status === 'OK' ? 'var(--status-ok)' : item.status === 'REMOVED' ? 'var(--status-warning)' : 'var(--text-secondary)'};">
                                            ${item.status_msg}
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
                <p style="margin-top: 1rem; font-weight: 500; color: var(--primary-color);">Deseja processar e atualizar o banco de dados?</p>
            `;

            resultadoDiv.innerHTML = html;
            btnPrevia.style.display = 'none';
            btnEnviar.style.display = 'inline-block';

        } catch (err) {
            resultadoDiv.innerHTML = `<p style="color: var(--status-danger);">❌ Erro: ${err.message}</p>`;
            btnPrevia.disabled = false;
            btnPrevia.textContent = 'Carregar';
        }
    });

    // Passo 2: Processar e Persistir
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!previewData || !previewData.aeronave_id) {
            showToast('Dados de prévia não encontrados.', 'error');
            return;
        }

        btnEnviar.disabled = true;
        btnEnviar.textContent = 'Gravando...';

        const body = {
            aeronave_id: previewData.aeronave_id,
            itens: previewData.itens.map(it => ({
                slot_id: it.slot_id,
                sn_final: it.sn_encontrado
            }))
        };

        try {
            const data = await apiFetch('/equipamentos/inventario/upload-xlsx/process', {
                method: 'POST',
                body: body,
            });

            showToast(`Sucesso! ${data.itens_atualizados} itens atualizados.`, 'success');
            
            // Exibir resumo final
            resultadoDiv.innerHTML = `
                <div style="text-align: center; padding: 1rem;">
                    <div style="color: var(--status-ok); font-size: 2rem; margin-bottom: 0.5rem;">✅</div>
                    <h4 style="margin: 0;">Processamento Concluído</h4>
                    <p>${data.itens_atualizados} de ${data.total_linhas} slots foram atualizados para a aeronave ${previewData.matricula}.</p>
                </div>
            `;
            
            btnEnviar.style.display = 'none';
            setTimeout(fecharModal, 3000);

        } catch (err) {
            showToast(err.message || 'Erro ao processar inventário.', 'error');
            btnEnviar.disabled = false;
            btnEnviar.textContent = 'Enviar e Processar';
        }
    });
})();

