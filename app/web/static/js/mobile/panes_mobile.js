// app/web/static/js/mobile/panes_mobile.js
// Módulo Panes do SAA29 Mobile: aba do hub, relato rápido (Nova Pane) e
// detalhe da pane (foto, assumir, comentar, concluir).

// ============================================================================
// Aba "Panes" do hub da aeronave (RF-M20)
// ============================================================================

window.carregarAbaPanes = async function carregarAbaPanes(aeronaveId, container) {
    container.innerHTML = '<div class="mobile-loading">Buscando panes da aeronave...</div>';

    try {
        const panes = await apiFetch(`/panes/?aeronave_id=${aeronaveId}&status=ABERTA`);
        renderizarListaPanes(Array.isArray(panes) ? panes : [], aeronaveId, container);
    } catch (err) {
        console.error('Erro ao carregar panes da aeronave:', err);
        container.innerHTML = '<div class="mobile-loading" style="color: var(--mobile-danger);">Erro ao carregar panes.</div>';
    }
};

function renderizarListaPanes(panes, aeronaveId, container) {
    container.innerHTML = '';

    const lista = document.createElement('div');
    lista.className = 'mobile-task-list';

    if (panes.length === 0) {
        lista.innerHTML = `
            <div class="mobile-card" style="text-align:center;">
                <p style="margin:0; color: var(--mobile-success-bright); font-weight:700;">Tudo em dia!</p>
                <p style="margin:0.35rem 0 0; color: var(--mobile-text-muted); font-size:0.85rem;">Nenhuma pane aberta para esta aeronave no momento.</p>
            </div>
        `;
    } else {
        panes.forEach((pane) => lista.appendChild(montarCardPane(pane)));
    }

    container.appendChild(lista);

    const fab = document.createElement('a');
    fab.href = `/m/pane/nova?aeronave_id=${aeronaveId}`;
    fab.className = 'mobile-fab';
    fab.innerHTML = `
        <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.4" viewBox="0 0 24 24"><path stroke-linecap="round" d="M12 4v16m8-8H4"></path></svg>
        Nova Pane
    `;
    container.appendChild(fab);
}

function montarCardPane(pane) {
    const card = document.createElement('a');
    card.href = `/m/pane/${pane.id}`;
    card.className = 'mobile-task-card';

    const trigrama = pane.criador && pane.criador.trigrama ? pane.criador.trigrama : 'MANT';
    const codigo = pane.codigo || '';
    const dataAbertura = pane.data_abertura ? new Date(pane.data_abertura).toLocaleDateString() : '';
    const sistemaTexto = pane.sistema_ata ? pane.sistema_ata.codigo : 'Sem sistema ATA';

    card.innerHTML = `
        <div class="mobile-task-card-top">
            <span class="mobile-pill">${escapeHtml(codigo)} · ABERTA</span>
            <span class="mobile-task-card-meta">${escapeHtml(dataAbertura)}</span>
        </div>
        <p class="mobile-task-card-title">${escapeHtml(pane.descricao || 'Pane de Linha de Voo')}</p>
        <p class="mobile-task-card-meta">${escapeHtml(sistemaTexto)} · relator ${escapeHtml(trigrama)}</p>
    `;
    return card;
}

// ============================================================================
// Nova Pane — relato rápido (RF-M21) — /m/pane/nova?aeronave_id=
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    const formNovaPane = document.getElementById('form-pane-nova');
    if (formNovaPane) inicializarFormNovaPane(formNovaPane);

    const contextoPaneDetalhe = document.getElementById('context-pane-detalhe');
    if (contextoPaneDetalhe) inicializarPaneDetalhe(contextoPaneDetalhe.getAttribute('data-pane-id'));
});

function abreviarMatriculaPane(matricula) {
    if (!matricula) return '----';
    const digitos = matricula.replace(/\D/g, '');
    return digitos.length >= 4 ? digitos.slice(-4) : matricula;
}

