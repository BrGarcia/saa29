/**
 * app/web/static/js/configuracoes_inventario.js
 * Gestão de slots de inventário e consulta da trilha de auditoria.
 *
 * Arquivo separado de configuracoes.js pelo mesmo motivo de
 * configuracoes_publicacoes.js: o principal já passa de 1900 linhas.
 *
 * CSP: a política do projeto é `script-src 'self'` sem 'unsafe-inline'.
 * Nenhum handler pode ser atribuído por onclick no HTML — todos são
 * registrados aqui com addEventListener.
 */

let slotsCache = [];
let modelosCache = [];
let acaoExclusaoPendente = null;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('btn-gerenciar-slots')?.addEventListener('click', abrirModalSlots);
    document.getElementById('btn-close-modal-slots')?.addEventListener('click', () => fecharModal('modal-slots'));
    document.getElementById('btn-close-slots')?.addEventListener('click', () => fecharModal('modal-slots'));
    document.getElementById('chk-incluir-inativos')?.addEventListener('change', carregarSlots);

    document.getElementById('btn-novo-slot')?.addEventListener('click', () => abrirFormSlot(null));
    document.getElementById('btn-close-form-slot')?.addEventListener('click', () => fecharModal('modal-form-slot'));
    document.getElementById('btn-cancelar-form-slot')?.addEventListener('click', () => fecharModal('modal-form-slot'));
    document.getElementById('form-slot')?.addEventListener('submit', salvarSlot);

    document.getElementById('btn-cancelar-exclusao')?.addEventListener('click', () => fecharModal('modal-confirmar-exclusao'));
    document.getElementById('btn-confirmar-exclusao')?.addEventListener('click', confirmarExclusao);
    document.getElementById('btn-close-historico')?.addEventListener('click', () => fecharModal('modal-historico'));
});

function abrirModal(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'flex';
}

function fecharModal(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
}

// ---------------------------------------------------------------- //
//  Listagem de slots
// ---------------------------------------------------------------- //

async function abrirModalSlots() {
    abrirModal('modal-slots');
    await carregarSlots();
}

async function carregarSlots() {
    const tbody = document.getElementById('lista-slots-body');
    if (!tbody) return;

    // `incluir_inativos` é o que torna a inativação reversível: sem ele o slot
    // desligado some da listagem e não haveria como reativá-lo pela tela.
    const incluirInativos = document.getElementById('chk-incluir-inativos')?.checked;
    const query = incluirInativos ? '?incluir_inativos=true' : '';

    tbody.innerHTML = '<tr><td colspan="7" style="padding: 1rem;">Carregando…</td></tr>';
    try {
        slotsCache = await apiFetch(`/equipamentos/slots/${query}`);
        renderizarSlots(slotsCache);
    } catch (e) {
        tbody.innerHTML = '';
        showToast(e.message || 'Erro ao carregar slots.', 'error');
    }
}

function renderizarSlots(slots) {
    const tbody = document.getElementById('lista-slots-body');
    tbody.innerHTML = '';

    if (!slots.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="padding: 1rem; color: var(--text-secondary);">Nenhum slot cadastrado.</td></tr>';
        return;
    }

    slots.forEach((slot) => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid var(--border-color)';
        if (!slot.ativo) tr.style.opacity = '0.55';

        tr.innerHTML = `
            <td style="padding: 0.75rem;">${escapeHtml(slot.sistema || '---')}</td>
            <td style="padding: 0.75rem;">${escapeHtml(slot.nome_posicao)}</td>
            <td style="padding: 0.75rem;">${escapeHtml(nomePn(slot.modelo_id))}</td>
            <td style="padding: 0.75rem;">${escapeHtml(slot.posicao_xlsx || '---')}</td>
            <td style="padding: 0.75rem;">${slot.ordem_exibicao ?? '---'}</td>
            <td style="padding: 0.75rem;">${slot.ativo ? 'Ativo' : 'Inativo'}</td>
            <td style="padding: 0.75rem; text-align: right;"><span class="acoes" style="display: flex; gap: 0.5rem; justify-content: flex-end;"></span></td>
        `;

        const acoes = tr.querySelector('.acoes');
        acoes.appendChild(botao('Editar', () => abrirFormSlot(slot.id)));
        acoes.appendChild(
            slot.ativo
                ? botao('Inativar', () => alternarAtivo(slot, false))
                : botao('Reativar', () => alternarAtivo(slot, true))
        );
        acoes.appendChild(botao('Excluir', () => pedirExclusaoSlot(slot), 'var(--status-danger)'));
        acoes.appendChild(botao('Histórico', () => abrirHistorico('SLOT', slot.id)));
        tbody.appendChild(tr);
    });
}

