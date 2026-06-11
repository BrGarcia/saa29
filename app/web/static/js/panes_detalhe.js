// @ts-check

/**
 * @typedef {Object} PaneDetalheDTO
 * @property {string} id
 * @property {string} codigo
 * @property {string} [sistema_ata_id]
 * @property {{descricao: string}} [sistema_ata]
 * @property {string} descricao
 * @property {{posto: string, nome: string}} [criador]
 * @property {string} data_abertura
 * @property {{matricula: string}} [aeronave]
 * @property {string} [comentarios]
 * @property {boolean} ativo
 * @property {string} status
 * @property {string} [observacao_conclusao]
 * @property {{posto?: string, nome?: string, trigrama?: string, username?: string}} [concluido_por]
 */

/**
 * @typedef {Object} AnexoDTO
 * @property {string} id
 * @property {string} tipo
 */

let ehGestorGlobal = false;
/** @type {string | null} */
let PANE_ID = null;
let paneSomenteLeitura = false;

/**
 * @returns {void}
 */
function acaoBloqueadaPaneInativa() {
    // @ts-ignore
    showToast("Pane excluída: ação indisponível enquanto estiver na lixeira.", "info");
}

/**
 * @returns {Promise<void>}
 */
async function carregarDetalhe() {
    try {
        /** @type {PaneDetalheDTO} */
        // @ts-ignore
        const pane = await apiFetch(`/panes/${PANE_ID}`);
        paneSomenteLeitura = !pane.ativo;

        // Textos base e Cabeçalho (Matrícula)
        const detId = document.getElementById("det-id");
        if(detId) detId.innerText = pane.codigo || "---/--";
        
        const detSistema = document.getElementById("det-sistema");
        if(detSistema) {
            detSistema.innerText = pane.sistema_ata ? pane.sistema_ata.descricao : "Não especificado";
            // Guardamos o id para usar na edição se necessário
            detSistema.dataset.id = pane.sistema_ata_id || "";
        }
        
        const detDescricao = document.getElementById("det-descricao");
        if(detDescricao) detDescricao.innerText = pane.descricao;

        // Relator
        const relator = pane.criador;
        const detRelator = document.getElementById("det-relator");
        if (detRelator) {
            if (relator) {
                const postoNome = [relator.posto, relator.nome].filter(Boolean).join(" ");
                detRelator.innerText = postoNome;
            } else {
                detRelator.innerText = "Não registrado";
            }
        }

        // Formatar Data e Hora
        const detData = document.getElementById("det-data");
        if (detData) {
            if (pane.data_abertura) {
                const dObj = new Date(pane.data_abertura);
                const fullDate = dObj.toLocaleString('pt-BR', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit'
                });
                detData.innerText = fullDate;
            } else {
                detData.innerText = "--";
            }
        }

        // Popula a matrícula da aeronave no cabeçalho
        const matricula = pane.aeronave?.matricula || "59XX";
        const detMatricula = document.getElementById("det-matricula");
        if(detMatricula) detMatricula.innerText = `Aeronave ${matricula}`;

        // Botões de fluxo e Status badge
        /** @type {HTMLButtonElement | null} */
        const btnConc = document.querySelector("#btn-concluir");
        /** @type {HTMLButtonElement | null} */
        const btnDelegar = document.querySelector("#btn-delegar");
        /** @type {HTMLButtonElement | null} */
        const btnEditOcorrencia = document.querySelector("#btn-edit-ocorrencia");
        const spanSts = document.getElementById("det-status");
        /** @type {HTMLFormElement | null} */
        const formUp = document.querySelector("#formUpload");

        /** @type {HTMLTextAreaElement | null} */
        const resInput = document.querySelector("#resolucao-texto");
        const resStatus = document.getElementById("status-resolucao-salva");
        const divAssinatura = document.getElementById("det-assinatura");
        /** @type {HTMLTextAreaElement | null} */
        const comInput = document.querySelector("#comentarios-texto");
        const alertaInativa = document.getElementById("det-inativa-alerta");
        /** @type {HTMLButtonElement | null} */
        const btnSalvarComentarios = document.querySelector("#btn-salvar-comentarios");

        if(btnConc) btnConc.style.display = "none";
        if(btnDelegar) btnDelegar.style.display = "none";
        if(btnEditOcorrencia) btnEditOcorrencia.style.display = "none";
        if(formUp) formUp.style.display = "flex";
        if(resInput) resInput.disabled = false;
        if(resStatus) resStatus.style.display = "none";
        if(divAssinatura) divAssinatura.style.display = "none";
        if(alertaInativa) alertaInativa.style.display = "none";
        if(btnSalvarComentarios) {
            btnSalvarComentarios.style.display = "inline-flex";
            btnSalvarComentarios.disabled = false;
        }
        if(comInput) {
            comInput.value = pane.comentarios || "";
            comInput.disabled = false;
        }

        const localUserJson = localStorage.getItem("saa29_user");
        const localUser = localUserJson ? JSON.parse(localUserJson) : {};
        // @ts-ignore
        ehGestorGlobal = window.hasPermission ? window.hasPermission('ENCARREGADO') : false;

        let bClass = "badge-aberta";
        let statusLabel = (pane.status || "").replace("_", " ");
        if (paneSomenteLeitura) {
            bClass = "badge-resolvida";
            statusLabel = "EXCLUIDA";
            if(formUp) formUp.style.display = "none";
            if(resInput) {
                resInput.disabled = true;
                resInput.value = pane.observacao_conclusao || "";
            }
            if(comInput) comInput.disabled = true;
            if(btnSalvarComentarios) btnSalvarComentarios.style.display = "none";
            if(alertaInativa) alertaInativa.style.display = "block";
        } else if (pane.status === "RESOLVIDA") {
            bClass = "badge-resolvida";
            if(formUp) formUp.style.display = "none";
            if(resInput) resInput.disabled = true;

            if (pane.observacao_conclusao && resInput && resStatus) {
                resInput.value = pane.observacao_conclusao;
                resStatus.style.display = "block";
                resStatus.innerText = "Ação Corretiva Finalizada e Assinada.";
            }

            if (pane.concluido_por && divAssinatura) {
                divAssinatura.style.display = "block";
                const u = pane.concluido_por;
                const postoNome = [u.posto, u.nome].filter(Boolean).join(" ");
                // @ts-ignore
                divAssinatura.innerHTML = `<strong>Finalizado por:</strong> ${escapeHtml(postoNome)} (${escapeHtml(u.trigrama || u.username || '')})`;
            }
        } else if (pane.status === "ABERTA") {
            if(btnConc) btnConc.style.display = "block";
            if (ehGestorGlobal) {
                if(btnDelegar) btnDelegar.style.display = "block";
                if(btnEditOcorrencia) btnEditOcorrencia.style.display = "block";
            }
            if(resInput) resInput.value = pane.observacao_conclusao || "";
        }

        if(spanSts) spanSts.innerHTML = `<span class="badge ${bClass}">${statusLabel}</span>`;

        carregarAnexos();

    } catch (e) {
        console.error(e);
        // @ts-ignore
        showToast("Falha ao recuperar informações da Pane.", "error");
    }
}