async function inicializarFormNovaPane(form) {
    const aeronaveId = form.getAttribute('data-aeronave-id');
    const selectSistema = document.getElementById('pane-nova-sistema');
    const inputFoto = document.getElementById('pane-nova-foto-input');
    const btnAbrirCamera = document.getElementById('btn-pane-nova-foto');
    const btnSubmit = document.getElementById('btn-pane-nova-submit');
    const labelAeronave = document.getElementById('pane-nova-aeronave-label');

    if (btnAbrirCamera && inputFoto) {
        btnAbrirCamera.addEventListener('click', () => inputFoto.click());
    }

    if (labelAeronave) {
        try {
            const aeronave = await apiFetch(`/aeronaves/${aeronaveId}`);
            labelAeronave.textContent = abreviarMatriculaPane(aeronave.matricula);
        } catch (e) {
            console.warn('Falha ao carregar aeronave da pane:', e);
        }
    }

    try {
        const sistemas = await apiFetch('/panes/sistemas');
        if (Array.isArray(sistemas) && selectSistema) {
            sistemas.forEach((sistema) => {
                const opt = document.createElement('option');
                opt.value = sistema.id;
                opt.textContent = `${sistema.codigo} · ${sistema.descricao}`;
                selectSistema.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn('Falha ao carregar sistemas ATA:', e);
    }

    let fotoSelecionada = null;
    const iconeAdicionarFoto = btnAbrirCamera ? btnAbrirCamera.innerHTML : '';
    if (inputFoto) {
        inputFoto.addEventListener('change', () => {
            fotoSelecionada = inputFoto.files && inputFoto.files[0] ? inputFoto.files[0] : null;
            if (btnAbrirCamera) {
                btnAbrirCamera.innerHTML = fotoSelecionada
                    ? `<img src="${URL.createObjectURL(fotoSelecionada)}" alt="Prévia da foto anexada">`
                    : iconeAdicionarFoto;
            }
        });
    }

    form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.textContent = 'Registrando...';
        }

        try {
            const descricao = document.getElementById('pane-nova-descricao').value.trim();
            const payload = {
                aeronave_id: aeronaveId,
                sistema_ata_id: selectSistema && selectSistema.value ? selectSistema.value : null,
                descricao: descricao || undefined,
            };

            const pane = await apiFetch('/panes/', { method: 'POST', body: payload });

            if (fotoSelecionada) {
                const formData = new FormData();
                formData.append('arquivo', fotoSelecionada);
                try {
                    await apiFetch(`/panes/${pane.id}/anexos`, { method: 'POST', body: formData });
                } catch (e) {
                    console.warn('Pane criada, mas o anexo falhou:', e);
                    showToast('Pane registrada, mas o anexo da foto falhou. Anexe novamente no detalhe.', 'warning');
                }
            }

            showToast('Pane registrada com sucesso!', 'success');
            window.location.href = `/m/pane/${pane.id}`;
        } catch (err) {
            console.error('Erro ao registrar pane:', err);
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.textContent = 'Registrar Pane';
            }
        }
    });
}

// ============================================================================
// Detalhe da pane (RF-M22, RF-M23) — /m/pane/{pane_id}
// ============================================================================

let paneIdAtual = null;
let usuarioIdAtual = null;

async function inicializarPaneDetalhe(paneId) {
    paneIdAtual = paneId;
    const contextoGlobal = document.getElementById('mobile-global-context');
    usuarioIdAtual = contextoGlobal ? contextoGlobal.getAttribute('data-user-id') : null;

    await carregarPaneDetalhe();

    const inputFoto = document.getElementById('pane-camera-input');
    const btnTirarFoto = document.getElementById('btn-pane-tirar-foto');
    if (btnTirarFoto && inputFoto) {
        btnTirarFoto.addEventListener('click', () => inputFoto.click());
        inputFoto.addEventListener('change', handleAnexarFotoPane);
    }

    const btnAssumir = document.getElementById('btn-pane-assumir');
    if (btnAssumir) btnAssumir.addEventListener('click', handleAssumirPane);

    const formConcluir = document.getElementById('form-pane-concluir');
    if (formConcluir) formConcluir.addEventListener('submit', handleConcluirPane);

    const formComentarios = document.getElementById('form-pane-comentarios');
    if (formComentarios) formComentarios.addEventListener('submit', handleSalvarComentarios);
}

async function carregarPaneDetalhe() {
    try {
        const pane = await apiFetch(`/panes/${paneIdAtual}`);
        renderizarPaneDetalhe(pane);
    } catch (err) {
        console.error('Erro ao carregar detalhe da pane:', err);
        showToast('Erro ao carregar a pane.', 'error');
    }
}