function botao(rotulo, handler, cor) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn btn-outline';
    b.style.padding = '0.25rem 0.6rem';
    b.style.fontSize = '0.8rem';
    if (cor) b.style.color = cor;
    b.textContent = rotulo;
    b.addEventListener('click', handler);
    return b;
}

function nomePn(modeloId) {
    const modelo = modelosCache.find((m) => m.id === modeloId);
    return modelo ? modelo.part_number : '---';
}

// ---------------------------------------------------------------- //
//  Formulário de slot
// ---------------------------------------------------------------- //

async function abrirFormSlot(slotId) {
    if (!modelosCache.length) {
        try {
            modelosCache = await apiFetch('/equipamentos/');
        } catch (e) {
            showToast(e.message || 'Erro ao carregar o catálogo de PNs.', 'error');
            return;
        }
    }

    const select = document.getElementById('slot-modelo-id');
    select.innerHTML = '';
    modelosCache.forEach((m) => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = `${m.part_number} — ${m.nome_generico}`;
        select.appendChild(opt);
    });

    const slot = slotId ? slotsCache.find((s) => s.id === slotId) : null;
    document.getElementById('titulo-form-slot').textContent = slot ? 'Editar Slot' : 'Novo Slot';
    document.getElementById('slot-id').value = slot ? slot.id : '';
    document.getElementById('slot-nome-posicao').value = slot ? slot.nome_posicao : '';
    document.getElementById('slot-sistema').value = slot ? (slot.sistema || '') : '';
    document.getElementById('slot-posicao-xlsx').value = slot ? (slot.posicao_xlsx || '') : '';
    document.getElementById('slot-descricao').value = slot ? (slot.descricao || '') : '';
    document.getElementById('slot-ordem').value = slot && slot.ordem_exibicao != null ? slot.ordem_exibicao : '';
    if (slot) select.value = slot.modelo_id;

    abrirModal('modal-form-slot');
}

async function salvarSlot(evento) {
    evento.preventDefault();
    const slotId = document.getElementById('slot-id').value;
    const ordem = document.getElementById('slot-ordem').value;

    const corpo = {
        nome_posicao: document.getElementById('slot-nome-posicao').value.trim(),
        sistema: document.getElementById('slot-sistema').value.trim(),
        posicao_xlsx: document.getElementById('slot-posicao-xlsx').value.trim(),
        modelo_id: document.getElementById('slot-modelo-id').value,
        descricao: document.getElementById('slot-descricao').value.trim() || null,
        ordem_exibicao: ordem === '' ? null : Number(ordem),
    };

    try {
        if (slotId) {
            await apiFetch(`/equipamentos/slots/${slotId}`, { method: 'PATCH', body: corpo });
        } else {
            await apiFetch('/equipamentos/slots/', { method: 'POST', body: corpo });
        }
        showToast(slotId ? 'Slot atualizado.' : 'Slot criado.', 'success');
        fecharModal('modal-form-slot');
        await carregarSlots();
    } catch (e) {
        // O backend devolve 409 com o motivo (slot ocupado, nome duplicado);
        // exibir a mensagem dele em vez de um texto genérico.
        showToast(e.message || 'Erro ao salvar o slot.', 'error');
    }
}

// ---------------------------------------------------------------- //
//  Inativar / reativar / excluir
// ---------------------------------------------------------------- //

async function alternarAtivo(slot, ativar) {
    const rota = ativar ? 'reativar' : 'inativar';
    try {
        await apiFetch(`/equipamentos/slots/${slot.id}/${rota}`, { method: 'POST' });
        showToast(ativar ? 'Slot reativado.' : 'Slot inativado.', 'success');
        await carregarSlots();
    } catch (e) {
        showToast(e.message || 'Erro ao alterar a situação do slot.', 'error');
    }
}