/**
 * @returns {Promise<void>}
 */
async function handleSalvarComentarios() {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    /** @type {HTMLTextAreaElement | null} */
    const comInput = document.querySelector("#comentarios-texto");
    const comentarios = comInput ? comInput.value.trim() : "";
    
    /** @type {HTMLButtonElement | null} */
    const btn = document.querySelector("#btn-salvar-comentarios");
    const statusMsg = document.getElementById("status-comentarios-salvo");

    if(btn) {
        btn.disabled = true;
        btn.innerText = "Salvando...";
    }
    if(statusMsg) statusMsg.style.display = "none";

    try {
        // @ts-ignore
        await apiFetch(`/panes/${PANE_ID}`, {
            method: "PUT",
            body: { comentarios: comentarios }
        });

        // @ts-ignore
        showToast("Observações salvas com sucesso!", "success");
        if(statusMsg) {
            statusMsg.style.display = "block";
            setTimeout(() => { statusMsg.style.display = "none"; }, 3000);
        }
    } catch (e) {
        console.error(e);
        // @ts-ignore
        showToast("Erro ao salvar observações.", "error");
    } finally {
        if(btn) {
            btn.disabled = false;
            btn.innerText = "Salvar Comentário";
        }
    }
}

/**
 * @returns {Promise<void>}
 */
