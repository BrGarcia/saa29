// @ts-check

/**
 * Gerência do módulo de publicações na página de Configurações.
 *
 * Card "Publicações" + três modais: edições do acervo (com ativar/reverter e
 * arquivar), relatório de diff, e status do acervo.
 *
 * Arquivo separado de `configuracoes.js` (1.900+ linhas) por ser um bloco
 * coeso e independente. Segue as mesmas convenções daquele: nenhum handler
 * inline (CSP), tudo registrado no DOMContentLoaded, e os utilitários globais
 * de `app.js` acessados via window.
 *
 * Fase 2 de `docs/backlog/modulo_publicacoes/09_plano_configuracoes.md`.
 */

const URL_EDICOES = "/publicacoes/api/edicoes";

/**
 * @typedef {Object} EdicaoDTO
 * @property {string} id
 * @property {string} rotulo
 * @property {"AGUARDANDO_ATIVACAO"|"VIGENTE"|"ANTERIOR"|"ARQUIVADA"} status
 * @property {string} data_publicacao
 * @property {number} manuais
 * @property {number} documentos
 * @property {boolean} indice_disponivel
 * @property {boolean} tem_relatorio
 * @property {string | null} snapshot_key
 */

/** Aparência de cada status na pílula da tabela. */
const ESTILO_STATUS = {
    VIGENTE: { rotulo: "Vigente", fundo: "rgba(46, 204, 113, 0.12)", cor: "var(--status-ok)" },
    AGUARDANDO_ATIVACAO: { rotulo: "Aguardando ativação", fundo: "rgba(230, 126, 34, 0.12)", cor: "var(--status-warning)" },
    ANTERIOR: { rotulo: "Anterior", fundo: "rgba(148, 163, 184, 0.15)", cor: "var(--text-secondary)" },
    ARQUIVADA: { rotulo: "Arquivada", fundo: "rgba(231, 76, 60, 0.12)", cor: "var(--status-danger)" },
};

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btn-gerenciar-edicoes")?.addEventListener("click", abrirModalEdicoes);
    document.getElementById("btn-close-modal-edicoes")?.addEventListener("click", fecharModalEdicoes);
    document.getElementById("btn-close-edicoes")?.addEventListener("click", fecharModalEdicoes);

    document.getElementById("btn-status-acervo")?.addEventListener("click", abrirModalStatusAcervo);
    document.getElementById("btn-close-modal-status-acervo")?.addEventListener("click", fecharModalStatusAcervo);
    document.getElementById("btn-close-status-acervo")?.addEventListener("click", fecharModalStatusAcervo);

    document.getElementById("btn-close-modal-relatorio")?.addEventListener("click", fecharModalRelatorio);
    document.getElementById("btn-close-relatorio")?.addEventListener("click", fecharModalRelatorio);

    // Atalho que faltava: hoje só se chega às avulsas pelo link dentro de
    // /publicacoes. Mesmo padrão do btn-config-efetivo em configuracoes.js.
    document.getElementById("btn-ir-avulsas")?.addEventListener("click", () => {
        window.location.href = "/publicacoes/avulsas";
    });

    // Upload de Edições (.zip)
    document.getElementById("btn-toggle-area-upload")?.addEventListener("click", toggleAreaUpload);
    document.getElementById("form-upload-edicao")?.addEventListener("submit", tratarSubmitUpload);
    document.getElementById("btn-cancelar-upload")?.addEventListener("click", cancelarUploadAtual);
});

// ==========================================
// Modal: Edições do Acervo
// ==========================================

/** @returns {void} */
function abrirModalEdicoes() {
    const modal = document.getElementById("modal-edicoes");
    if (modal) modal.style.display = "flex";
    carregarEdicoes();
}

/** @returns {void} */
function fecharModalEdicoes() {
    const modal = document.getElementById("modal-edicoes");
    if (modal) modal.style.display = "none";
}

/**
 * Carrega a lista de edições e monta a tabela.
 * @returns {Promise<void>}
 */
async function carregarEdicoes() {
    const tbody = document.getElementById("lista-edicoes-body");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 1rem;">Carregando edições...</td></tr>';

    try {
        /** @type {EdicaoDTO[]} */
        const edicoes = await apiFetch(URL_EDICOES);
        tbody.innerHTML = "";

        if (edicoes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 1rem; color: var(--text-secondary);">Nenhuma edição publicada ainda.</td></tr>';
            return;
        }

        edicoes.forEach((e) => tbody.appendChild(montarLinhaEdicao(e)));
        atualizarAvisoRetencao(edicoes);
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar edições.</td></tr>';
    }
}