async function pedirExclusaoSlot(slot) {
    let aviso = `Excluir o slot ${slot.nome_posicao} (${slot.sistema || 's/ Loc'})?`;
    try {
        const ocupacao = await apiFetch(`/equipamentos/slots/${slot.id}/ocupacao`);
        if (ocupacao.length) {
            const matriculas = [...new Set(ocupacao.map((o) => o.aeronave))].join(', ');
            aviso = `Este slot tem ${ocupacao.length} instalação(ões) vinculada(s) (${matriculas}). `
                + 'A exclusão será recusada — considere inativar o slot.';
        }
    } catch (e) {
        // Consulta de apoio: se falhar, seguimos com o aviso genérico e deixamos
        // o backend recusar. Não é motivo para bloquear o fluxo.
    }

    document.getElementById('texto-confirmar-exclusao').textContent = aviso;
    document.getElementById('exclusao-justificativa').value = '';
    acaoExclusaoPendente = { url: `/equipamentos/slots/${slot.id}/remover`, recarregar: carregarSlots };
    abrirModal('modal-confirmar-exclusao');
}

async function confirmarExclusao() {
    if (!acaoExclusaoPendente) return;
    const justificativa = document.getElementById('exclusao-justificativa').value.trim();
    if (justificativa.length < 5) {
        showToast('A justificativa precisa de ao menos 5 caracteres.', 'error');
        return;
    }

    try {
        // POST, não DELETE: a justificativa exige corpo, e corpo em DELETE é
        // descartado por vários proxies (a aplicação roda atrás do nginx).
        await apiFetch(acaoExclusaoPendente.url, { method: 'POST', body: { justificativa } });
        showToast('Registro excluído.', 'success');
        fecharModal('modal-confirmar-exclusao');
        await acaoExclusaoPendente.recarregar();
        acaoExclusaoPendente = null;
    } catch (e) {
        showToast(e.message || 'Erro ao excluir.', 'error');
    }
}

// ---------------------------------------------------------------- //
//  Trilha de auditoria
// ---------------------------------------------------------------- //

async function abrirHistorico(entidade, entidadeId) {
    const container = document.getElementById('lista-historico');
    container.innerHTML = 'Carregando…';
    abrirModal('modal-historico');

    try {
        const registros = await apiFetch(
            `/equipamentos/auditoria?entidade=${entidade}&entidade_id=${entidadeId}`
        );
        if (!registros.length) {
            container.innerHTML = '<p style="color: var(--text-secondary);">Nenhuma alteração registrada.</p>';
            return;
        }

        container.innerHTML = '';
        registros.forEach((r) => {
            const bloco = document.createElement('div');
            bloco.style.cssText = 'border-bottom: 1px solid var(--border-color); padding: 0.75rem 0;';
            const quando = new Date(r.criado_em).toLocaleString('pt-BR');
            const campos = Object.keys(r.valores_novos || {});
            const resumo = campos.length
                ? campos.map((c) => `${c}: ${formatarValor(r.valores_anteriores?.[c])} → ${formatarValor(r.valores_novos?.[c])}`).join('<br>')
                : '<em>sem diferenças registradas</em>';

            bloco.innerHTML = `
                <div style="font-size: 0.85rem; color: var(--text-secondary);">
                    ${escapeHtml(r.acao)} — ${escapeHtml(quando)}
                </div>
                <div style="font-size: 0.9rem; margin-top: 0.25rem;">${resumo}</div>
                ${r.justificativa ? `<div style="font-size: 0.85rem; margin-top: 0.25rem;"><strong>Justificativa:</strong> ${escapeHtml(r.justificativa)}</div>` : ''}
            `;
            container.appendChild(bloco);
        });
    } catch (e) {
        container.innerHTML = '';
        showToast(e.message || 'Erro ao carregar o histórico.', 'error');
    }
}

function formatarValor(valor) {
    if (valor === null || valor === undefined) return '<em>vazio</em>';
    return escapeHtml(String(valor));
}
