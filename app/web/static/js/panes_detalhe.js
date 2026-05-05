let ehGestorGlobal = false;
let PANE_ID = null;
let paneSomenteLeitura = false;

function acaoBloqueadaPaneInativa() {
    showToast("Pane excluída: ação indisponível enquanto estiver na lixeira.", "info");
}

async function carregarDetalhe() {
    try {
        const pane = await apiFetch(`/panes/${PANE_ID}`);
        paneSomenteLeitura = !pane.ativo;

        // Textos base e Cabeçalho (Matrícula)
        document.getElementById("det-id").innerText = pane.codigo || "---/--";
        document.getElementById("det-sistema").innerText = pane.sistema_ata ? pane.sistema_ata.descricao : "Não especificado";
        // Guardamos o id para usar na edição se necessário
        document.getElementById("det-sistema").dataset.id = pane.sistema_ata_id || "";
        document.getElementById("det-descricao").innerText = pane.descricao;

        // Relator
        const relator = pane.criador;
        if (relator) {
            const postoNome = [relator.posto, relator.nome].filter(Boolean).join(" ");
            document.getElementById("det-relator").innerText = postoNome;
        } else {
            document.getElementById("det-relator").innerText = "Não registrado";
        }

        // Formatar Data e Hora
        if (pane.data_abertura) {
            const dObj = new Date(pane.data_abertura);
            const fullDate = dObj.toLocaleString('pt-BR', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
            document.getElementById("det-data").innerText = fullDate;
        } else {
            document.getElementById("det-data").innerText = "--";
        }

        // Popula a matrícula da aeronave no cabeçalho
        const matricula = pane.aeronave?.matricula || "59XX";
        document.getElementById("det-matricula").innerText = `Aeronave ${matricula}`;

        // Botões de fluxo e Status badge
        const btnConc = document.getElementById("btn-concluir");
        const btnDelegar = document.getElementById("btn-delegar");
        const btnEditOcorrencia = document.getElementById("btn-edit-ocorrencia");
        const spanSts = document.getElementById("det-status");
        const formUp = document.getElementById("formUpload");

        const resInput = document.getElementById("resolucao-texto");
        const resStatus = document.getElementById("status-resolucao-salva");
        const divAssinatura = document.getElementById("det-assinatura");
        const comInput = document.getElementById("comentarios-texto");
        const alertaInativa = document.getElementById("det-inativa-alerta");
        const btnSalvarComentarios = document.getElementById("btn-salvar-comentarios");

        btnConc.style.display = "none";
        btnDelegar.style.display = "none";
        btnEditOcorrencia.style.display = "none";
        formUp.style.display = "flex";
        resInput.disabled = false;
        resStatus.style.display = "none";
        divAssinatura.style.display = "none";
        alertaInativa.style.display = "none";
        btnSalvarComentarios.style.display = "inline-flex";
        btnSalvarComentarios.disabled = false;
        comInput.value = pane.comentarios || "";
        comInput.disabled = false;

        const localUser = JSON.parse(localStorage.getItem("saa29_user") || '{}');
        ehGestorGlobal = window.hasPermission('ENCARREGADO');

        let bClass = "badge-aberta";
        let statusLabel = pane.status.replace("_", " ");
        if (paneSomenteLeitura) {
            bClass = "badge-resolvida";
            statusLabel = "EXCLUIDA";
            formUp.style.display = "none";
            resInput.disabled = true;
            comInput.disabled = true;
            btnSalvarComentarios.style.display = "none";
            alertaInativa.style.display = "block";
            resInput.value = pane.observacao_conclusao || "";
        } else if (pane.status === "RESOLVIDA") {
            bClass = "badge-resolvida";
            formUp.style.display = "none";
            resInput.disabled = true;

            if (pane.observacao_conclusao) {
                resInput.value = pane.observacao_conclusao;
                resStatus.style.display = "block";
                resStatus.innerText = "Ação Corretiva Finalizada e Assinada.";
            }

            if (pane.concluido_por) {
                divAssinatura.style.display = "block";
                const u = pane.concluido_por;
                const postoNome = [u.posto, u.nome].filter(Boolean).join(" ");
                divAssinatura.innerHTML = `<strong>Finalizado por:</strong> ${escapeHtml(postoNome)} (${escapeHtml(u.trigrama || u.username)})`;
            }
        } else if (pane.status === "ABERTA") {
            btnConc.style.display = "block";
            if (ehGestorGlobal) {
                btnDelegar.style.display = "block";
                btnEditOcorrencia.style.display = "block";
            }
            resInput.value = pane.observacao_conclusao || "";
        }

        spanSts.innerHTML = `<span class="badge ${bClass}">${statusLabel}</span>`;

        carregarAnexos();

    } catch (e) {
        console.error(e);
        showToast("Falha ao recuperar informações da Pane.", "error");
    }
}

async function handleSalvarComentarios() {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    const comentarios = document.getElementById("comentarios-texto").value.trim();
    const btn = document.getElementById("btn-salvar-comentarios");
    const statusMsg = document.getElementById("status-comentarios-salvo");

    btn.disabled = true;
    btn.innerText = "Salvando...";
    statusMsg.style.display = "none";

    try {
        await apiFetch(`/panes/${PANE_ID}`, {
            method: "PUT",
            body: { comentarios: comentarios }
        });

        showToast("Observações salvas com sucesso!", "success");
        statusMsg.style.display = "block";
        setTimeout(() => { statusMsg.style.display = "none"; }, 3000);
    } catch (e) {
        console.error(e);
        showToast("Erro ao salvar observações.", "error");
    } finally {
        btn.disabled = false;
        btn.innerText = "Salvar Comentário";
    }
}

async function handleConcluirDireto() {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    const obs = document.getElementById("resolucao-texto").value.trim();
    if (!obs) {
        showToast("Por favor, descreva a ação corretiva antes de concluir.", "error");
        document.getElementById("resolucao-texto").focus();
        return;
    }

    const btn = document.getElementById("btn-concluir");
    btn.disabled = true;
    btn.innerText = "Processando...";

    try {
        await apiFetch(`/panes/${PANE_ID}/concluir`, {
            method: "POST",
            body: { observacao_conclusao: obs }
        });

        showToast("Pane finalizada com sucesso!", "success");
        carregarDetalhe();
    } catch (e) {
        btn.disabled = false;
        btn.innerText = "Concluir e Assinar";
    }
}

function openConcluirModal() { document.getElementById("modal-concluir").style.display = "flex"; }
function closeConcluirModal() { document.getElementById("modal-concluir").style.display = "none"; }

async function enviarConclusao(e) {
    e.preventDefault();
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    const obs = document.getElementById("obsConclusao").value;
    try {
        await apiFetch(`/panes/${PANE_ID}/concluir`, {
            method: "POST",
            body: { observacao_conclusao: obs }
        });

        showToast("Pane finalizada e assinada.", "success");
        closeConcluirModal();
        carregarDetalhe();
    } catch (e) { }
}

let usuariosParaDelegar = [];
async function openDelegarModal() {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    document.getElementById("modal-delegar").style.display = "flex";
    const select = document.getElementById("mantenedorSelect");
    select.innerHTML = '<option value="">Carregando...</option>';
    try {
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
function closeDelegarModal() { document.getElementById("modal-delegar").style.display = "none"; }

async function enviarDelegacao(e) {
    e.preventDefault();
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    const mantId = document.getElementById("mantenedorSelect").value;
    if (!mantId) return;

    const usuarioSelecionado = usuariosParaDelegar.find(u => u.id === mantId);
    const papelAtribuir = usuarioSelecionado ? usuarioSelecionado.funcao : "MANTENEDOR";

    try {
        await apiFetch(`/panes/${PANE_ID}/responsaveis`, {
            method: "POST",
            body: { usuario_id: mantId, papel: papelAtribuir }
        });
        showToast("Pane delegada com sucesso.", "success");
        closeDelegarModal();
    } catch (e) { }
}

async function openEditarModal() {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    
    const editSistema = document.getElementById("editSistema");
    editSistema.innerHTML = '<option value="">Carregando...</option>';
    
    try {
        const sistemas = await apiFetch("/panes/sistemas");
        editSistema.innerHTML = '<option value="">-- Selecione o Sistema --</option>';
        sistemas.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.id;
            opt.innerText = `${s.codigo} - ${s.descricao}`;
            editSistema.appendChild(opt);
        });
        editSistema.value = document.getElementById("det-sistema").dataset.id || "";
    } catch(e) { console.error(e) }

    document.getElementById("editDescricao").value = document.getElementById("det-descricao").innerText;
    document.getElementById("modal-editar").style.display = "flex";
}
function closeEditarModal() { document.getElementById("modal-editar").style.display = "none"; }

async function salvarEdicao(e) {
    e.preventDefault();
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    const sistema = document.getElementById("editSistema").value;
    const descricao = document.getElementById("editDescricao").value;

    try {
        await apiFetch(`/panes/${PANE_ID}`, {
            method: "PUT",
            body: { sistema_ata_id: sistema || null, descricao: descricao }
        });
        showToast("Dados atualizados com sucesso.", "success");
        closeEditarModal();
        carregarDetalhe();
    } catch (e) { }
}

async function carregarAnexos() {
    try {
        const anexos = await apiFetch(`/panes/${PANE_ID}/anexos`);
        const lista = document.getElementById("lista-anexos");
        lista.innerHTML = "";

        if (anexos.length === 0) {
            lista.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-secondary); text-align: center;">Sem arquivos vinculados.</p>`;
            return;
        }

        anexos.forEach(ax => {
            const div = document.createElement("div");
            div.style = "display: flex; align-items: center; justify-content: space-between; padding: 0.5rem; background: var(--bg-primary); border-radius: var(--radius-md); font-size: 0.85rem; border: 1px solid var(--border-color);";

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
            btnAbrir.addEventListener('click', () => abrirAnexo(ax.id, ax.tipo));
            
            const btnExcluirTrigger = div.querySelector('.btn-excluir-anexo');
            if(btnExcluirTrigger) {
                btnExcluirTrigger.addEventListener('click', () => handleExcluirAnexo(ax.id));
            }

            lista.appendChild(div);
        });
    } catch (e) { }
}