/**
 * Uma linha da tabela de edições, com os botões que fazem sentido para o estado dela.
 * @param {EdicaoDTO} e
 * @returns {HTMLTableRowElement}
 */
function montarLinhaEdicao(e) {
    const tr = document.createElement("tr");
    tr.style.borderBottom = "1px solid var(--border-color)";

    const estilo = ESTILO_STATUS[e.status] || ESTILO_STATUS.ANTERIOR;
    const data = e.data_publicacao ? new Date(e.data_publicacao).toLocaleDateString("pt-BR") : "—";
    const numDocs = (e.documentos || 0).toLocaleString("pt-BR");

    const indice = e.indice_disponivel
        ? '<span title="catalog.db desta edição presente no disco" style="color: var(--status-ok);">✓</span>'
        : '<span title="Índice ausente — reindexe antes de ativar" style="color: var(--status-warning);">ausente</span>';

    tr.innerHTML = `
        <td style="padding: 0.75rem;"><strong>${escapeHtml(e.rotulo)}</strong></td>
        <td style="padding: 0.75rem; text-align: center; color: var(--text-secondary);">${data}</td>
        <td style="padding: 0.75rem; text-align: center;">${numDocs}</td>
        <td style="padding: 0.75rem; text-align: center;">${indice}</td>
        <td style="padding: 0.75rem; text-align: center;">
            <span style="display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.78rem; font-weight: 600; background: ${estilo.fundo}; color: ${estilo.cor};">${estilo.rotulo}</span>
        </td>
        <td class="celula-acoes" style="padding: 0.75rem; text-align: right;"></td>
    `;

    const acoes = tr.querySelector(".celula-acoes");
    if (acoes) montarAcoesEdicao(/** @type {HTMLElement} */(acoes), e);
    return tr;
}

/**
 * Botões de ação da linha.
 *
 * "Ativar" só existe quando há índice em disco: o servidor recusa com 409 sem
 * ele, e oferecer um botão que será recusado é pior do que não oferecer. No
 * lugar vai a instrução do que fazer.
 *
 * @param {HTMLElement} celula
 * @param {EdicaoDTO} e
 * @returns {void}
 */
function montarAcoesEdicao(celula, e) {
    celula.style.display = "flex";
    celula.style.gap = "0.4rem";
    celula.style.justifyContent = "flex-end";
    celula.style.flexWrap = "wrap";

    const podeAtivar = e.status === "AGUARDANDO_ATIVACAO" || e.status === "ANTERIOR";

    if (podeAtivar && e.indice_disponivel) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-publicacao";
        btn.style.cssText = "padding: 0.3rem 0.7rem; font-size: 0.8rem;";
        // Rótulo diferente para a mesma ação: voltar para a edição anterior é
        // reverter, e chamar isso de "ativar" esconderia o que está acontecendo.
        btn.textContent = e.status === "ANTERIOR" ? "Reverter" : "Ativar";
        btn.addEventListener("click", () => ativarEdicao(e));
        celula.appendChild(btn);
    } else if (podeAtivar) {
        const aviso = document.createElement("span");
        aviso.style.cssText = "font-size: 0.75rem; color: var(--text-secondary); text-align: right;";
        aviso.textContent = "reindexe para poder ativar";
        aviso.title = `Rode: python -m scripts.publicacoes.indexar --edicao ${e.rotulo}`;
        celula.appendChild(aviso);
    }

    if (e.tem_relatorio) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-outline-publicacao";
        btn.style.cssText = "padding: 0.3rem 0.7rem; font-size: 0.8rem;";
        btn.textContent = "Relatório";
        btn.addEventListener("click", () => abrirModalRelatorio(e));
        celula.appendChild(btn);
    }

    if (e.status === "ANTERIOR" || e.status === "AGUARDANDO_ATIVACAO") {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-icon";
        btn.style.color = "var(--status-danger)";
        btn.title = "Arquivar (libera os artefatos de disco para descarte)";
        btn.innerHTML = '<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="pointer-events:none;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" /></svg>';
        btn.addEventListener("click", () => arquivarEdicao(e));
        celula.appendChild(btn);
    }
}

