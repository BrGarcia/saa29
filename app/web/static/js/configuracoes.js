// @ts-check

/**
 * Scripts para a página de configurações.
 * Por enquanto serve de stub para as funcionalidades futuras.
 */

// Importamos tipos globais de app.js para autocompletação no editor
/** @typedef {import('./app.js').SAAUser} SAAUser */
/** @typedef {import('./app.js').Aeronave} Aeronave */

// Declaramos funções globais importadas do app.js
/** @type {typeof import('./app.js').apiFetch} */
const apiFetch = /** @type {any} */ (window).apiFetch;

/** @type {typeof import('./app.js').showToast} */
const showToast = /** @type {any} */ (window).showToast;

document.addEventListener("DOMContentLoaded", () => {
    // Verificação extra de segurança no frontend
    const userJson = localStorage.getItem("saa29_user");
    if (userJson) {
        try {
            /** @type {SAAUser} */
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
    
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formAeronave'));
    if(form) form.addEventListener('submit', criarAeronave);

    const btnAlterarStatus = document.getElementById('btn-alterar-status-aeronave');
    if(btnAlterarStatus) btnAlterarStatus.addEventListener('click', openModalStatus);
    
    const formStatus = /** @type {HTMLFormElement | null} */ (document.getElementById('formAlterarStatusAeronave'));
    if(formStatus) formStatus.addEventListener('submit', alterarStatusAeronave);

    const btnTiposControle = document.getElementById('btn-tipos-controle');
    if(btnTiposControle) btnTiposControle.addEventListener('click', openModalTipoControle);

    const formTipoControle = /** @type {HTMLFormElement | null} */ (document.getElementById('formTipoControle'));
    if(formTipoControle) formTipoControle.addEventListener('submit', salvarTipoControle);

    const btnEditarTipo = document.getElementById('btn-editar-tipo-controle');
    if(btnEditarTipo) btnEditarTipo.addEventListener('click', openModalEditarTipo);

    const formEditarTipo = /** @type {HTMLFormElement | null} */ (document.getElementById('formEditarTipoControle'));
    if(formEditarTipo) formEditarTipo.addEventListener('submit', salvarEditarTipo);

    const btnEquipamentoControle = document.getElementById('btn-equipamento-controle');
    if(btnEquipamentoControle) btnEquipamentoControle.addEventListener('click', openModalRegras);

    const formNovaRegra = /** @type {HTMLFormElement | null} */ (document.getElementById('formNovaRegra'));
    if(formNovaRegra) formNovaRegra.addEventListener('submit', salvarNovaRegra);

    const btnPN = document.getElementById('btn-gerenciar-catalogo');
    if(btnPN) btnPN.addEventListener('click', openModalCatalogo);

    const btnNovoPN = document.getElementById('btn-novo-pn');
    if(btnNovoPN) btnNovoPN.addEventListener('click', openModalNovoPN);

    const formNovoPN = /** @type {HTMLFormElement | null} */ (document.getElementById('formNovoPN'));
    if(formNovoPN) formNovoPN.addEventListener('submit', salvarNovoPN);

    const formEditarPN = /** @type {HTMLFormElement | null} */ (document.getElementById('formEditarPN'));
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

/**
 * Abre o modal de configuração de nova aeronave.
 * @returns {void}
 */
function openModalConfig() {
    const modalH3 = document.querySelector("#modal-aeronave h3");
    if (modalH3) {
        /** @type {HTMLElement} */ (modalH3).innerText = "Nova Aeronave";
    }
    const btnSalvar = document.getElementById("btnSalvarAcft");
    if (btnSalvar) {
        /** @type {HTMLElement} */ (btnSalvar).innerText = "Registrar";
    }
    const statusInput = /** @type {HTMLInputElement | null} */ (document.getElementById("statusInput"));
    if (statusInput) {
        statusInput.value = "DISPONIVEL";
        statusInput.disabled = false;
    }
    const modalAeronave = document.getElementById("modal-aeronave");
    if (modalAeronave) {
        modalAeronave.style.display = "flex";
    }
}

/**
 * Fecha o modal de configuração de aeronave e limpa o formulário.
 * @returns {void}
 */
function closeModalConfig() {
    const modalAeronave = document.getElementById("modal-aeronave");
    if (modalAeronave) {
        modalAeronave.style.display = "none";
    }
    const formAeronave = /** @type {HTMLFormElement | null} */ (document.getElementById("formAeronave"));
    if (formAeronave) {
        formAeronave.reset();
    }
}

/**
 * Cadastra uma nova aeronave no backend.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function criarAeronave(e) {
    e.preventDefault();
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById("btnSalvarAcft"));
    if (btn) btn.disabled = true;
    
    const matriculaInput = /** @type {HTMLInputElement | null} */ (document.getElementById("matriculaInput"));
    const snInput = /** @type {HTMLInputElement | null} */ (document.getElementById("snInput"));
    const statusInput = /** @type {HTMLInputElement | null} */ (document.getElementById("statusInput"));

    const matricula = matriculaInput ? matriculaInput.value.trim().toUpperCase() : "";
    const sn = snInput ? snInput.value.trim() : "";
    const status = statusInput ? statusInput.value : "";

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
        // @ts-ignore
        showToast(err.message || "Erro ao cadastrar aeronave.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

/** @type {any} */ (window).openModalConfig = openModalConfig;
/** @type {any} */ (window).closeModalConfig = closeModalConfig;

/**
 * Abre o modal de alteração de status de aeronave e carrega opções.
 * @returns {Promise<void>}
 */
async function openModalStatus() {
    const modalStatus = document.getElementById("modal-alterar-status-aeronave");
    if (modalStatus) modalStatus.style.display = "flex";
    
    const select = /** @type {HTMLSelectElement | null} */ (document.getElementById("aeronaveStatusSelect"));
    if (!select) return;
    
    select.innerHTML = '<option value="" disabled selected>Carregando aeronaves...</option>';
    
    try {
        /** @type {Aeronave[]} */
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

/**
 * Fecha o modal de alteração de status.
 * @returns {void}
 */
function closeModalStatus() {
    const modalStatus = document.getElementById("modal-alterar-status-aeronave");
    if (modalStatus) modalStatus.style.display = "none";
    const formStatus = /** @type {HTMLFormElement | null} */ (document.getElementById("formAlterarStatusAeronave"));
    if (formStatus) formStatus.reset();
}

/**
 * Envia a alteração de status da aeronave para o backend.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function alterarStatusAeronave(e) {
    e.preventDefault();
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById("btnConfirmarStatus"));
    const select = /** @type {HTMLSelectElement | null} */ (document.getElementById("aeronaveStatusSelect"));
    const novoStatusInput = /** @type {HTMLInputElement | null} */ (document.getElementById("novoStatusInput"));
    
    if (!select || !novoStatusInput) return;
    const novoStatus = novoStatusInput.value;
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
    
    if (btn) btn.disabled = true;
    
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
        // @ts-ignore
        showToast(err.message || "Erro ao alterar status.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

/** @type {any} */ (window).openModalStatus = openModalStatus;
/** @type {any} */ (window).closeModalStatus = closeModalStatus;

// ==========================================
// Módulo de Controles de Vencimento
// ==========================================

/**
 * Abre o modal para cadastrar novo tipo de controle.
 * @returns {void}
 */
function openModalTipoControle() {
    const modal = document.getElementById('modal-tipo-controle');
    if(modal) modal.style.display = 'flex';
}

/**
 * Fecha o modal de novo tipo de controle e limpa o formulário.
 * @returns {void}
 */
function closeModalTipoControle() {
    const modal = document.getElementById('modal-tipo-controle');
    if(modal) modal.style.display = 'none';
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formTipoControle'));
    if(form) form.reset();
}

/**
 * Salva o novo tipo de controle no backend.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function salvarTipoControle(e) {
    e.preventDefault();
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById("btnSalvarTipoControle"));
    if (btn) btn.disabled = true;

    const codigoInput = /** @type {HTMLInputElement | null} */ (document.getElementById("codigoControleInput"));
    const descInput = /** @type {HTMLInputElement | null} */ (document.getElementById("descControleInput"));

    const nome = codigoInput ? codigoInput.value.trim().toUpperCase() : "";
    const descricao = descInput ? descInput.value.trim() : "";

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
        // @ts-ignore
        showToast(err.message || "Erro ao cadastrar tipo de controle.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

/** @type {any} */ (window).openModalTipoControle = openModalTipoControle;
/** @type {any} */ (window).closeModalTipoControle = closeModalTipoControle;

// ---- Editar Tipo de Controle ----

/** @type {TipoControle[]} */
let tiposControleCache = [];

/**
 * Abre o modal de edição de tipo de controle e carrega as opções.
 * @returns {Promise<void>}
 */
async function openModalEditarTipo() {
    const modal = document.getElementById('modal-editar-tipo-controle');
    if (modal) modal.style.display = 'flex';
    
    const select = /** @type {HTMLSelectElement | null} */ (document.getElementById('editarTipoSelect'));
    if (!select) return;
    
    select.innerHTML = '<option value="" disabled selected>Carregando...</option>';
    
    const editarCodigoInput = /** @type {HTMLInputElement | null} */ (document.getElementById('editarCodigoInput'));
    const editarDescInput = /** @type {HTMLInputElement | null} */ (document.getElementById('editarDescInput'));
    
    if (editarCodigoInput) editarCodigoInput.value = '';
    if (editarDescInput) editarDescInput.value = '';

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
            if (editarCodigoInput) editarCodigoInput.value = tipo.nome;
            if (editarDescInput) editarDescInput.value = tipo.descricao || '';
        }
    });
}

/**
 * Fecha o modal de edição de tipo de controle e reseta o formulário.
 * @returns {void}
 */
function closeModalEditarTipo() {
    const modal = document.getElementById('modal-editar-tipo-controle');
    if(modal) modal.style.display = 'none';
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formEditarTipoControle'));
    if(form) form.reset();
}

/**
 * Salva a alteração do tipo de controle no backend.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function salvarEditarTipo(e) {
    e.preventDefault();
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById('btnSalvarEditarTipo'));
    const select = /** @type {HTMLSelectElement | null} */ (document.getElementById('editarTipoSelect'));
    const tipoId = select ? select.value : "";

    if(!tipoId) {
        showToast('Selecione um tipo de controle.', 'error');
        return;
    }

    if (btn) btn.disabled = true;
    const editarCodigoInput = /** @type {HTMLInputElement | null} */ (document.getElementById('editarCodigoInput'));
    const editarDescInput = /** @type {HTMLInputElement | null} */ (document.getElementById('editarDescInput'));
    
    const nome = editarCodigoInput ? editarCodigoInput.value.trim().toUpperCase() : "";
    const descricao = editarDescInput ? editarDescInput.value.trim() : "";

    try {
        await apiFetch(`/vencimentos/tipos-controle/${tipoId}`, {
            method: 'PUT',
            body: { nome, descricao }
        });
        showToast('Tipo de controle atualizado com sucesso!', 'success');
        closeModalEditarTipo();
    } catch(err) {
        // @ts-ignore
        showToast(err.message || 'Erro ao atualizar tipo de controle.', 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

/** @type {any} */ (window).openModalEditarTipo = openModalEditarTipo;
/** @type {any} */ (window).closeModalEditarTipo = closeModalEditarTipo;

// ---- Regras por Equipamento (Vencimentos) ----

/**
 * Abre o modal de gerenciamento de regras de periodicidade por equipamento.
 * @returns {Promise<void>}
 */
async function openModalRegras() {
    const modal = document.getElementById('modal-regras-equipamento');
    if (modal) modal.style.display = 'flex';
    await carregarOptionsRegras();
    await carregarListaRegras();
}

/**
 * Fecha o modal de regras de periodicidade.
 * @returns {void}
 */
function closeModalRegras() {
    const modal = document.getElementById('modal-regras-equipamento');
    if(modal) modal.style.display = 'none';
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formNovaRegra'));
    if(form) form.reset();
}

/**
 * Carrega as opções de PNs e tipos de controle nos selects do formulário de regras.
 * @returns {Promise<void>}
 */
async function carregarOptionsRegras() {
    const selectEquip = /** @type {HTMLSelectElement | null} */ (document.getElementById('regraEquipamentoSelect'));
    const selectTipo = /** @type {HTMLSelectElement | null} */ (document.getElementById('regraTipoSelect'));
    
    if (!selectEquip || !selectTipo) return;
    
    selectEquip.innerHTML = '<option value="">Carregando...</option>';
    selectTipo.innerHTML = '<option value="">Carregando...</option>';

    try {
        /** @type {[Equipamento[], TipoControle[]]} */
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

/**
 * Carrega e renderiza a tabela de regras de periodicidade.
 * @returns {Promise<void>}
 */
async function carregarListaRegras() {
    const tbody = document.getElementById('lista-regras-body');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem;">Carregando regras...</td></tr>';

    try {
        /** @type {RegraVencimento[]} */
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
                    const target = /** @type {HTMLElement} */ (e.currentTarget);
                    const mid = target.getAttribute('data-modelo') || "";
                    const tid = target.getAttribute('data-tipo') || "";
                    removerRegra(mid, tid);
                });
            }
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar lista.</td></tr>';
    }
}

/**
 * Salva uma nova regra de periodicidade por equipamento.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function salvarNovaRegra(e) {
    e.preventDefault();
    const formTarget = /** @type {HTMLFormElement} */ (e.target);
    const btn = /** @type {HTMLButtonElement | null} */ (formTarget.querySelector('button[type="submit"]'));
    if (btn) btn.disabled = true;

    const selectModelo = /** @type {HTMLSelectElement | null} */ (document.getElementById('regraEquipamentoSelect'));
    const selectTipo = /** @type {HTMLSelectElement | null} */ (document.getElementById('regraTipoSelect'));
    const inputMeses = /** @type {HTMLInputElement | null} */ (document.getElementById('regraMesesInput'));

    const modelo_id = selectModelo ? selectModelo.value : "";
    const tipo_controle_id = selectTipo ? selectTipo.value : "";
    const periodicidade_meses = inputMeses ? parseInt(inputMeses.value) : 0;

    try {
        await apiFetch('/vencimentos/regras', {
            method: 'POST',
            body: { modelo_id, tipo_controle_id, periodicidade_meses }
        });
        showToast("Regra cadastrada/atualizada com sucesso!", "success");
        await carregarListaRegras();
    } catch(err) {
        // @ts-ignore
        showToast(err.message || "Erro ao salvar regra.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

/**
 * Remove uma regra de periodicidade.
 * @param {string} modeloId
 * @param {string} tipoId
 * @returns {Promise<void>}
 */
async function removerRegra(modeloId, tipoId) {
    console.log("INÍCIO: removerRegra", {modeloId, tipoId});
    
    if(!confirm("Tem certeza que deseja remover esta regra de periodicidade?")) {
        console.log("CANCELADO: Usuário desistiu");
        return;
    }

    try {
        console.log("DISPARANDO: apiFetch DELETE...");
        await apiFetch(`/vencimentos/regras/${modeloId}/${tipoId}`, {
            method: 'DELETE'
        });

        console.log("SUCESSO: Regra removida");
        showToast("Regra removida com sucesso!", "success");
        await carregarListaRegras();
    } catch(err) {
        console.error("ERRO FATAL (Network/JS):", err);
    }
}

window.openModalRegras = openModalRegras;
window.closeModalRegras = closeModalRegras;
/** @type {any} */ (window).removerRegra = removerRegra;

// ==========================================
// Módulo de Catálogo (Part Numbers)
// ==========================================

/**
 * Abre o modal do catálogo de Part Numbers e lista os itens.
 * @returns {void}
 */
function openModalCatalogo() {
    const modal = document.getElementById('modal-catalogo');
    if (modal) modal.style.display = 'flex';
    carregarListaCatalogo();
}

/**
 * Fecha o modal do catálogo de Part Numbers.
 * @returns {void}
 */
function closeModalCatalogo() {
    const modal = document.getElementById('modal-catalogo');
    if(modal) modal.style.display = 'none';
}

/**
 * Abre o modal de cadastro de novo Part Number.
 * @returns {void}
 */
function openModalNovoPN() {
    const modal = document.getElementById('modal-novo-pn');
    if (modal) modal.style.display = 'flex';
}

/**
 * Fecha o modal de novo Part Number e limpa o formulário.
 * @returns {void}
 */
function closeModalNovoPN() {
    const modal = document.getElementById('modal-novo-pn');
    if (modal) modal.style.display = 'none';
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formNovoPN'));
    if (form) form.reset();
}

/** @type {Equipamento[]} */
let catalogoCache = [];

/**
 * Carrega a lista de Part Numbers do catálogo e renderiza a tabela.
 * @returns {Promise<void>}
 */
async function carregarListaCatalogo() {
    const tbody = document.getElementById('lista-catalogo-body');
    if (!tbody) return;
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
            
            const btnEdit = tr.querySelector('.btn-editar-pn');
            if (btnEdit) btnEdit.addEventListener('click', () => openModalEditarPN(m.id));
            
            const btnRemove = tr.querySelector('.btn-remover-pn');
            if (btnRemove) btnRemove.addEventListener('click', () => removerPN(m.id, m.part_number));
            
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar catálogo.</td></tr>';
    }
}

/**
 * Salva um novo Part Number no catálogo.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function salvarNovoPN(e) {
    e.preventDefault();
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById('btnSalvarPN'));
    if (btn) btn.disabled = true;

    const pnInput = /** @type {HTMLInputElement | null} */ (document.getElementById('pnInput'));
    const nomePnInput = /** @type {HTMLInputElement | null} */ (document.getElementById('nomePnInput'));
    const descPnInput = /** @type {HTMLInputElement | null} */ (document.getElementById('descPnInput'));

    const part_number = pnInput ? pnInput.value.trim().toUpperCase() : "";
    const nome_generico = nomePnInput ? nomePnInput.value.trim() : "";
    const descricao = descPnInput ? descPnInput.value.trim() : "";

    try {
        await apiFetch('/equipamentos/', {
            method: 'POST',
            body: { part_number, nome_generico, descricao }
        });
        showToast("Part Number cadastrado com sucesso!", "success");
        closeModalNovoPN();
        const modalCatalogo = document.getElementById('modal-catalogo');
        if (modalCatalogo && modalCatalogo.style.display === 'flex') {
            carregarListaCatalogo();
        }
    } catch(err) {
        // @ts-ignore
        showToast(err.message || "Erro ao cadastrar PN.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

/**
 * Abre o modal de edição de um Part Number específico.
 * @param {string} id
 * @returns {void}
 */
function openModalEditarPN(id) {
    const pn = catalogoCache.find(m => m.id === id);
    if (!pn) return;

    const inputId = /** @type {HTMLInputElement | null} */ (document.getElementById('editarPnId'));
    const inputPn = /** @type {HTMLInputElement | null} */ (document.getElementById('editarPnInput'));
    const inputNome = /** @type {HTMLInputElement | null} */ (document.getElementById('editarNomePnInput'));
    const inputDesc = /** @type {HTMLInputElement | null} */ (document.getElementById('editarDescPnInput'));

    if (inputId) inputId.value = pn.id;
    if (inputPn) inputPn.value = pn.part_number;
    if (inputNome) inputNome.value = pn.nome_generico;
    if (inputDesc) inputDesc.value = pn.descricao || '';
    
    const modal = document.getElementById('modal-editar-pn');
    if (modal) modal.style.display = 'flex';
}

/**
 * Fecha o modal de edição de Part Number e limpa o formulário.
 * @returns {void}
 */
function closeModalEditarPN() {
    const modal = document.getElementById('modal-editar-pn');
    if (modal) modal.style.display = 'none';
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formEditarPN'));
    if (form) form.reset();
}

/**
 * Salva as alterações de um Part Number no catálogo.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function salvarEditarPN(e) {
    e.preventDefault();
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById('btnSalvarEditarPN'));
    const inputId = /** @type {HTMLInputElement | null} */ (document.getElementById('editarPnId'));
    const id = inputId ? inputId.value : "";
    
    if (btn) btn.disabled = true;
    
    const inputPn = /** @type {HTMLInputElement | null} */ (document.getElementById('editarPnInput'));
    const inputNome = /** @type {HTMLInputElement | null} */ (document.getElementById('editarNomePnInput'));
    const inputDesc = /** @type {HTMLInputElement | null} */ (document.getElementById('editarDescPnInput'));

    const part_number = inputPn ? inputPn.value.trim().toUpperCase() : "";
    const nome_generico = inputNome ? inputNome.value.trim() : "";
    const descricao = inputDesc ? inputDesc.value.trim() : "";

    try {
        await apiFetch(`/equipamentos/${id}`, {
            method: 'PATCH',
            body: { part_number, nome_generico, descricao }
        });
        showToast("Part Number updated successfully!", "success");
        closeModalEditarPN();
        carregarListaCatalogo();
    } catch(err) {
        // @ts-ignore
        showToast(err.message || "Erro ao atualizar PN.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

/**
 * Remove um Part Number do catálogo.
 * @param {string} id
 * @param {string} pn
 * @returns {Promise<void>}
 */
async function removerPN(id, pn) {
    if (!confirm(`Tem certeza que deseja remover o PN ${pn}? Esta ação pode afetar itens vinculados.`)) {
        return;
    }

    try {
        await apiFetch(`/equipamentos/${id}`, { method: 'DELETE' });
        showToast("Part Number removido com sucesso!", "success");
        carregarListaCatalogo();
    } catch(err) {
        // @ts-ignore
        showToast(err.message || "Erro ao remover PN.", "error");
    }
}

window.openModalCatalogo = openModalCatalogo;
window.closeModalCatalogo = closeModalCatalogo;
/** @type {any} */ (window).openModalEditarPN = openModalEditarPN;
/** @type {any} */ (window).closeModalEditarPN = closeModalEditarPN;
/** @type {any} */ (window).salvarEditarPN = salvarEditarPN;
/** @type {any} */ (window).removerPN = removerPN;

// ==========================================
// Módulo de Inspeções (Tipos e Tarefas)
// ==========================================

/** @type {TipoInspecao[]} */
let tiposInspecaoCache = [];
/** @type {any[]} */
let tarefasTemplateCache = [];

/**
 * Abre o modal de visualização de tipos de inspeção.
 * @returns {void}
 */
function openModalTiposInspecao() {
    const modal = document.getElementById('modal-inspecoes-tipos');
    if (modal) modal.style.display = 'flex';
    carregarListaTiposInspecao();
}

/**
 * Fecha o modal de tipos de inspeção.
 * @returns {void}
 */
function closeModalTiposInspecao() {
    const modal = document.getElementById('modal-inspecoes-tipos');
    if(modal) modal.style.display = 'none';
}

/**
 * Carrega a lista de tipos de inspeção do servidor e preenche a tabela.
 * @returns {Promise<void>}
 */
async function carregarListaTiposInspecao() {
    const tbody = document.getElementById('lista-tipos-inspecao-body');
    if (!tbody) return;
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
                    ${t.duracao_dias && t.duracao_dias > 0 ? `<span title="Duração">${t.duracao_dias}d</span>` : '<span style="color:var(--text-secondary)">—</span>'}
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
            
            const btnTarefas = tr.querySelector('.btn-tarefas-tipo');
            if (btnTarefas) btnTarefas.addEventListener('click', () => openModalTarefasTemplate(t.id));
            
            const btnEdit = tr.querySelector('.btn-editar-tipo-insp');
            if (btnEdit) btnEdit.addEventListener('click', () => openModalFormTipoInspecao(t.id));
            
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar tipos de inspeção.</td></tr>';
    }
}

/**
 * Abre o modal de cadastro/edição de um tipo de inspeção.
 * @param {string | null} [id] - ID do tipo de inspeção (opcional para edição)
 * @returns {void}
 */
function openModalFormTipoInspecao(id = null) {
    const modal = document.getElementById('modal-form-tipo-inspecao');
    if (modal) modal.style.display = 'flex';
    
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formTipoInspecao'));
    if (form) form.reset();
    
    const inputId = /** @type {HTMLInputElement | null} */ (document.getElementById('tipoInspecaoId'));
    const inputCodigo = /** @type {HTMLInputElement | null} */ (document.getElementById('codigoTipoInspecaoInput'));
    const inputNome = /** @type {HTMLInputElement | null} */ (document.getElementById('nomeTipoInspecaoInput'));
    const inputDesc = /** @type {HTMLInputElement | null} */ (document.getElementById('descTipoInspecaoInput'));
    const inputDuracao = /** @type {HTMLInputElement | null} */ (document.getElementById('duracaoTipoInspecaoInput'));
    const selectAtivo = /** @type {HTMLSelectElement | null} */ (document.getElementById('ativoTipoInspecaoInput'));
    
    const title = document.getElementById('titulo-form-tipo-inspecao');
    const containerStatus = document.getElementById('container-status-tipo-inspecao');

    if (id) {
        const t = tiposInspecaoCache.find(x => x.id === id);
        if (t) {
            if (title) title.innerText = 'Editar Tipo de Inspeção';
            if (inputId) inputId.value = t.id;
            if (inputCodigo) inputCodigo.value = t.codigo;
            if (inputNome) inputNome.value = t.nome;
            if (inputDesc) inputDesc.value = t.descricao || '';
            if (inputDuracao) inputDuracao.value = String(t.duracao_dias ?? 0);
            if (containerStatus) containerStatus.style.display = 'block';
            if (selectAtivo) selectAtivo.value = t.ativo ? 'true' : 'false';
        }
    } else {
        if (title) title.innerText = 'Novo Tipo de Inspeção';
        if (inputId) inputId.value = '';
        if (containerStatus) containerStatus.style.display = 'none';
    }
}

/**
 * Fecha o modal de formulário de tipo de inspeção.
 * @returns {void}
 */
function closeModalFormTipoInspecao() {
    const modal = document.getElementById('modal-form-tipo-inspecao');
    if (modal) modal.style.display = 'none';
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formTipoInspecao'));
    if (form) form.reset();
}

/**
 * Salva ou atualiza um tipo de inspeção.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function salvarTipoInspecao(e) {
    e.preventDefault();
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById('btnSalvarTipoInspecao'));
    if (btn) btn.disabled = true;

    const inputId = /** @type {HTMLInputElement | null} */ (document.getElementById('tipoInspecaoId'));
    const inputCodigo = /** @type {HTMLInputElement | null} */ (document.getElementById('codigoTipoInspecaoInput'));
    const inputNome = /** @type {HTMLInputElement | null} */ (document.getElementById('nomeTipoInspecaoInput'));
    const inputDesc = /** @type {HTMLInputElement | null} */ (document.getElementById('descTipoInspecaoInput'));
    const inputDuracao = /** @type {HTMLInputElement | null} */ (document.getElementById('duracaoTipoInspecaoInput'));
    const selectAtivo = /** @type {HTMLSelectElement | null} */ (document.getElementById('ativoTipoInspecaoInput'));

    const id = inputId ? inputId.value : "";
    const codigo = inputCodigo ? inputCodigo.value.trim().toUpperCase() : "";
    const nome = inputNome ? inputNome.value.trim() : "";
    const descricao = inputDesc ? inputDesc.value.trim() : "";
    const duracao_dias = inputDuracao ? (parseInt(inputDuracao.value, 10) || 0) : 0;
    
    try {
        if (id) {
            const ativo = selectAtivo ? selectAtivo.value === 'true' : true;
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
        // @ts-ignore
        showToast(err.message || "Erro ao salvar.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ---- Tarefas do Template ----

/** @type {string | null} */
let tipoInspecaoAtualId = null;

/**
 * Abre o modal de gerenciamento de tarefas associadas a um tipo de inspeção.
 * @param {string} tipoId
 * @returns {void}
 */
function openModalTarefasTemplate(tipoId) {
    tipoInspecaoAtualId = tipoId;
    const tipo = tiposInspecaoCache.find(x => x.id === tipoId);
    const title = document.getElementById('titulo-modal-tarefas');
    if(tipo && title) {
        title.innerText = `Tarefas: ${tipo.codigo} - ${tipo.nome}`;
    }
    
    const inputId = /** @type {HTMLInputElement | null} */ (document.getElementById('tarefaTipoInspecaoId'));
    if (inputId) inputId.value = tipoId;
    
    const modal = document.getElementById('modal-tarefas-template');
    if (modal) modal.style.display = 'flex';
    
    carregarListaTarefasTemplate();
    carregarOpcoesCatalogoTarefas();
}

/**
 * Fecha o modal de tarefas associadas ao template.
 * @returns {void}
 */
function closeModalTarefasTemplate() {
    const modal = document.getElementById('modal-tarefas-template');
    if (modal) modal.style.display = 'none';
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formNovaTarefa'));
    if (form) form.reset();
    tipoInspecaoAtualId = null;
}

/**
 * Carrega a lista de tarefas associadas ao tipo de inspeção atual.
 * @returns {Promise<void>}
 */
async function carregarListaTarefasTemplate() {
    if (!tipoInspecaoAtualId) return;
    
    const tbody = document.getElementById('lista-tarefas-template-body');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 1rem;">Carregando...</td></tr>';

    const inputOrdem = /** @type {HTMLInputElement | null} */ (document.getElementById('tarefaOrdemInput'));

    try {
        tarefasTemplateCache = await apiFetch(`/inspecoes/tipos/${tipoInspecaoAtualId}/tarefas`);
        tbody.innerHTML = '';
        
        if(tarefasTemplateCache.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhuma tarefa cadastrada para este tipo.</td></tr>';
            if (inputOrdem) inputOrdem.value = "1";
            return;
        }

        const maxOrdem = Math.max(...tarefasTemplateCache.map(t => t.ordem));
        if (inputOrdem) inputOrdem.value = String(maxOrdem + 1);

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
            
            const btnRemove = tr.querySelector('.btn-remover-tarefa');
            if (btnRemove) btnRemove.addEventListener('click', () => removerTarefaTemplate(t.id));
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar tarefas.</td></tr>';
    }
}

/**
 * Salva uma nova tarefa no template da inspeção.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function salvarTarefaTemplate(e) {
    e.preventDefault();
    if (!tipoInspecaoAtualId) return;
    
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById('btnSalvarTarefaTemplate'));
    if (btn) btn.disabled = true;

    const inputOrdem = /** @type {HTMLInputElement | null} */ (document.getElementById('tarefaOrdemInput'));
    const selectCatalogo = /** @type {HTMLSelectElement | null} */ (document.getElementById('tarefaCatalogoSelect'));
    const checkObrigatoria = /** @type {HTMLInputElement | null} */ (document.getElementById('tarefaObrigatoriaInput'));

    const ordem = inputOrdem ? parseInt(inputOrdem.value) : 0;
    const tarefa_catalogo_id = selectCatalogo ? selectCatalogo.value : "";
    const obrigatoria = checkObrigatoria ? checkObrigatoria.checked : true;

    if (!tarefa_catalogo_id) {
        showToast("Selecione uma tarefa do catálogo.", "error");
        if (btn) btn.disabled = false;
        return;
    }

    try {
        await apiFetch(`/inspecoes/tipos/${tipoInspecaoAtualId}/tarefas`, {
            method: 'POST',
            body: { ordem, tarefa_catalogo_id, obrigatoria }
        });
        showToast("Tarefa adicionada!", "success");
        const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formNovaTarefa'));
        if (form) form.reset();
        carregarListaTarefasTemplate();
        if (checkObrigatoria) checkObrigatoria.checked = true;
    } catch(err) {
        // @ts-ignore
        showToast(err.message || "Erro ao adicionar tarefa.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

/**
 * Remove uma tarefa do template.
 * @param {string} tarefaId
 * @returns {Promise<void>}
 */
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
        // @ts-ignore
        showToast(err.message || "Erro ao remover.", "error");
    }
}

// ==========================================
// Módulo do Catálogo Global de Tarefas
// ==========================================

/** @type {any[]} */
let tarefasCatalogoGeralCache = [];

/**
 * Abre o modal do catálogo de tarefas e carrega a listagem.
 * @returns {void}
 */
function openModalCatalogoTarefas() {
    const modal = document.getElementById('modal-catalogo-tarefas');
    if (modal) modal.style.display = 'flex';
    carregarListaCatalogoTarefas();
}

/**
 * Fecha o modal do catálogo de tarefas.
 * @returns {void}
 */
function closeModalCatalogoTarefas() {
    const modal = document.getElementById('modal-catalogo-tarefas');
    if (modal) modal.style.display = 'none';
}

/**
 * Carrega a lista de tarefas do catálogo global e monta a tabela.
 * @returns {Promise<void>}
 */
async function carregarListaCatalogoTarefas() {
    const tbody = document.getElementById('lista-tarefas-catalogo-body');
    if (!tbody) return;
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
            
            const btnEdit = tr.querySelector('.btn-editar-tarefa-catalogo');
            if (btnEdit) btnEdit.addEventListener('click', () => openModalFormTarefaCatalogo(t.id));
            
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

/**
 * Abre o modal de cadastro/edição de tarefa no catálogo global.
 * @param {string | null} [id] - ID da tarefa do catálogo (opcional para edição)
 * @returns {void}
 */
function openModalFormTarefaCatalogo(id = null) {
    const modal = document.getElementById('modal-form-tarefa-catalogo');
    if (modal) modal.style.display = 'flex';
    
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formTarefaCatalogo'));
    if (form) form.reset();
    
    const inputId = /** @type {HTMLInputElement | null} */ (document.getElementById('tarefaCatalogoId'));
    const inputTitulo = /** @type {HTMLInputElement | null} */ (document.getElementById('tituloTarefaCatalogoInput'));
    const inputSistema = /** @type {HTMLInputElement | null} */ (document.getElementById('sistemaTarefaCatalogoInput'));
    const inputDesc = /** @type {HTMLInputElement | null} */ (document.getElementById('descTarefaCatalogoInput'));
    const selectAtivo = /** @type {HTMLSelectElement | null} */ (document.getElementById('ativoTarefaCatalogoInput'));

    const title = document.getElementById('titulo-form-tarefa-catalogo');
    const containerStatus = document.getElementById('container-status-tarefa-catalogo');

    if (id) {
        const t = tarefasCatalogoGeralCache.find(x => x.id === id);
        if (t) {
            if (title) title.innerText = 'Editar Tarefa no Catálogo';
            if (inputId) inputId.value = t.id;
            if (inputTitulo) inputTitulo.value = t.titulo;
            if (inputSistema) inputSistema.value = t.sistema || '';
            if (inputDesc) inputDesc.value = t.descricao || '';
            if (containerStatus) containerStatus.style.display = 'block';
            if (selectAtivo) selectAtivo.value = t.ativa ? 'true' : 'false';
        }
    } else {
        if (title) title.innerText = 'Nova Tarefa no Catálogo';
        if (inputId) inputId.value = '';
        if (containerStatus) containerStatus.style.display = 'none';
    }
}

/**
 * Fecha o modal do formulário de tarefa do catálogo.
 * @returns {void}
 */
function closeModalFormTarefaCatalogo() {
    const modal = document.getElementById('modal-form-tarefa-catalogo');
    if (modal) modal.style.display = 'none';
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formTarefaCatalogo'));
    if (form) form.reset();
}

/**
 * Salva ou edita uma tarefa no catálogo global.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function salvarTarefaCatalogo(e) {
    e.preventDefault();
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById('btnSalvarTarefaCatalogo'));
    if (btn) btn.disabled = true;

    const inputId = /** @type {HTMLInputElement | null} */ (document.getElementById('tarefaCatalogoId'));
    const inputTitulo = /** @type {HTMLInputElement | null} */ (document.getElementById('tituloTarefaCatalogoInput'));
    const inputSistema = /** @type {HTMLInputElement | null} */ (document.getElementById('sistemaTarefaCatalogoInput'));
    const inputDesc = /** @type {HTMLInputElement | null} */ (document.getElementById('descTarefaCatalogoInput'));
    const selectAtivo = /** @type {HTMLSelectElement | null} */ (document.getElementById('ativoTarefaCatalogoInput'));

    const id = inputId ? inputId.value : "";
    const isEdit = !!id;

    const body = {
        titulo: inputTitulo ? inputTitulo.value.trim() : "",
        sistema: inputSistema ? (inputSistema.value.trim() || null) : null,
        descricao: inputDesc ? (inputDesc.value.trim() || null) : null,
        ativa: true
    };

    if (isEdit && selectAtivo) {
        body.ativa = selectAtivo.value === 'true';
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
        // @ts-ignore
        showToast(err.message || "Erro ao salvar tarefa.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ==========================================
// Módulo de Calendário (Tipos de Evento)
// ==========================================

/** @type {any[]} */
let tiposEventoCache = [];

/**
 * Abre o modal de categorias de eventos do calendário.
 * @returns {void}
 */
function openModalCalendarioTipos() {
    const modal = document.getElementById('modal-calendario-tipos');
    if (modal) modal.style.display = 'flex';
    carregarListaTiposEvento();
}

/**
 * Fecha o modal de categorias de eventos.
 * @returns {void}
 */
function closeModalCalendarioTipos() {
    const modal = document.getElementById('modal-calendario-tipos');
    if(modal) modal.style.display = 'none';
}

/**
 * Carrega a lista de categorias de eventos do calendário e popula a tabela.
 * @returns {Promise<void>}
 */
async function carregarListaTiposEvento() {
    const tbody = document.getElementById('lista-tipos-evento-body');
    if (!tbody) return;
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
            
            const btnEdit = tr.querySelector('.btn-editar-tipo-evento');
            if (btnEdit) btnEdit.addEventListener('click', () => openModalFormTipoEvento(t.id));
            
            const badge = tr.querySelector('.badge-status-evento');
            if (badge) badge.addEventListener('click', () => toggleStatusTipoEvento(t.id, t.active));
            
            tbody.appendChild(tr);
        });
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar categorias.</td></tr>';
    }
}

/**
 * Abre o modal de cadastro/edição de tipo de evento do calendário.
 * @param {string | null} [id] - ID do tipo de evento (opcional para edição)
 * @returns {void}
 */
function openModalFormTipoEvento(id = null) {
    const modal = document.getElementById('modal-form-tipo-evento');
    if (modal) modal.style.display = 'flex';
    
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formTipoEvento'));
    if (form) form.reset();
    
    const inputId = /** @type {HTMLInputElement | null} */ (document.getElementById('tipoEventoId'));
    const inputNome = /** @type {HTMLInputElement | null} */ (document.getElementById('nomeTipoEventoInput'));
    const inputIcon = /** @type {HTMLInputElement | null} */ (document.getElementById('iconTipoEventoInput'));
    const selectSigilo = /** @type {HTMLSelectElement | null} */ (document.getElementById('sigiloTipoEventoInput'));
    const inputColor = /** @type {HTMLInputElement | null} */ (document.getElementById('colorTipoEventoInput'));
    const inputPrivColor = /** @type {HTMLInputElement | null} */ (document.getElementById('privateColorTipoEventoInput'));
    const selectAtivo = /** @type {HTMLSelectElement | null} */ (document.getElementById('ativoTipoEventoInput'));
    
    const title = document.getElementById('titulo-form-tipo-evento');
    const containerStatus = document.getElementById('container-status-tipo-evento');

    if (id) {
        const t = tiposEventoCache.find(x => x.id === id);
        if (t) {
            if (title) title.innerText = 'Editar Categoria';
            if (inputId) inputId.value = t.id;
            if (inputNome) inputNome.value = t.name;
            if (inputIcon) inputIcon.value = t.icon;
            if (selectSigilo) selectSigilo.value = t.visibility_type;
            if (inputColor) inputColor.value = t.color;
            if (inputPrivColor) inputPrivColor.value = t.private_color || '#94a3b8';
            if (containerStatus) containerStatus.style.display = 'block';
            if (selectAtivo) selectAtivo.value = t.active ? 'true' : 'false';
        }
    } else {
        if (title) title.innerText = 'Nova Categoria de Evento';
        if (inputId) inputId.value = '';
        if (containerStatus) containerStatus.style.display = 'none';
        if (inputColor) inputColor.value = '#3b82f6';
        if (inputPrivColor) inputPrivColor.value = '#94a3b8';
    }
}

/**
 * Fecha o modal de formulário de tipo de evento.
 * @returns {void}
 */
function closeModalFormTipoEvento() {
    const modal = document.getElementById('modal-form-tipo-evento');
    if (modal) modal.style.display = 'none';
}

/**
 * Salva ou edita a categoria de evento do calendário.
 * @param {SubmitEvent} e
 * @returns {Promise<void>}
 */
async function salvarTipoEvento(e) {
    e.preventDefault();
    const btn = /** @type {HTMLButtonElement | null} */ (document.getElementById('btnSalvarTipoEvento'));
    if (btn) btn.disabled = true;

    const inputId = /** @type {HTMLInputElement | null} */ (document.getElementById('tipoEventoId'));
    const inputNome = /** @type {HTMLInputElement | null} */ (document.getElementById('nomeTipoEventoInput'));
    const inputIcon = /** @type {HTMLInputElement | null} */ (document.getElementById('iconTipoEventoInput'));
    const selectSigilo = /** @type {HTMLSelectElement | null} */ (document.getElementById('sigiloTipoEventoInput'));
    const inputColor = /** @type {HTMLInputElement | null} */ (document.getElementById('colorTipoEventoInput'));
    const inputPrivColor = /** @type {HTMLInputElement | null} */ (document.getElementById('privateColorTipoEventoInput'));
    const selectAtivo = /** @type {HTMLSelectElement | null} */ (document.getElementById('ativoTipoEventoInput'));

    const id = inputId ? inputId.value : "";
    const isEdit = !!id;

    const body = {
        name: inputNome ? inputNome.value.trim() : "",
        icon: inputIcon ? inputIcon.value.trim() : "",
        visibility_type: selectSigilo ? selectSigilo.value : "public",
        color: inputColor ? inputColor.value : "#3b82f6",
        private_color: inputPrivColor ? inputPrivColor.value : "#94a3b8",
        active: true
    };

    if (isEdit && selectAtivo) {
        body.active = selectAtivo.value === 'true';
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
        // @ts-ignore
        showToast(err.message || "Erro ao salvar categoria.", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

/**
 * Ativa/desativa uma categoria de evento.
 * @param {string} id
 * @param {boolean} currentStatus
 * @returns {Promise<void>}
 */
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
        // @ts-ignore
        showToast(err.message || "Erro ao alterar status.", "error");
    }
}

/**
 * Inativa uma tarefa do catálogo global.
 * @param {string} id
 * @returns {Promise<void>}
 */
async function desativarTarefaCatalogo(id) {
    if (!confirm("Tem certeza que deseja inativar esta tarefa do catálogo global?")) return;

    try {
        await apiFetch(`/inspecoes/tarefas-catalogo/${id}`, { method: 'DELETE' });
        showToast("Tarefa inativada com sucesso!", "success");
        carregarListaCatalogoTarefas();
    } catch(err) {
        // @ts-ignore
        showToast(err.message || "Erro ao inativar tarefa.", "error");
    }
}

/**
 * Carrega a lista de tarefas do catálogo e preenche o select de seleção de tarefas.
 * @returns {Promise<void>}
 */
async function carregarOpcoesCatalogoTarefas() {
    const select = /** @type {HTMLSelectElement | null} */ (document.getElementById('tarefaCatalogoSelect'));
    if (!select) return;
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
    const btnUpload = /** @type {HTMLButtonElement | null} */ (document.getElementById('btn-upload-xlsx'));
    const modal = /** @type {HTMLElement | null} */ (document.getElementById('modal-upload-xlsx'));
    const btnClose = /** @type {HTMLButtonElement | null} */ (document.getElementById('btn-close-modal-xlsx'));
    const btnCancel = /** @type {HTMLButtonElement | null} */ (document.getElementById('btn-cancel-modal-xlsx'));
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById('formUploadXlsx'));
    const fileInput = /** @type {HTMLInputElement | null} */ (document.getElementById('xlsxFileInput'));
    const resultadoDiv = /** @type {HTMLDivElement | null} */ (document.getElementById('xlsx-resultado'));
    const btnPrevia = /** @type {HTMLButtonElement | null} */ (document.getElementById('btnPreviaXlsx'));
    const btnEnviar = /** @type {HTMLButtonElement | null} */ (document.getElementById('btnEnviarXlsx'));

    /** @type {any} */
    let previewData = null;

    if (!btnUpload || !modal || !form || !fileInput || !resultadoDiv || !btnPrevia || !btnEnviar || !btnClose || !btnCancel) return;

    /**
     * Abre o modal de upload do XLSX e reseta os estados.
     * @returns {void}
     */
    function abrirModal() {
        if (modal) modal.style.display = 'flex';
        if (form) form.reset();
        if (resultadoDiv) {
            resultadoDiv.style.display = 'none';
            resultadoDiv.innerHTML = '';
        }
        if (btnPrevia) {
            btnPrevia.style.display = 'inline-block';
            btnPrevia.disabled = false;
            btnPrevia.textContent = 'Carregar';
        }
        if (btnEnviar) {
            btnEnviar.style.display = 'none';
            btnEnviar.disabled = false;
            btnEnviar.textContent = 'Enviar e Processar';
        }
        previewData = null;
    }

    /**
     * Fecha o modal de upload do XLSX.
     * @returns {void}
     */
    function fecharModal() {
        if (modal) modal.style.display = 'none';
    }

    // Resetar estado se o usuário trocar o arquivo
    fileInput.addEventListener('change', () => {
        if (btnPrevia) {
            btnPrevia.style.display = 'inline-block';
            btnPrevia.disabled = false;
            btnPrevia.textContent = 'Carregar';
        }
        if (btnEnviar) btnEnviar.style.display = 'none';
        if (resultadoDiv) resultadoDiv.style.display = 'none';
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
        if (!fileInput.files) return;
        const file = fileInput.files[0];
        if (!file) {
            showToast('Selecione um arquivo .xlsx.', 'error');
            return;
        }

        if (!file.name.toLowerCase().endsWith('.xlsx')) {
            showToast('Selecione um arquivo .xlsx válido.', 'error');
            return;
        }

        if (btnPrevia) {
            btnPrevia.disabled = true;
            btnPrevia.textContent = 'Lendo...';
        }
        if (resultadoDiv) {
            resultadoDiv.style.display = 'block';
            resultadoDiv.innerHTML = '<p>⏳ Analisando arquivo...</p>';
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const data = await apiFetch('/equipamentos/inventario/upload-xlsx/preview', {
                method: 'POST',
                body: formData,
            });

            if (data.erros && data.erros.length > 0) {
                if (resultadoDiv) {
                    resultadoDiv.innerHTML = `<div style="color: var(--status-danger);">
                        <strong>Erros encontrados:</strong><br>
                        ${data.erros.map((/** @type {string} */ e) => `• ${e}`).join('<br>')}
                    </div>`;
                }
                if (btnPrevia) {
                    btnPrevia.disabled = false;
                    btnPrevia.textContent = 'Carregar';
                }
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
                                ${data.itens.map((/** @type {any} */ item) => `
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

            if (resultadoDiv) resultadoDiv.innerHTML = html;
            if (btnPrevia) btnPrevia.style.display = 'none';
            if (btnEnviar) btnEnviar.style.display = 'inline-block';

        } catch (err) {
            // @ts-ignore
            if (resultadoDiv) resultadoDiv.innerHTML = `<p style="color: var(--status-danger);">❌ Erro: ${err.message}</p>`;
            if (btnPrevia) {
                btnPrevia.disabled = false;
                btnPrevia.textContent = 'Carregar';
            }
        }
    });

    // Passo 2: Processar e Persistir
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!previewData || !previewData.aeronave_id) {
            showToast('Dados de prévia não encontrados.', 'error');
            return;
        }

        if (btnEnviar) {
            btnEnviar.disabled = true;
            btnEnviar.textContent = 'Gravando...';
        }

        const body = {
            aeronave_id: previewData.aeronave_id,
            itens: previewData.itens.map((/** @type {any} */ it) => ({
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
            if (resultadoDiv) {
                resultadoDiv.innerHTML = `
                    <div style="text-align: center; padding: 1rem;">
                        <div style="color: var(--status-ok); font-size: 2rem; margin-bottom: 0.5rem;">✅</div>
                        <h4 style="margin: 0;">Processamento Concluído</h4>
                        <p>${data.itens_atualizados} de ${data.total_linhas} slots foram atualizados para a aeronave ${previewData.matricula}.</p>
                    </div>
                `;
            }
            
            if (btnEnviar) btnEnviar.style.display = 'none';
            setTimeout(fecharModal, 3000);

        } catch (err) {
            // @ts-ignore
            showToast(err.message || 'Erro ao processar inventário.', 'error');
            if (btnEnviar) {
                btnEnviar.disabled = false;
                btnEnviar.textContent = 'Enviar e Processar';
            }
        }
    });
})();
