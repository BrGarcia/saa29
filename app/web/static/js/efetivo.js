let usuariosCache = [];
let isAdmin = false;

async function loadEfetivo(forceRefresh = false) {
    const filterStatusEl = document.getElementById('filter-status-user');
    if(!filterStatusEl) return;
    const filterStatus = filterStatusEl.value;
    const incluirInativos = filterStatus === 'inativos';

    if(usuariosCache.length === 0 || forceRefresh) {
        try {
            usuariosCache = await apiFetch(`/auth/usuarios?inativos=${incluirInativos}`);
        } catch(e) {
            console.error(e);
        }
    }
    
    const body = document.getElementById('efetivo-table-body');
    const filterUserEl = document.getElementById('filter-user');
    if(!body || !filterUserEl) return;
    
    const str = filterUserEl.value.toLowerCase();
    
    const filtered = usuariosCache.filter(u => 
        u.nome.toLowerCase().includes(str) || 
        u.username.toLowerCase().includes(str)
    );

    body.innerHTML = '';
    if(filtered.length === 0) {
        body.innerHTML = `<tr><td colspan="5" style="padding: 2rem; text-align: center; color: var(--text-secondary);">Sem registros encontrados.</td></tr>`;
        return;
    }

    const currentUser = JSON.parse(localStorage.getItem("saa29_user") || '{}');

    filtered.forEach(u => {
        let roleColor = "--text-secondary";
        if(u.funcao === "ADMINISTRADOR") roleColor = "--status-danger";
        else if(u.funcao === "ENCARREGADO") roleColor = "--status-warning";
        else if(u.funcao === "INSPETOR") roleColor = "--status-ok";
        else if(u.funcao === "MANTENEDOR") roleColor = "--primary-color";

        const isSelf = u.id === currentUser.id;
        const tr = document.createElement("tr");
        tr.style.borderBottom = "1px solid var(--border-color)";
        if (!u.ativo) tr.style.opacity = "0.6";
        
        tr.innerHTML = `
            <td style="padding: 1rem; font-weight: 500;">${escapeHtml(u.posto)} ${escapeHtml(u.nome)} ${u.trigrama ? `<span style="font-size:0.75rem; font-family:monospace; background:var(--bg-tertiary); padding:0.1rem 0.4rem; border-radius:4px; margin-left:0.25rem;">${escapeHtml(u.trigrama)}</span>` : ''}</td>
            <td style="padding: 1rem; font-family: monospace;">${escapeHtml(u.username)}</td>
            <td style="padding: 1rem;"><span style="color: var(${roleColor}); font-weight: 600; font-size: 0.85rem;">${escapeHtml(u.funcao)}</span></td>
            <td style="padding: 1rem; color: var(--text-secondary);">${escapeHtml(u.ramal) || '-'}</td>
            <td class="td-acoes" style="padding: 0.75rem; white-space: nowrap;"></td>
        `;

        const tdAcoes = tr.querySelector('.td-acoes');
        if(isAdmin) {
            if (u.ativo) {
                const btnEdit = document.createElement('button');
                btnEdit.className = 'btn-icon';
                btnEdit.title = 'Editar';
                btnEdit.style.color = 'var(--status-warning)';
                btnEdit.innerHTML = `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>`;
                btnEdit.addEventListener('click', () => openEditarMembro(u));
                tdAcoes.appendChild(btnEdit);

                const btnPwd = document.createElement('button');
                btnPwd.className = 'btn-icon';
                btnPwd.title = 'Alterar Senha';
                btnPwd.style.color = 'var(--primary-color)';
                btnPwd.style.marginLeft = '0.25rem';
                btnPwd.innerHTML = `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4v-3.828l7.257-7.257A6 6 0 1115 7h.01z"/></svg>`;
                btnPwd.addEventListener('click', () => openResetarSenha(u));
                tdAcoes.appendChild(btnPwd);

                if(!isSelf) {
                    const btnDelete = document.createElement('button');
                    btnDelete.className = 'btn-icon';
                    btnDelete.title = 'Desativar';
                    btnDelete.style.color = 'var(--status-danger)';
                    btnDelete.style.marginLeft = '0.25rem';
                    btnDelete.innerHTML = `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`;
                    btnDelete.addEventListener('click', () => excluirMembro(u.id, u.nome));
                    tdAcoes.appendChild(btnDelete);
                }
            } else {
                const btnRestore = document.createElement('button');
                btnRestore.className = 'btn-icon';
                btnRestore.title = 'Reativar';
                btnRestore.style.color = 'var(--status-ok)';
                btnRestore.innerHTML = `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>`;
                btnRestore.addEventListener('click', () => restaurarMembro(u.id, u.nome));
                tdAcoes.appendChild(btnRestore);
            }
        } else {
            tdAcoes.style.display = 'none';
        }

        body.appendChild(tr);
    });
}

function openModalMembro() { document.getElementById("modal-membro").style.display = "flex"; }
function closeModalMembro() { document.getElementById("modal-membro").style.display = "none"; document.getElementById("formMembro").reset(); }