async function handleConcluirDireto() {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    /** @type {HTMLTextAreaElement | null} */
    const resInput = document.querySelector("#resolucao-texto");
    const obs = resInput ? resInput.value.trim() : "";
    
    if (!obs) {
        // @ts-ignore
        showToast("Por favor, descreva a ação corretiva antes de concluir.", "error");
        if(resInput) resInput.focus();
        return;
    }

    /** @type {HTMLButtonElement | null} */
    const btn = document.querySelector("#btn-concluir");
    if(btn) {
        btn.disabled = true;
        btn.innerText = "Processando...";
    }

    try {
        // @ts-ignore
        await apiFetch(`/panes/${PANE_ID}/concluir`, {
            method: "POST",
            body: { observacao_conclusao: obs }
        });

        // @ts-ignore
        showToast("Pane finalizada com sucesso!", "success");
        carregarDetalhe();
    } catch (e) {
        if(btn) {
            btn.disabled = false;
            btn.innerText = "Concluir e Assinar";
        }
    }
}

/**
 * @returns {void}
 */
function openConcluirModal() { 
    const modal = document.getElementById("modal-concluir");
    if(modal) modal.style.display = "flex"; 
}

/**
 * @returns {void}
 */
function closeConcluirModal() { 
    const modal = document.getElementById("modal-concluir");
    if(modal) modal.style.display = "none"; 
}

/**
 * @param {Event} e
 * @returns {Promise<void>}
 */
async function enviarConclusao(e) {
    e.preventDefault();
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    /** @type {HTMLTextAreaElement | null} */
    const obsInput = document.querySelector("#obsConclusao");
    const obs = obsInput ? obsInput.value : "";
    try {
        // @ts-ignore
        await apiFetch(`/panes/${PANE_ID}/concluir`, {
            method: "POST",
            body: { observacao_conclusao: obs }
        });

        // @ts-ignore
        showToast("Pane finalizada e assinada.", "success");
        closeConcluirModal();
        carregarDetalhe();
    } catch (e) { }
}

/** @type {any[]} */
let usuariosParaDelegar = [];

/**
 * @returns {Promise<void>}
 */
async function openDelegarModal() {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    const modal = document.getElementById("modal-delegar");
    if(modal) modal.style.display = "flex";
    
    /** @type {HTMLSelectElement | null} */
    const select = document.querySelector("#mantenedorSelect");
    if(!select) return;
    
    select.innerHTML = '<option value="">Carregando...</option>';
    try {
        // @ts-ignore
        const usuarios = await apiFetch("/auth/usuarios");
        usuariosParaDelegar = usuarios;
        const possiveis = usuarios.filter(u => u.funcao === "MANTENEDOR" || u.funcao === "ENCARREGADO");
        select.innerHTML = '<option value="">-- Selecione o Servidor --</option>';
        possiveis.forEach(u => {
            const opt = document.createElement("option");
            opt.value = u.id;
            opt.innerText = `${u.posto} ${u.nome} (${u.especialidade})`;
            select.appendChild(opt);
        });
    } catch (e) {
        select.innerHTML = '<option value="">Falha ao carregar servidores.</option>';
    }
}

/**
 * @returns {void}
 */
