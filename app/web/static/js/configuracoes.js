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
    if(btnNova) btnNova.onclick = openModalConfig;
    
    const form = document.getElementById('formAeronave');
    if(form) form.addEventListener('submit', criarAeronave);

    const btnAlterarStatus = document.getElementById('btn-alterar-status-aeronave');
    if(btnAlterarStatus) btnAlterarStatus.onclick = openModalStatus;
    
    const formStatus = document.getElementById('formAlterarStatusAeronave');
    if(formStatus) formStatus.addEventListener('submit', alterarStatusAeronave);

    const btnTiposControle = document.getElementById('btn-tipos-controle');
    if(btnTiposControle) btnTiposControle.onclick = openModalTipoControle;

    const formTipoControle = document.getElementById('formTipoControle');
    if(formTipoControle) formTipoControle.addEventListener('submit', salvarTipoControle);

    const btnEditarTipo = document.getElementById('btn-editar-tipo-controle');
    if(btnEditarTipo) btnEditarTipo.onclick = openModalEditarTipo;

    const formEditarTipo = document.getElementById('formEditarTipoControle');
    if(formEditarTipo) formEditarTipo.addEventListener('submit', salvarEditarTipo);

    const btnEquipamentoControle = document.getElementById('btn-equipamento-controle');
    if(btnEquipamentoControle) btnEquipamentoControle.onclick = openModalRegras;

    const formNovaRegra = document.getElementById('formNovaRegra');
    if(formNovaRegra) formNovaRegra.addEventListener('submit', salvarNovaRegra);

    const btnCatalogo = document.getElementById('btn-gerenciar-catalogo');
    if(btnCatalogo) btnCatalogo.onclick = openModalCatalogo;

    const formPN = document.getElementById('formNovoPN');
    if(formPN) formPN.addEventListener('submit', salvarNovoModelo);
});

function openModalConfig() {
    document.querySelector("#modal-aeronave h3").innerText = "Nova Aeronave";
    document.getElementById("btnSalvarAcft").innerText = "Registrar";
    document.getElementById("statusInput").value = "OPERACIONAL";
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
        // Verificar se já existe a matrícula antes de salvar
        const existentes = await apiFetch(`/aeronaves/?limit=1000&incluir_inativas=true`);
        const jaExiste = existentes.some(a => a.matricula === matricula);
        
        if (jaExiste) {
            showToast(`A matrícula ${matricula} já está cadastrada no sistema.`, "error");
            btn.disabled = false;
            return;
        }

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

    const matricula = select.options[select.selectedIndex].text.split(' ')[0];
    
    if (!confirm(`Deseja alterar o status da aeronave ${matricula} para ${novoStatus}?`)) {
        return;
    }
    
    btn.disabled = true;
    
    try {
        // Usamos PUT para atualizar o status diretamente
        // Nota: O endpoint PUT /aeronaves/{id} aceita o campo 'status'
        await apiFetch(`/aeronaves/${aeronaveId}`, { 
            method: "PUT",
            body: {
                status: novoStatus
            }
        });
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
        await apiFetch("/equipamentos/tipos-controle", {
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
        tiposControleCache = await apiFetch('/equipamentos/tipos-controle');
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

    select.onchange = function() {
        const tipo = tiposControleCache.find(t => t.id === this.value);
        if(tipo) {
            document.getElementById('editarCodigoInput').value = tipo.nome;
            document.getElementById('editarDescInput').value = tipo.descricao || '';
        }
    };
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
        await apiFetch(`/equipamentos/tipos-controle/${tipoId}`, {
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
            apiFetch('/equipamentos/tipos-controle')
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
        const regras = await apiFetch('/equipamentos/controles/regras');
        tbody.innerHTML = '';
        
        if(regras.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhuma regra configurada.</td></tr>';
            return;
        }

        regras.forEach(r => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-color)';
            tr.innerHTML = `
                <td style="padding: 0.75rem;">${r.pn || '---'}</td>
                <td style="padding: 0.75rem; text-align: center;"><strong>${r.tipo_nome || '---'}</strong></td>
                <td style="padding: 0.75rem; text-align: center;">${r.periodicidade_meses} meses</td>
                <td style="padding: 0.75rem; text-align: right;">
                    <button class="btn-icon" style="color: var(--status-danger);" onclick="removerRegra('${r.modelo_id}', '${r.tipo_controle_id}')">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                </td>
            `;
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
        await apiFetch('/equipamentos/controles/regras', {
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
    if(!confirm("Tem certeza que deseja remover esta regra de periodicidade?")) return;

    try {
        await apiFetch(`/equipamentos/controles/regras/${modeloId}/${tipoId}`, {
            method: 'DELETE'
        });
        showToast("Regra removida com sucesso!", "success");
        await carregarListaRegras();
    } catch(err) {
        showToast(err.message || "Erro ao remover regra.", "error");
    }
}

window.openModalRegras = openModalRegras;
window.closeModalRegras = closeModalRegras;
window.removerRegra = removerRegra;

// ==========================================
// Módulo de Catálogo (Part Numbers)
// ==========================================

async function openModalCatalogo() {
    const modal = document.getElementById('modal-catalogo');
    modal.style.display = 'flex';
    await carregarListaCatalogo();
}

function closeModalCatalogo() {
    const modal = document.getElementById('modal-catalogo');
    if(modal) modal.style.display = 'none';
    const form = document.getElementById('formNovoPN');
    if(form) form.reset();
}

async function carregarListaCatalogo() {
    const tbody = document.getElementById('lista-catalogo-body');
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding: 1rem;">Carregando catálogo...</td></tr>';

    try {
        const modelos = await apiFetch('/equipamentos/');
        tbody.innerHTML = '';
        
        if(modelos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhum equipamento cadastrado.</td></tr>';
            return;
        }

        modelos.forEach(m => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border-color)';
            tr.innerHTML = `
                <td style="padding: 0.75rem;"><strong>${m.part_number}</strong></td>
                <td style="padding: 0.75rem;">${m.nome_generico}</td>
                <td style="padding: 0.75rem; color: var(--text-secondary); font-size: 0.85rem;">${m.descricao || '---'}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar catálogo.</td></tr>';
    }
}

async function salvarNovoModelo(e) {
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
        document.getElementById('formNovoPN').reset();
        await carregarListaCatalogo();
    } catch(err) {
        showToast(err.message || "Erro ao cadastrar PN.", "error");
    } finally {
        btn.disabled = false;
    }
}

window.openModalCatalogo = openModalCatalogo;
window.closeModalCatalogo = closeModalCatalogo;
window.salvarNovoModelo = salvarNovoModelo;