async function criarMembro(e) {
    e.preventDefault();
    const btn = document.getElementById("btnSalvarMembro");
    btn.disabled = true;

    const payload = {
        nome: document.getElementById("nomeInput").value,
        posto: document.getElementById("postoInput").value,
        especialidade: document.getElementById("espInput").value || null,
        funcao: document.getElementById("funcaoInput").value,
        ramal: document.getElementById("ramalInput").value || null,
        trigrama: document.getElementById("trigramaInput").value.toUpperCase() || null,
        username: document.getElementById("nipInput").value,
        password: document.getElementById("passInput").value
    };

    try {
        await apiFetch("/auth/usuarios", {
            method: "POST",
            body: payload
        });
        showToast("Militar registrado com sucesso!", "success");
        usuariosCache = []; // clear cache
        closeModalMembro();
        loadEfetivo();
    } catch(err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

function openEditarMembro(u) {
    document.getElementById('editMembroId').value = u.id;
    document.getElementById('editPostoInput').value = u.posto || '';
    document.getElementById('editNomeInput').value = u.nome || '';
    document.getElementById('editTrigramaInput').value = u.trigrama || '';
    document.getElementById('editEspInput').value = u.especialidade || '';
    document.getElementById('editFuncaoInput').value = u.funcao || 'MANTENEDOR';
    document.getElementById('editRamalInput').value = u.ramal || '';
    document.getElementById("modal-editar-membro").style.display = 'flex';
}

function closeEditarMembro() {
    document.getElementById("modal-editar-membro").style.display = 'none';
}

function openResetarSenha(u) {
    document.getElementById('resetSenhaUserId').value = u.id;
    document.getElementById('resetSenhaUserName').textContent = u.nome;
    document.getElementById('novaSenhaInput').value = '';
    document.getElementById('modal-resetar-senha').style.display = 'flex';
}

function closeResetarSenha() {
    document.getElementById('modal-resetar-senha').style.display = 'none';
    const form = document.getElementById('formResetarSenha');
    if (form) form.reset();
}

async function salvarEdicaoMembro(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarEdicao');
    btn.disabled = true;
    const id = document.getElementById('editMembroId').value;
    const payload = {
        nome:         document.getElementById('editNomeInput').value || undefined,
        posto:        document.getElementById('editPostoInput').value || undefined,
        especialidade:document.getElementById('editEspInput').value || null,
        funcao:       document.getElementById('editFuncaoInput').value || undefined,
        ramal:        document.getElementById('editRamalInput').value || null,
        trigrama:     document.getElementById('editTrigramaInput').value.toUpperCase() || null,
    };
    try {
        await apiFetch(`/auth/usuarios/${id}`, { method: 'PUT', body: payload });
        showToast('Dados do militar atualizados!', 'success');
        usuariosCache = [];
        closeEditarMembro();
        loadEfetivo();
    } catch(err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

async function salvarNovaSenha(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSalvarNovaSenha');
    btn.disabled = true;
    const id = document.getElementById('resetSenhaUserId').value;
    const novaSenha = document.getElementById('novaSenhaInput').value;
    
    try {
        await apiFetch(`/auth/usuarios/${id}/senha`, { 
            method: 'PUT', 
            body: { nova_senha: novaSenha } 
        });
        showToast('Senha alterada com sucesso!', 'success');
        closeResetarSenha();
    } catch(err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

async function excluirMembro(id, nome) {
    if(!confirm(`Atenção: O militar "${nome}" será desativado do sistema. Ele não poderá mais logar, mas seu histórico de panes será preservado. Confirmar?`)) return;
    try {
        await apiFetch(`/auth/usuarios/${id}`, { method: 'DELETE' });
        showToast(`${nome} desativado com sucesso.`, 'info');
        loadEfetivo(true);
    } catch(e) {}
}

async function restaurarMembro(id, nome) {
    if(!confirm(`Deseja reativar o acesso de "${nome}" ao sistema?`)) return;
    try {
        await apiFetch(`/auth/usuarios/${id}/restaurar`, { method: 'POST' });
        showToast(`${nome} reativado com sucesso!`, 'success');
        loadEfetivo(true);
    } catch(e) {}
}

window.openModalMembro = openModalMembro;
window.closeModalMembro = closeModalMembro;
window.closeEditarMembro = closeEditarMembro;
window.loadEfetivo = loadEfetivo;

document.addEventListener("DOMContentLoaded", () => {
    isAdmin = window.hasPermission('ADMINISTRADOR');
    if(isAdmin) {
        const btnAdd = document.getElementById('btn-add-membro');
        if(btnAdd) btnAdd.addEventListener('click', openModalMembro);
    }
    loadEfetivo();

    const filterUser = document.getElementById('filter-user');
    if (filterUser) {
        filterUser.addEventListener('keyup', () => loadEfetivo());
    }

    const filterStatus = document.getElementById('filter-status-user');
    if (filterStatus) {
        filterStatus.addEventListener('change', () => loadEfetivo(true));
    }

    const formMembro = document.getElementById('formMembro');
    if(formMembro) formMembro.addEventListener('submit', criarMembro);

    const formEditar = document.getElementById('formEditarMembro');
    if(formEditar) formEditar.addEventListener('submit', salvarEdicaoMembro);
    
    const formResetSenha = document.getElementById('formResetarSenha');
    if(formResetSenha) formResetSenha.addEventListener('submit', salvarNovaSenha);

    // Handlers para fechar modais (CSP compliant)
    document.getElementById('btn-cancelar-membro')?.addEventListener('click', closeModalMembro);
    document.getElementById('btn-cancelar-edicao-membro')?.addEventListener('click', closeEditarMembro);
    document.getElementById('btn-cancelar-reset-senha')?.addEventListener('click', closeResetarSenha);
});