function closeDelegarModal() { 
    const modal = document.getElementById("modal-delegar");
    if(modal) modal.style.display = "none"; 
}

/**
 * @param {Event} e
 * @returns {Promise<void>}
 */
async function enviarDelegacao(e) {
    e.preventDefault();
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    /** @type {HTMLSelectElement | null} */
    const select = document.querySelector("#mantenedorSelect");
    const mantId = select ? select.value : "";
    if (!mantId) return;

    const usuarioSelecionado = usuariosParaDelegar.find(u => u.id === mantId);
    const papelAtribuir = usuarioSelecionado ? usuarioSelecionado.funcao : "MANTENEDOR";

    try {
        // @ts-ignore
        await apiFetch(`/panes/${PANE_ID}/responsaveis`, {
            method: "POST",
            body: { usuario_id: mantId, papel: papelAtribuir }
        });
        // @ts-ignore
        showToast("Pane delegada com sucesso.", "success");
        closeDelegarModal();
    } catch (e) { }
}

/**
 * @returns {Promise<void>}
 */
async function openEditarModal() {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    
    /** @type {HTMLSelectElement | null} */
    const editSistema = document.querySelector("#editSistema");
    if(!editSistema) return;
    
    editSistema.innerHTML = '<option value="">Carregando...</option>';
    
    try {
        // @ts-ignore
        const sistemas = await apiFetch("/panes/sistemas");
        editSistema.innerHTML = '<option value="">-- Selecione o Sistema --</option>';
        sistemas.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.id;
            opt.innerText = `${s.codigo} - ${s.descricao}`;
            editSistema.appendChild(opt);
        });
        const detSistema = document.getElementById("det-sistema");
        editSistema.value = detSistema ? (detSistema.dataset.id || "") : "";
    } catch(e) { console.error(e) }

    /** @type {HTMLTextAreaElement | null} */
    const editDescricao = document.querySelector("#editDescricao");
    const detDescricao = document.getElementById("det-descricao");
    if(editDescricao && detDescricao) editDescricao.value = detDescricao.innerText;
    
    const modal = document.getElementById("modal-editar");
    if(modal) modal.style.display = "flex";
}

/**
 * @returns {void}
 */
function closeEditarModal() { 
    const modal = document.getElementById("modal-editar");
    if(modal) modal.style.display = "none"; 
}

/**
 * @param {Event} e
 * @returns {Promise<void>}
 */
async function salvarEdicao(e) {
    e.preventDefault();
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    /** @type {HTMLSelectElement | null} */
    const editSistema = document.querySelector("#editSistema");
    const sistema = editSistema ? editSistema.value : "";
    
    /** @type {HTMLTextAreaElement | null} */
    const editDescricao = document.querySelector("#editDescricao");
    const descricao = editDescricao ? editDescricao.value : "";

    try {
        // @ts-ignore
        await apiFetch(`/panes/${PANE_ID}`, {
            method: "PUT",
            body: { sistema_ata_id: sistema || null, descricao: descricao }
        });
        // @ts-ignore
        showToast("Dados atualizados com sucesso.", "success");
        closeEditarModal();
        carregarDetalhe();
    } catch (e) { }
}

/**
 * @returns {Promise<void>}
 */