function renderizarPaneDetalhe(pane) {
    const tituloEl = document.getElementById('pane-detalhe-codigo');
    const statusEl = document.getElementById('pane-detalhe-status');
    const infoEl = document.getElementById('pane-detalhe-info');
    const descricaoEl = document.getElementById('pane-detalhe-descricao');
    const galeriaEl = document.getElementById('pane-detalhe-galeria');
    const responsavelEl = document.getElementById('pane-detalhe-responsavel');
    const comentariosInput = document.getElementById('pane-comentarios-input');
    const areaConcluir = document.getElementById('pane-area-concluir');
    const observacaoConcluida = document.getElementById('pane-observacao-conclusao');

    const linkVoltar = document.getElementById('pane-detalhe-voltar');
    if (linkVoltar && pane.aeronave_id) linkVoltar.href = `/m/aeronave/${pane.aeronave_id}`;

    if (tituloEl) tituloEl.textContent = pane.codigo || '';
    if (statusEl) {
        statusEl.textContent = pane.status;
        statusEl.className = `badge-status ${pane.status === 'ABERTA' ? 'status-aberta' : 'status-resolvida'}`;
    }
    if (infoEl) {
        const sistema = pane.sistema_ata ? pane.sistema_ata.codigo : 'Sem sistema ATA';
        const relator = pane.criador && pane.criador.trigrama ? pane.criador.trigrama : '—';
        infoEl.textContent = `${sistema} · relator ${relator}`;
    }
    if (descricaoEl) descricaoEl.textContent = pane.descricao || '';

    if (galeriaEl) {
        galeriaEl.innerHTML = '';
        (pane.anexos || []).forEach((anexo) => {
            const link = document.createElement('a');
            link.href = `/panes/${pane.id}/anexos/${anexo.id}/download`;
            link.target = '_blank';
            link.rel = 'noopener';
            link.className = 'mobile-photo';
            if (anexo.tipo === 'IMAGEM') {
                link.innerHTML = `<img src="/panes/${pane.id}/anexos/${anexo.id}/download" alt="Anexo da pane">`;
            } else {
                link.textContent = 'PDF';
            }
            galeriaEl.appendChild(link);
        });
    }

    if (responsavelEl) {
        const responsaveis = pane.responsaveis || [];
        responsavelEl.textContent = responsaveis.length > 0
            ? responsaveis.map((r) => r.trigrama || '—').join(', ')
            : 'Ninguém assumiu ainda';
    }

    const btnAssumir = document.getElementById('btn-pane-assumir');
    if (btnAssumir) {
        const jaAssumido = (pane.responsaveis || []).some((r) => r.usuario_id === usuarioIdAtual);
        btnAssumir.hidden = jaAssumido;
    }

    if (comentariosInput && document.activeElement !== comentariosInput) {
        comentariosInput.value = pane.comentarios || '';
    }

    const paneAberta = pane.status === 'ABERTA';
    if (areaConcluir) areaConcluir.hidden = !paneAberta;
    if (observacaoConcluida) {
        observacaoConcluida.hidden = paneAberta;
        observacaoConcluida.textContent = pane.observacao_conclusao
            ? `Solução aplicada: ${pane.observacao_conclusao}`
            : '';
    }
}

async function handleAnexarFotoPane(ev) {
    const arquivo = ev.target.files && ev.target.files[0];
    if (!arquivo) return;

    try {
        const formData = new FormData();
        formData.append('arquivo', arquivo);
        await apiFetch(`/panes/${paneIdAtual}/anexos`, { method: 'POST', body: formData });
        showToast('Foto anexada com sucesso!', 'success');
        await carregarPaneDetalhe();
    } catch (err) {
        console.error('Erro ao anexar foto:', err);
    } finally {
        ev.target.value = '';
    }
}

async function handleAssumirPane() {
    if (!usuarioIdAtual) return;

    const btn = document.getElementById('btn-pane-assumir');
    if (btn) btn.disabled = true;

    try {
        await apiFetch(`/panes/${paneIdAtual}/responsaveis`, {
            method: 'POST',
            body: { usuario_id: usuarioIdAtual, papel: 'MANTENEDOR' },
        });
        showToast('Responsabilidade assumida.', 'success');
        await carregarPaneDetalhe();
    } catch (err) {
        console.error('Erro ao assumir pane:', err);
        if (btn) btn.disabled = false;
    }
}

async function handleConcluirPane(ev) {
    ev.preventDefault();
    const textarea = document.getElementById('pane-concluir-observacao');
    const btn = document.getElementById('btn-pane-concluir');

    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Concluindo...';
    }

    try {
        await apiFetch(`/panes/${paneIdAtual}/concluir`, {
            method: 'POST',
            body: { observacao_conclusao: textarea ? textarea.value.trim() || null : null },
        });
        showToast('Pane concluída com sucesso!', 'success');
        await carregarPaneDetalhe();
    } catch (err) {
        console.error('Erro ao concluir pane:', err);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Concluir e Assinar';
        }
    }
}

async function handleSalvarComentarios(ev) {
    ev.preventDefault();
    const textarea = document.getElementById('pane-comentarios-input');
    const btn = document.getElementById('btn-pane-comentarios-salvar');

    if (btn) btn.disabled = true;
    try {
        await apiFetch(`/panes/${paneIdAtual}`, {
            method: 'PUT',
            body: { comentarios: textarea ? textarea.value : '' },
        });
        showToast('Comentário salvo.', 'success');
    } catch (err) {
        console.error('Erro ao salvar comentário:', err);
    } finally {
        if (btn) btn.disabled = false;
    }
}