async function handleExcluirAnexo(anexoId) {
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    if (!confirm("Deseja realmente excluir este anexo?")) return;
    try {
        await apiFetch(`/panes/${PANE_ID}/anexos/${anexoId}`, { method: "DELETE" });
        showToast("Anexo removido com sucesso.", "success");
        carregarAnexos();
    } catch (e) {
        console.error(e);
        showToast("Erro ao excluir anexo.", "error");
    }
}

function closeAnexoModal() {
    const modalAnexo = document.getElementById("modal-anexo");
    modalAnexo.style.display = "none";
    if (window.currentAnexoUrl) {
        URL.revokeObjectURL(window.currentAnexoUrl);
        window.currentAnexoUrl = null;
    }
    document.getElementById("anexo-content").innerHTML = "";
}

async function abrirAnexo(anexoId, tipoAnexo) {
    const modalAnexo = document.getElementById("modal-anexo");
    const anexoContent = document.getElementById("anexo-content");
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
        showToast("Falha ao abrir anexo.", "error");
        closeAnexoModal();
    }
}

async function handleUpload(e) {
    e.preventDefault();
    if (paneSomenteLeitura) {
        acaoBloqueadaPaneInativa();
        return;
    }
    const input = document.getElementById("arquivoInput");
    if (input.files.length === 0) return;

    const formData = new FormData();
    formData.append("arquivo", input.files[0]);

    const btn = document.getElementById("btnUpload");
    btn.disabled = true;

    try {
        await apiFetch(`/panes/${PANE_ID}/anexos`, {
            method: "POST",
            body: formData
        });

        showToast("Evidência anexada.", "success");
        input.value = "";
        carregarAnexos();
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

// Global scope exposed functions
window.openConcluirModal = openConcluirModal;
window.closeConcluirModal = closeConcluirModal;
window.openDelegarModal = openDelegarModal;
window.closeDelegarModal = closeDelegarModal;
window.openEditarModal = openEditarModal;
window.closeEditarModal = closeEditarModal;
window.closeAnexoModal = closeAnexoModal;
window.handleConcluirDireto = handleConcluirDireto;
window.handleSalvarComentarios = handleSalvarComentarios;

document.addEventListener("DOMContentLoaded", () => {
    PANE_ID = document.getElementById("pane-data")?.getAttribute("data-pane-id");
    if(!PANE_ID) {
        console.error("PANE_ID não encontrado no DOM");
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