async function carregarAnexos() {
    try {
        /** @type {AnexoDTO[]} */
        // @ts-ignore
        const anexos = await apiFetch(`/panes/${PANE_ID}/anexos`);
        const lista = document.getElementById("lista-anexos");
        if(!lista) return;
        
        lista.innerHTML = "";

        if (anexos.length === 0) {
            lista.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-secondary); text-align: center;">Sem arquivos vinculados.</p>`;
            return;
        }

        anexos.forEach(ax => {
            const div = document.createElement("div");
            div.style.display = "flex";
            div.style.alignItems = "center";
            div.style.justifyContent = "space-between";
            div.style.padding = "0.5rem";
            div.style.background = "var(--bg-primary)";
            div.style.borderRadius = "var(--radius-md)";
            div.style.fontSize = "0.85rem";
            div.style.border = "1px solid var(--border-color)";

            let btnExcluir = '';
            if (ehGestorGlobal && !paneSomenteLeitura) {
                btnExcluir = `
                    <button type="button" class="btn-icon btn-excluir-anexo" style="color: var(--status-error); width: 28px; height: 28px; background: transparent;" title="Excluir Anexo">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                `;
            }

            div.innerHTML = `
               <span style="font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px;" title="Anexo_${ax.id}">
                   📎 Anexo_${ax.id.substring(0, 4)}
               </span>
               <div style="display: flex; gap: 0.25rem; align-items: center;">
                   <button type="button" class="badge btn-abrir-anexo" style="background: var(--bg-tertiary); color: var(--text-primary); cursor: pointer; border: none; font-size: 0.7rem;">VISUALIZAR</button>
                   ${btnExcluir}
               </div>
           `;
            
            const btnAbrir = div.querySelector('.btn-abrir-anexo');
            if(btnAbrir) btnAbrir.addEventListener('click', () => abrirAnexo(ax.id, ax.tipo));
            
            const btnExcluirTrigger = div.querySelector('.btn-excluir-anexo');
            if(btnExcluirTrigger) {
                btnExcluirTrigger.addEventListener('click', () => handleExcluirAnexo(ax.id));
            }

            lista.appendChild(div);
        });
    } catch (e) { }
}

/**
 * @param {string} anexoId
 * @returns {Promise<void>}
 */
async function handleExcluirAnexo(anexoId) {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    if (!confirm("Deseja realmente excluir este anexo?")) return;
    try {
        // @ts-ignore
        await apiFetch(`/panes/${PANE_ID}/anexos/${anexoId}`, { method: "DELETE" });
        // @ts-ignore
        showToast("Anexo removido com sucesso.", "success");
        carregarAnexos();
    } catch (e) {
        console.error(e);
        // @ts-ignore
        showToast("Erro ao excluir anexo.", "error");
    }
}

/**
 * @returns {void}
 */
function closeAnexoModal() {
    const modalAnexo = document.getElementById("modal-anexo");
    if(modalAnexo) modalAnexo.style.display = "none";
    // @ts-ignore
    if (window.currentAnexoUrl) {
        // @ts-ignore
        URL.revokeObjectURL(window.currentAnexoUrl);
        // @ts-ignore
        window.currentAnexoUrl = null;
    }
    const content = document.getElementById("anexo-content");
    if(content) content.innerHTML = "";
}

/**
 * @param {string} anexoId
 * @param {string} tipoAnexo
 * @returns {Promise<void>}
 */
async function abrirAnexo(anexoId, tipoAnexo) {
    const modalAnexo = document.getElementById("modal-anexo");
    const anexoContent = document.getElementById("anexo-content");
    if(!modalAnexo || !anexoContent) return;
    
    modalAnexo.style.display = "flex";
    anexoContent.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">Carregando arquivo...</p>';

    try {
        const downloadUrl = `/panes/${PANE_ID}/anexos/${anexoId}/download`;

        if (tipoAnexo === "IMAGEM") {
            anexoContent.innerHTML = `<img src="${downloadUrl}" style="max-width: 100%; max-height: 80vh; object-fit: contain; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">`;
        } else if (tipoAnexo === "DOCUMENTO") {
            anexoContent.innerHTML = `<iframe src="${downloadUrl}" style="width: 100%; height: 80vh; border: none;"></iframe>`;
        } else {
            anexoContent.innerHTML = `
                <div style="text-align: center; color: var(--text-primary);">
                    <p style="margin-bottom: 1.5rem;">O arquivo não pode ser visualizado diretamente no navegador.</p>
                    <a href="${downloadUrl}" download="anexo" class="btn btn-primary" target="_blank">Baixar Arquivo</a>
                </div>
            `;
        }
    } catch (e) {
        console.error(e);
        // @ts-ignore
        showToast("Falha ao abrir anexo.", "error");
        closeAnexoModal();
    }
}