/**
 * Ativa (ou reverte para) uma edição, após confirmação nomeando as duas pontas.
 * @param {EdicaoDTO} e
 * @returns {Promise<void>}
 */
async function ativarEdicao(e) {
    const verbo = e.status === "ANTERIOR" ? "Reverter para" : "Ativar";
    if (!confirm(
        `${verbo} a edição "${e.rotulo}"?\n\n` +
        "Todo o sistema passa a consultar esta edição na busca de manuais. " +
        "A edição vigente atual passa a ANTERIOR e continua acessível."
    )) {
        return;
    }

    try {
        await apiFetch(`${URL_EDICOES}/${e.id}/ativar`, { method: "POST" });
        showToast(`Edição "${e.rotulo}" está vigente.`, "success");
        await carregarEdicoes();
    } catch (err) {
        // apiFetch exibe o toast de erro automaticamente se lançado.
    }
}

/**
 * @param {EdicaoDTO} e
 * @returns {Promise<void>}
 */
async function arquivarEdicao(e) {
    if (!confirm(
        `Arquivar a edição "${e.rotulo}"?\n\n` +
        "O catálogo e a auditoria são preservados; o que fica liberado para descarte " +
        "são os artefatos de disco (PDFs e índice) dessa edição."
    )) {
        return;
    }

    try {
        await apiFetch(`${URL_EDICOES}/${e.id}/arquivar`, { method: "POST" });
        showToast(`Edição "${e.rotulo}" arquivada.`, "success");
        await carregarEdicoes();
    } catch (err) {
        // apiFetch exibe o toast de erro automaticamente se lançado.
    }
}

/**
 * Avisa quando há mais edições com índice em disco do que o previsto online.
 *
 * O gate do M4 fala em duas edições retidas (vigente + anterior). Passar disso
 * não é erro — é consumo de disco que ninguém pediu, e que só aparece quando
 * alguém olha. Aviso, nunca remoção automática.
 *
 * @param {EdicaoDTO[]} edicoes
 * @returns {void}
 */
function atualizarAvisoRetencao(edicoes) {
    const aviso = document.getElementById("aviso-retencao-edicoes");
    if (!aviso) return;

    const comIndice = edicoes.filter((e) => e.indice_disponivel);
    const LIMITE = 2;

    if (comIndice.length <= LIMITE) {
        aviso.style.display = "none";
        return;
    }

    aviso.textContent =
        `${comIndice.length} edições têm índice de busca em disco (previsto: ${LIMITE}). ` +
        "Arquivar as que não são mais necessárias libera espaço — nenhuma é removida automaticamente.";
    aviso.style.display = "block";
}

// ==========================================
// Modal: Relatório de diff
// ==========================================

/**
 * @param {EdicaoDTO} e
 * @returns {Promise<void>}
 */
async function abrirModalRelatorio(e) {
    const modal = document.getElementById("modal-relatorio-edicao");
    const titulo = document.getElementById("titulo-relatorio-edicao");
    const conteudo = document.getElementById("conteudo-relatorio-edicao");
    if (!modal || !conteudo) return;

    if (titulo) titulo.textContent = `Relatório de Publicação — ${e.rotulo}`;
    conteudo.textContent = "Carregando...";
    modal.style.display = "flex";

    try {
        const dados = await apiFetch(`${URL_EDICOES}/${e.id}/relatorio`);
        // textContent, não innerHTML: o relatório vem de script e é exibido como
        // texto puro de propósito (nada de markdown renderizado).
        conteudo.textContent = dados.relatorio || "Esta edição não tem relatório de diff — não foi publicada por scripts/publicacoes/publicar.py.";
    } catch (err) {
        conteudo.textContent = "Erro ao carregar o relatório.";
    }
}

/** @returns {void} */
function fecharModalRelatorio() {
    const modal = document.getElementById("modal-relatorio-edicao");
    if (modal) modal.style.display = "none";
}

// ==========================================
// Modal: Status do Acervo
// ==========================================

/** @returns {void} */
function abrirModalStatusAcervo() {
    const modal = document.getElementById("modal-status-acervo");
    if (modal) modal.style.display = "flex";
    carregarStatusAcervo();
}