/**
 * @param {Event} e
 * @returns {Promise<void>}
 */
async function handleUpload(e) {
    e.preventDefault();
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    /** @type {HTMLInputElement | null} */
    const input = document.querySelector("#arquivoInput");
    if (!input || !input.files || input.files.length === 0) return;

    const formData = new FormData();
    formData.append("arquivo", input.files[0]);

    /** @type {HTMLButtonElement | null} */
    const btn = document.querySelector("#btnUpload");
    if(btn) btn.disabled = true;

    try {
        // @ts-ignore
        await apiFetch(`/panes/${PANE_ID}/anexos`, {
            method: "POST",
            body: formData
        });

        // @ts-ignore
        showToast("Evidência anexada.", "success");
        input.value = "";
        carregarAnexos();
    } catch (err) {
        // @ts-ignore
        showToast(err.message, "error");
    } finally {
        if(btn) btn.disabled = false;
    }
}

// Global scope exposed functions
// @ts-ignore
window.openConcluirModal = openConcluirModal;
// @ts-ignore
window.closeConcluirModal = closeConcluirModal;
// @ts-ignore
window.openDelegarModal = openDelegarModal;
// @ts-ignore
window.closeDelegarModal = closeDelegarModal;
// @ts-ignore
window.openEditarModal = openEditarModal;
// @ts-ignore
window.closeEditarModal = closeEditarModal;
// @ts-ignore
window.closeAnexoModal = closeAnexoModal;
// @ts-ignore
window.handleConcluirDireto = handleConcluirDireto;
// @ts-ignore
window.handleSalvarComentarios = handleSalvarComentarios;

document.addEventListener("DOMContentLoaded", () => {
    const paneData = document.getElementById("pane-data");
    PANE_ID = paneData ? paneData.getAttribute("data-pane-id") : null;
    
    if(!PANE_ID) {
        console.error("PANE_ID não encontrado no DOM");
        // @ts-ignore
        showToast("Erro ao carregar ID da Pane.", "error");
        return;
    }
    carregarDetalhe();

    // Bind button events
    const btnConcluir = document.getElementById('btn-concluir');
    if(btnConcluir) btnConcluir.addEventListener('click', handleConcluirDireto);

    const btnSalvarCom = document.getElementById('btn-salvar-comentarios');
    if(btnSalvarCom) btnSalvarCom.addEventListener('click', handleSalvarComentarios);

    const btnDelegar = document.getElementById('btn-delegar');
    if(btnDelegar) btnDelegar.addEventListener('click', openDelegarModal);

    const btnEditOcorr = document.getElementById('btn-edit-ocorrencia');
    if(btnEditOcorr) btnEditOcorr.addEventListener('click', openEditarModal);
    
    // Bind form events
    const formUpload = document.getElementById('formUpload');
    if(formUpload) formUpload.addEventListener('submit', handleUpload);
    
    const formConcluir = document.getElementById('formConcluir');
    if(formConcluir) formConcluir.addEventListener('submit', enviarConclusao);
    
    const formDelegar = document.getElementById('formDelegar');
    if(formDelegar) formDelegar.addEventListener('submit', enviarDelegacao);
    
    const formEditar = document.getElementById('formEditar');
    if(formEditar) formEditar.addEventListener('submit', salvarEdicao);

    // Handlers para fechar modais (CSP compliant)
    document.getElementById('btn-cancel-modal-concluir')?.addEventListener('click', closeConcluirModal);
    document.getElementById('btn-cancel-modal-editar')?.addEventListener('click', closeEditarModal);
    document.getElementById('btn-cancel-modal-delegar')?.addEventListener('click', closeDelegarModal);
    document.getElementById('btn-close-modal-anexo')?.addEventListener('click', closeAnexoModal);
});