/** @returns {void} */
function fecharModalStatusAcervo() {
    const modal = document.getElementById("modal-status-acervo");
    if (modal) modal.style.display = "none";
}

/**
 * Um bloco de número + rótulo, no estilo dos cards da página.
 * @param {string} rotulo
 * @param {string} valor
 * @param {string} [cor]
 * @returns {string}
 */
function blocoStatus(rotulo, valor, cor) {
    return `
        <div style="padding: 0.9rem 1rem; border-radius: var(--radius-md); background: rgba(99, 102, 241, 0.06); border: 1px solid var(--border-color);">
            <div style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.03em;">${escapeHtml(rotulo)}</div>
            <div style="font-size: 1.35rem; font-weight: 600; margin-top: 0.25rem; ${cor ? `color: ${cor};` : ""}">${escapeHtml(valor)}</div>
        </div>
    `;
}

/**
 * Carrega `/api/status` e `/api/duplicacao` e monta os blocos.
 * Resiliente a perfil de usuário: `/api/duplicacao` é exclusivo de Admin,
 * enquanto Inspetores/Encarregados também acessam o card de status.
 * @returns {Promise<void>}
 */
async function carregarStatusAcervo() {
    const grid = document.getElementById("grid-status-acervo");
    if (!grid) return;
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding: 1rem;">Carregando...</div>';

    try {
        let status = null;
        let dup = null;

        try {
            status = await apiFetch("/publicacoes/api/status");
        } catch (err) {
            throw err;
        }

        // /api/duplicacao requer privilégio de AdminRequired (403 para Inspetor/Encarregado).
        try {
            dup = await apiFetch("/publicacoes/api/duplicacao");
        } catch (err) {
            dup = null;
        }

        const numero = (/** @type {number} */ n) => Number(n || 0).toLocaleString("pt-BR");
        const atualizado = status.atualizado_em
            ? new Date(status.atualizado_em * 1000).toLocaleString("pt-BR")
            : "—";

        const textoDup = dup
            ? (dup.anterior ? `${numero(dup.duplicados_por_hash)} (vs ${escapeHtml(dup.anterior)})` : "sem edição anterior")
            : "restrito a administradores";

        grid.innerHTML = [
            blocoStatus("Edição vigente", status.edicao || "nenhuma"),
            blocoStatus(
                "Índice de busca",
                status.indice_disponivel ? "disponível" : "indisponível",
                status.indice_disponivel ? "var(--status-ok)" : "var(--status-danger)"
            ),
            blocoStatus("Índice atualizado em", atualizado),
            blocoStatus("Manuais", numero(status.manuais)),
            blocoStatus("Documentos", numero(status.documentos)),
            blocoStatus("Páginas indexadas", numero(status.paginas_indexadas)),
            // Em destaque quando > 0: é o número que dispara a discussão de OCR
            // (M4 tarefa 8), e até aqui não aparecia em lugar nenhum da interface.
            blocoStatus(
                "Documentos sem texto",
                numero(status.documentos_sem_texto),
                status.documentos_sem_texto > 0 ? "var(--status-warning)" : undefined
            ),
            blocoStatus("Mensagens do FIM", numero(status.mensagens_fim)),
            blocoStatus("Duplicados por hash", textoDup),
        ].join("");
    } catch (err) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding: 1rem; color: var(--status-danger);">Erro ao carregar o status do acervo.</div>';
    }
}

// ==========================================
// Upload de Edição (.zip) — M4.Web
// ==========================================

/** @type {string | null} */
let currentUploadJobId = null;
/** @type {ReturnType<typeof setInterval> | null} */
let currentUploadPollingTimer = null;
let isUploading = false;

function toggleAreaUpload() {
    const painel = document.getElementById("painel-upload-edicao");
    if (painel) {
        painel.style.display = painel.style.display === "none" ? "block" : "none";
    }
}

/**
 * @param {Event} event
 */
async function tratarSubmitUpload(event) {
    event.preventDefault();
    if (isUploading) return;

    const inputRotulo = /** @type {HTMLInputElement} */ (document.getElementById("upload-edicao-rotulo"));
    const inputArquivo = /** @type {HTMLInputElement} */ (document.getElementById("upload-edicao-arquivo"));
    const btnSubmit = /** @type {HTMLButtonElement} */ (document.getElementById("btn-iniciar-upload"));

    if (!inputRotulo || !inputArquivo || !inputArquivo.files || inputArquivo.files.length === 0) {
        showToast("Selecione um arquivo .zip e informe o rótulo.", "warning");
        return;
    }

    const rotulo = inputRotulo.value.trim();
    const file = inputArquivo.files[0];

    if (!file.name.toLowerCase().endsWith(".zip")) {
        showToast("O arquivo deve ser um pacote .zip.", "warning");
        return;
    }

    const inputModo = document.querySelector('input[name="upload-modo-processamento"]:checked');
    const modoProcessamento = inputModo ? /** @type {HTMLInputElement} */ (inputModo).value : "AGENDADO";

    isUploading = true;
    if (btnSubmit) btnSubmit.disabled = true;
    const containerStatus = document.getElementById("status-upload-container");
    if (containerStatus) containerStatus.style.display = "flex";

    atualizarBarraUpload("Iniciando upload...", 0);

    try {
        // 1. Iniciar upload job no servidor
        const initResp = await apiFetch("/publicacoes/api/edicoes/uploads", {
            method: "POST",
            body: {
                rotulo: rotulo,
                tamanho_bytes: file.size,
                nome_arquivo: file.name,
                modo_processamento: modoProcessamento,
            },
        });

        currentUploadJobId = initResp.job_id;
        const tamanhoParte = (initResp.tamanho_parte_mb || 100) * 1024 * 1024;
        const totalPartes = Math.ceil(file.size / tamanhoParte);
        const partesEtags = [];

        // 2. Enviar partes
        for (let i = 0; i < totalPartes; i++) {
            if (!isUploading || !currentUploadJobId) {
                return; // Interrompe se o upload foi cancelado
            }

            const numeroParte = i + 1;
            const start = i * tamanhoParte;
            const end = Math.min(start + tamanhoParte, file.size);
            const chunk = file.slice(start, end);

            const pctEtapa = Math.round((i / totalPartes) * 40);
            atualizarBarraUpload(`Enviando parte ${numeroParte} de ${totalPartes}...`, pctEtapa);

            const parteResp = await apiFetch(`/publicacoes/api/edicoes/uploads/${currentUploadJobId}/partes?numero=${numeroParte}`, {
                method: "POST",
            });

            let etag = "";
            if (parteResp.url.includes("/publicacoes/api/edicoes/uploads/local-parte")) {
                const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                const csrfToken = csrfMeta ? (csrfMeta.getAttribute("content") || "") : "";
                const localResp = await fetch(parteResp.url, {
                    method: "PUT",
                    body: chunk,
                    headers: {
                        "X-CSRF-Token": csrfToken,
                    },
                    credentials: "same-origin",
                });
                // O CSRFMiddleware rotaciona o cookie+token a cada requisicao
                // mutante bem-sucedida. Este PUT usa fetch() bruto (nao apiFetch),
                // entao precisa sincronizar manualmente o meta tag com o novo
                // token — senao a proxima chamada apiFetch envia um token velho
                // e recebe 403 (CSRF), interrompendo o envio na parte seguinte.
                const novoToken = localResp.headers.get("X-CSRF-Token");
                if (novoToken && csrfMeta) csrfMeta.setAttribute("content", novoToken);
                if (!localResp.ok) throw new Error(`Falha no upload da parte ${numeroParte} local.`);
                const localJson = await localResp.json();
                etag = localJson.etag;
            } else {
                const r2Resp = await fetch(parteResp.url, {
                    method: "PUT",
                    body: chunk,
                });
                if (!r2Resp.ok) throw new Error(`Falha no upload da parte ${numeroParte} para o storage.`);
                etag = r2Resp.headers.get("ETag") || `etag-${numeroParte}`;
            }

            partesEtags.push({ numero: numeroParte, etag: etag });
        }

        if (!isUploading || !currentUploadJobId) return;

        // 3. Concluir multipart
        atualizarBarraUpload("Consolidando partes no storage...", 45);
        await apiFetch(`/publicacoes/api/edicoes/uploads/${currentUploadJobId}/concluir`, {
            method: "POST",
            body: { partes: partesEtags },
        });

        // 4. Iniciar Polling de progresso
        iniciarPollingUpload(currentUploadJobId);
    } catch (/** @type {any} */ err) {
        atualizarBarraUpload(`Erro: ${err.message || err}`, 0);
        if (btnSubmit) btnSubmit.disabled = false;
        isUploading = false;
    }
}

function iniciarPollingUpload(jobId) {
    if (currentUploadPollingTimer) {
        clearInterval(currentUploadPollingTimer);
        currentUploadPollingTimer = null;
    }

    const checarStatus = async () => {
        if (!currentUploadJobId) {
            if (currentUploadPollingTimer) {
                clearInterval(currentUploadPollingTimer);
                currentUploadPollingTimer = null;
            }
            return;
        }

        try {
            const job = await apiFetch(`/publicacoes/api/edicoes/uploads/${jobId}`);
            atualizarBarraUpload(job.etapa || "Processando...", job.progresso_pct || 50);

            if (job.status === "CONCLUIDO") {
                if (currentUploadPollingTimer) {
                    clearInterval(currentUploadPollingTimer);
                    currentUploadPollingTimer = null;
                }
                showToast(`Edição "${job.rotulo}" enviada e processada com sucesso!`, "success");
                carregarEdicoes();
                resetarFormUpload();
            } else if (job.status === "FALHOU") {
                if (currentUploadPollingTimer) {
                    clearInterval(currentUploadPollingTimer);
                    currentUploadPollingTimer = null;
                }
                showToast(`Erro no processamento: ${job.erro || 'Falha desconhecida'}`, "error");
                atualizarBarraUpload(`Falhou: ${job.erro || 'Erro no servidor'}`, 0);
                const btnSubmit = /** @type {HTMLButtonElement} */ (document.getElementById("btn-iniciar-upload"));
                if (btnSubmit) btnSubmit.disabled = false;
                isUploading = false;
            } else if (job.status === "CANCELADO") {
                if (currentUploadPollingTimer) {
                    clearInterval(currentUploadPollingTimer);
                    currentUploadPollingTimer = null;
                }
                showToast("Upload cancelado.", "info");
                resetarFormUpload();
            } else if (job.status === "AGUARDANDO_PROCESSAMENTO") {
                // Processamento agendado para a madrugada — não faz sentido manter
                // o navegador enviando ping a cada 3s por horas. O job já está
                // seguro no servidor; o usuário confere o resultado mais tarde
                // pela lista de edições.
                if (currentUploadPollingTimer) {
                    clearInterval(currentUploadPollingTimer);
                    currentUploadPollingTimer = null;
                }
                showToast(job.etapa || "Upload concluído. Processamento agendado para a madrugada.", "success");
                resetarFormUpload();
            }
        } catch (err) {
            console.error("Erro ao checar status do job de upload:", err);
        }
    };

    currentUploadPollingTimer = setInterval(checarStatus, 3000);
    checarStatus();
}

async function cancelarUploadAtual() {
    if (!currentUploadJobId) return;
    const jobId = currentUploadJobId;
    resetarFormUpload();

    try {
        await apiFetch(`/publicacoes/api/edicoes/uploads/${jobId}/cancelar`, { method: "POST" });
        showToast("Solicitação de cancelamento enviada.", "info");
    } catch (err) {
        // apiFetch trata o erro de rede/API se ocorrer.
    }
}

function atualizarBarraUpload(etapaTexto, pct) {
    const textEtapa = document.getElementById("text-upload-etapa");
    const textPct = document.getElementById("text-upload-pct");
    const bar = document.getElementById("bar-upload-progresso");

    if (textEtapa) textEtapa.textContent = etapaTexto;
    if (textPct) textPct.textContent = `${pct}%`;
    if (bar) bar.style.width = `${pct}%`;
}

function resetarFormUpload() {
    if (currentUploadPollingTimer) {
        clearInterval(currentUploadPollingTimer);
        currentUploadPollingTimer = null;
    }
    isUploading = false;
    currentUploadJobId = null;

    const form = /** @type {HTMLFormElement} */ (document.getElementById("form-upload-edicao"));
    if (form) form.reset();
    const btnSubmit = /** @type {HTMLButtonElement} */ (document.getElementById("btn-iniciar-upload"));
    if (btnSubmit) btnSubmit.disabled = false;
    const containerStatus = document.getElementById("status-upload-container");
    if (containerStatus) containerStatus.style.display = "none";
}


