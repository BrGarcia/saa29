/**
 * app/web/static/js/publicacoes_explorador.js
 * Explorador de arquivos do acervo de manuais — árvore Categoria → Manual →
 * Capítulo, busca por nome/conteúdo, resolução de mensagem do FIM.
 *
 * Client-fetch puro sobre os endpoints do módulo — nenhuma lógica de negócio
 * aqui, só apresentação:
 *   - GET /api/manuais                              (árvore, nível 1)
 *   - GET /api/manuais/{codigo}/capitulos            (árvore, nível 2 — sob demanda)
 *   - GET /api/manuais/{codigo}/documentos           (painel de documentos, paginado)
 *   - GET /api/catalogo/busca                        (busca por NOME)
 *   - GET /api/busca                                 (busca por CONTEÚDO)
 *   - GET /api/fim                                   (mensagem CAS/EICAS → procedimento)
 *
 * `apiFetch`/`escapeHtml`/`showToast` vêm de app.js (script clássico, roda
 * antes deste) e ficam disponíveis como globais — sem import.
 *
 * Estado da árvore: Categoria (nível 0, em memória) → Manual (nível 1, em
 * memória) → Capítulo (nível 2, carregado sob demanda ao abrir o manual) →
 * Documento (nível 3, carregado sob demanda ao abrir o capítulo).
 *
 * Os documentos entram na árvore por capítulo, nunca em bloco: cada capítulo
 * carrega no máximo `LIMITE_DOCUMENTOS_ARVORE` PDFs (o teto do endpoint), e o
 * excedente vira um nó "mais N documentos…" que leva à listagem paginada do
 * painel — a árvore nunca tenta segurar os milhares de documentos do acervo.
 *
 * Selecionar um documento NÃO troca de página: o PDF abre no próprio painel
 * direito, no mesmo shell da página dedicada
 * (`templates/publicacoes/_viewer_shell.html`), montado por `criarViewer()` de
 * `publicacoes_viewer.js` — importado dinamicamente na primeira vez que um
 * documento é aberto, porque puxa o build do PDF.js junto.
 *
 * `capitulo` distingue dois estados que parecem iguais e não são:
 *   - `null`      → nenhum capítulo selecionado (painel mostra os capítulos)
 *   - `""`        → "(raiz do manual)", capítulo real e válido (RN do acervo:
 *                    PDFs soltos na raiz de um manual têm `capitulo=""` no
 *                    banco — não confundir com "nada selecionado")
 *
 * `?q=` na URL é um contrato com quem já linkava para a busca desta página
 * (o checklist de inspeção, `inspecao_detalhe.js`) — dispara a busca "no
 * conteúdo" automaticamente ao abrir, mesmo efeito que a tela antiga tinha.
 *
 * Origem (Manutenção/Operacional): filtro, não nível novo da árvore — a
 * hierarquia continua Categoria → Manual → Capítulo. O mesmo `codigo` de
 * manual pode existir nas duas origens dentro da mesma edição vigente (os
 * dois discos do acervo, ver
 * docs/backlog/modulo_publicacoes/12_refinamento_gestao_e_envio.md §6 —
 * esta rodada não mescla revisão, só lista as duas lado a lado). Por isso
 * `codigo` sozinho NUNCA é chave de manual aqui — sempre `chaveManual(codigo,
 * origem)`, inclusive nos `Map`/`Set` de estado e no contrato de URL.
 */
(function () {
    "use strict";

    const raiz = document.getElementById("pub-acervo-app");
    if (!raiz) return;

    const CHAVE_VIEW = "pubAcervoViewMode";
    const CHAVE_ORDEM = "pubAcervoOrdemNome";
    const CHAVE_FILTRO_ORIGEM = "pubAcervoFiltroOrigem";
    const LIMITE_DOCUMENTOS = 60;
    /** Teto de `/api/manuais/{codigo}/documentos` — o resto do capítulo fica no painel. */
    const LIMITE_DOCUMENTOS_ARVORE = 100;

    /** Chave composta de manual — `codigo` sozinho colide entre origens. */
    function chaveManual(codigo, origem) {
        return `${origem}::${codigo}`;
    }

    /** Chave de capítulo — `""` (raiz do manual) é capítulo válido, não "nenhum". */
    function chaveCapitulo(codigo, origem, capitulo) {
        return `${chaveManual(codigo, origem)}::${capitulo}`;
    }

    const ICONE_CHEVRON =
        '<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m9 18 6-6-6-6"/></svg>';

    const ICONE_PASTA =
        '<svg width="17" height="17" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
        'd="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg>';

    const ICONE_PASTA_ABERTA =
        '<svg width="17" height="17" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
        'd="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2H3Z"/>' +
        '<path stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
        'd="m3 7 1.4 9.1A2 2 0 0 0 6.4 18h11.2a2 2 0 0 0 2-1.9L21 9H3Z"/></svg>';

    const ICONE_DOCUMENTO =
        '<svg width="17" height="17" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
        'd="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/>' +
        '<path stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M14 2v6h6"/></svg>';

    const els = {
        arvore: document.getElementById("pub-acervo-arvore"),
        painel: document.getElementById("pub-acervo-painel"),
        breadcrumb: document.getElementById("pub-acervo-breadcrumb"),
        btnVoltar: document.getElementById("pub-acervo-voltar"),
        btnAvancar: document.getElementById("pub-acervo-avancar"),
        btnRaiz: document.getElementById("pub-acervo-raiz"),
        btnLista: document.getElementById("pub-acervo-view-lista"),
        btnIcones: document.getElementById("pub-acervo-view-icones"),
        btnOrdenar: document.getElementById("pub-acervo-ordenar"),
        buscaInput: document.getElementById("pub-acervo-busca-input"),
        buscaResultados: document.getElementById("pub-acervo-busca-resultados"),
        buscaModos: document.querySelectorAll(".pub-acervo-busca-modos button"),
        fimInput: document.getElementById("pub-acervo-fim-input"),
        fimBtn: document.getElementById("pub-acervo-fim-btn"),
        fimResultados: document.getElementById("pub-acervo-fim-resultados"),
        filtroOrigemBtns: document.querySelectorAll(".pub-acervo-filtro-origem button"),
        viewer: document.getElementById("pub-acervo-viewer"),
        viewerShell: document.getElementById("pub-viewer-shell"),
        viewerContexto: document.getElementById("pub-viewer-context"),
    };

    const estado = {
        manuaisTodos: [],
        /** Lista completa (as duas origens), vinda de uma só chamada a `/api/manuais`. */
        categoriaOrdem: [],
        manuaisPorCategoria: new Map(),
        /** Reconstruídos por `reconstruirAgrupamento()` a cada troca do filtro de origem. */
        manuaisPorCodigo: new Map(),
        /** Chave composta (`chaveManual`) — nunca `codigo` sozinho. */
        capitulosPorManual: new Map(),
        /** Idem — chave composta. */
        documentosPorCapitulo: new Map(),
        /** Chave de `chaveCapitulo` → `"carregando"` | `{ total, results }`. */
        categoriasAbertas: new Set(),
        manuaisAbertos: new Set(),
        /** Idem — chave composta. */
        capitulosAbertos: new Set(),
        /** Chave de `chaveCapitulo`. */
        atual: { categoria: null, manual: null, origem: null, capitulo: null, doc: null, pagina: 1, offset: 0 },
        viewMode: localStorage.getItem(CHAVE_VIEW) === "icones" ? "icones" : "lista",
        ordemNome: localStorage.getItem(CHAVE_ORDEM) === "1",
        filtroOrigem: ["MANUTENCAO", "OPERACIONAL"].includes(localStorage.getItem(CHAVE_FILTRO_ORIGEM))
            ? localStorage.getItem(CHAVE_FILTRO_ORIGEM)
            : "MANUTENCAO",
        modoBusca: "nome",
        buscaSeq: 0,
    };

    /** Rótulo curto de origem, para badges/breadcrumb quando o filtro é "Todos". */
    function rotuloOrigem(origem) {
        return origem === "OPERACIONAL" ? "Operacional" : "Manutenção";
    }

    // --------------------------------------------------------------------
    // Carga de dados
    // --------------------------------------------------------------------

    async function carregarManuais() {
        try {
            const manuais = await apiFetch("/publicacoes/api/manuais");
            estado.manuaisTodos = manuais;
            manuais.forEach((m) => estado.manuaisPorCodigo.set(chaveManual(m.codigo, m.origem), m));
            reconstruirAgrupamento();
        } catch (e) {
            // apiFetch já notificou — a árvore fica vazia, com o estado tratado no render.
        }
    }

    /**
     * Reconstrói `categoriaOrdem`/`manuaisPorCategoria` a partir de
     * `manuaisTodos`, aplicando `estado.filtroOrigem` — sem nova requisição
     * (o filtro é 100% cliente, igual ao agrupamento por categoria já era).
     */
    function reconstruirAgrupamento() {
        estado.categoriaOrdem = [];
        estado.manuaisPorCategoria = new Map();
        const visiveis =
            estado.filtroOrigem === "TODOS"
                ? estado.manuaisTodos
                : estado.manuaisTodos.filter((m) => m.origem === estado.filtroOrigem);
        visiveis.forEach((m) => {
            if (!estado.manuaisPorCategoria.has(m.categoria)) {
                estado.manuaisPorCategoria.set(m.categoria, []);
                estado.categoriaOrdem.push(m.categoria);
            }
            estado.manuaisPorCategoria.get(m.categoria).push(m);
        });
    }

    /**
     * Resolve um manual por código, desambiguando por origem quando dada.
     * Sem origem (link antigo, mobile): MANUTENCAO vence — mesmo critério de
     * `service._manual_da_edicao_vigente` no backend.
     */
    function buscarManual(codigo, origem) {
        if (!codigo) return null;
        if (origem) return estado.manuaisPorCodigo.get(chaveManual(codigo, origem)) || null;
        return (
            estado.manuaisPorCodigo.get(chaveManual(codigo, "MANUTENCAO")) ||
            estado.manuaisTodos.find((m) => m.codigo === codigo) ||
            null
        );
    }

    async function carregarCapitulos(codigoManual, origem) {
        const chave = chaveManual(codigoManual, origem);
        if (Array.isArray(estado.capitulosPorManual.get(chave))) return;
        estado.capitulosPorManual.set(chave, "carregando");
        try {
            const params = new URLSearchParams();
            if (origem) params.set("origem", origem);
            const qs = params.toString();
            const resp = await apiFetch(
                `/publicacoes/api/manuais/${encodeURIComponent(codigoManual)}/capitulos${qs ? `?${qs}` : ""}`
            );
            estado.capitulosPorManual.set(chave, resp.capitulos);
        } catch (e) {
            estado.capitulosPorManual.set(chave, []);
        }
    }

    /**
     * Documentos de um capítulo para a árvore — a primeira página só, até
     * `LIMITE_DOCUMENTOS_ARVORE`. `total` fica guardado para o nó de excedente.
     */
    async function carregarDocumentosDoCapitulo(codigoManual, origem, capitulo) {
        const chave = chaveCapitulo(codigoManual, origem, capitulo);
        const cache = estado.documentosPorCapitulo.get(chave);
        if (cache && cache !== "carregando") return;
        estado.documentosPorCapitulo.set(chave, "carregando");
        try {
            const params = new URLSearchParams({
                limit: String(LIMITE_DOCUMENTOS_ARVORE),
                offset: "0",
            });
            params.set("capitulo", capitulo); // "" (raiz do manual) é valor válido
            if (origem) params.set("origem", origem);
            const resp = await apiFetch(
                `/publicacoes/api/manuais/${encodeURIComponent(codigoManual)}/documentos?${params.toString()}`
            );
            estado.documentosPorCapitulo.set(chave, { total: resp.total, results: resp.results });
        } catch (e) {
            estado.documentosPorCapitulo.set(chave, { total: 0, results: [] });
        }
    }

    function ordenarSeNecessario(lista, extrator) {
        if (!estado.ordemNome) return lista;
        return [...lista].sort((a, b) => extrator(a).localeCompare(extrator(b), "pt-BR"));
    }

    // --------------------------------------------------------------------
    // Navegação — estado, URL e histórico
    // --------------------------------------------------------------------

    function normalizarAlvo(alvo) {
        const out = {
            categoria: alvo.categoria || null,
            manual: alvo.manual || null,
            origem: alvo.origem || null,
            capitulo: alvo.capitulo === undefined ? null : alvo.capitulo,
            doc: alvo.doc || null,
            pagina: alvo.pagina || 1,
            offset: alvo.offset || 0,
        };
        if (out.manual) {
            const m = buscarManual(out.manual, out.origem);
            if (m) {
                out.origem = m.origem;
                if (!out.categoria) out.categoria = m.categoria;
            }
        }
        if (!out.manual) {
            out.capitulo = null;
            out.origem = null;
        }
        return out;
    }

    function estadoParaQueryString(alvo) {
        const params = new URLSearchParams();
        if (alvo.categoria) params.set("categoria", alvo.categoria);
        if (alvo.manual) params.set("manual", alvo.manual);
        if (alvo.manual && alvo.origem) params.set("origem", alvo.origem);
        if (alvo.capitulo !== null) params.set("capitulo", alvo.capitulo);
        if (alvo.doc) params.set("doc", alvo.doc);
        if (alvo.doc && alvo.pagina > 1) params.set("pagina", String(alvo.pagina));
        if (alvo.offset) params.set("offset", String(alvo.offset));
        const texto = params.toString();
        return texto ? `?${texto}` : "";
    }

    function alvoDaUrl() {
        const params = new URLSearchParams(window.location.search);
        return {
            categoria: params.get("categoria"),
            manual: params.get("manual"),
            origem: params.get("origem"),
            capitulo: params.has("capitulo") ? params.get("capitulo") : null,
            doc: params.get("doc"),
            pagina: parseInt(params.get("pagina") || "1", 10) || 1,
            offset: parseInt(params.get("offset") || "0", 10) || 0,
        };
    }

    async function irPara(alvoBruto, { historico = true } = {}) {
        const alvo = normalizarAlvo(alvoBruto);
        estado.atual = alvo;
        if (alvo.categoria) estado.categoriasAbertas.add(alvo.categoria);
        if (alvo.manual) {
            estado.manuaisAbertos.add(chaveManual(alvo.manual, alvo.origem));
            await carregarCapitulos(alvo.manual, alvo.origem);
        }
        // Com um documento selecionado a árvore precisa mostrar onde ele está —
        // abre o capítulo e garante que a lista de PDFs dele esteja carregada.
        if (alvo.manual && alvo.capitulo !== null && alvo.doc) {
            estado.capitulosAbertos.add(chaveCapitulo(alvo.manual, alvo.origem, alvo.capitulo));
            await carregarDocumentosDoCapitulo(alvo.manual, alvo.origem, alvo.capitulo);
        }
        if (historico) {
            history.pushState(null, "", `${window.location.pathname}${estadoParaQueryString(alvo)}`);
        }
        renderArvore();
        renderBreadcrumb();
        await renderPainel();
    }

    window.addEventListener("popstate", () => {
        irPara(alvoDaUrl(), { historico: false });
    });

    // --------------------------------------------------------------------
    // Árvore
    // --------------------------------------------------------------------

    function criarNoArvore({ nivel, temFilhos, aberto, selecionado, icone, rotulo, contagem, onClickLinha, onClickChevron }) {
        const el = document.createElement("div");
        el.className = "pub-acervo-node" + (aberto ? " is-aberto" : "") + (selecionado ? " is-selecionado" : "");
        el.style.setProperty("--pub-acervo-nivel", String(nivel));
        el.setAttribute("role", "treeitem");
        if (temFilhos) el.setAttribute("aria-expanded", String(aberto));

        const chevron = document.createElement("span");
        chevron.className = "pub-acervo-node-chevron" + (temFilhos ? "" : " is-invisivel");
        chevron.innerHTML = ICONE_CHEVRON;
        if (temFilhos) {
            chevron.addEventListener("click", (e) => {
                e.stopPropagation();
                onClickChevron();
            });
        }

        const iconeEl = document.createElement("span");
        iconeEl.className = "pub-acervo-node-icone";
        iconeEl.innerHTML = icone;

        const rotuloEl = document.createElement("span");
        rotuloEl.className = "pub-acervo-node-rotulo";
        rotuloEl.textContent = rotulo;
        rotuloEl.title = rotulo;

        el.append(chevron, iconeEl, rotuloEl);
        if (contagem !== null && contagem !== undefined) {
            const contagemEl = document.createElement("span");
            contagemEl.className = "pub-acervo-node-contagem";
            contagemEl.textContent = String(contagem);
            el.append(contagemEl);
        }
        el.addEventListener("click", onClickLinha);
        return el;
    }

    /**
     * Nível 3 da árvore: os PDFs de um capítulo aberto. Clicar num deles abre
     * o documento no painel direito (viewer embutido), sem trocar de página.
     */
    function renderDocumentosDaArvore(container, manual, cap) {
        const chaveCap = chaveCapitulo(manual.codigo, manual.origem, cap.capitulo);
        const dados = estado.documentosPorCapitulo.get(chaveCap);

        if (!dados || dados === "carregando") {
            const carregando = document.createElement("div");
            carregando.className = "pub-acervo-node-carregando";
            carregando.style.setProperty("--pub-acervo-nivel", "3");
            carregando.textContent = "Carregando documentos…";
            container.appendChild(carregando);
            return;
        }

        if (dados.results.length === 0) {
            const vazio = document.createElement("div");
            vazio.className = "pub-acervo-node-carregando";
            vazio.style.setProperty("--pub-acervo-nivel", "3");
            vazio.textContent = "Nenhum documento.";
            container.appendChild(vazio);
            return;
        }

        ordenarSeNecessario(dados.results, (d) => d.titulo).forEach((doc) => {
            container.appendChild(
                criarNoArvore({
                    nivel: 3,
                    temFilhos: false,
                    aberto: false,
                    selecionado: estado.atual.doc === doc.doc_id,
                    icone: ICONE_DOCUMENTO,
                    rotulo: doc.titulo,
                    contagem: doc.paginas ? `${doc.paginas}p` : null,
                    onClickLinha: () =>
                        irPara({
                            manual: manual.codigo,
                            origem: manual.origem,
                            capitulo: cap.capitulo,
                            doc: doc.doc_id,
                        }),
                    onClickChevron: () => {},
                })
            );
        });

        // O endpoint tem teto de 100 por página: o que passa disso não cabe na
        // árvore, mas continua alcançável pela listagem paginada do painel.
        if (dados.total > dados.results.length) {
            const restante = dados.total - dados.results.length;
            const mais = document.createElement("div");
            mais.className = "pub-acervo-node-carregando pub-acervo-node-mais";
            mais.style.setProperty("--pub-acervo-nivel", "3");
            mais.textContent = `mais ${restante} documento(s) — abrir listagem`;
            mais.addEventListener("click", () =>
                irPara({
                    manual: manual.codigo,
                    origem: manual.origem,
                    capitulo: cap.capitulo,
                    offset: LIMITE_DOCUMENTOS,
                })
            );
            container.appendChild(mais);
        }
    }

    function renderArvore() {
        els.arvore.innerHTML = "";
        if (estado.categoriaOrdem.length === 0) {
            els.arvore.innerHTML =
                '<div class="pub-acervo-estado-vazio">O acervo ainda não foi indexado nesta instância.</div>';
            return;
        }

        estado.categoriaOrdem.forEach((categoria) => {
            const manuais = estado.manuaisPorCategoria.get(categoria) || [];
            const abertaCategoria = estado.categoriasAbertas.has(categoria);

            els.arvore.appendChild(
                criarNoArvore({
                    nivel: 0,
                    temFilhos: true,
                    aberto: abertaCategoria,
                    selecionado: estado.atual.categoria === categoria && !estado.atual.manual,
                    icone: abertaCategoria ? ICONE_PASTA_ABERTA : ICONE_PASTA,
                    rotulo: categoria,
                    contagem: `(${manuais.length})`,
                    onClickLinha: () => {
                        estado.categoriasAbertas.add(categoria);
                        irPara({ categoria, manual: null, capitulo: null, offset: 0 });
                    },
                    onClickChevron: () => {
                        if (estado.categoriasAbertas.has(categoria)) estado.categoriasAbertas.delete(categoria);
                        else estado.categoriasAbertas.add(categoria);
                        renderArvore();
                    },
                })
            );

            const filhosCategoria = document.createElement("div");
            filhosCategoria.className = "pub-acervo-filhos" + (abertaCategoria ? " is-aberto" : "");

            manuais.forEach((manual) => {
                const chaveM = chaveManual(manual.codigo, manual.origem);
                const abertoManual = estado.manuaisAbertos.has(chaveM);
                // Badge de origem só quando "Todos" — com um filtro ativo, todo
                // mundo na árvore já é da mesma origem, o rótulo seria ruído.
                const rotuloManual =
                    estado.filtroOrigem === "TODOS"
                        ? `${manual.descricao} · ${rotuloOrigem(manual.origem)}`
                        : manual.descricao;
                filhosCategoria.appendChild(
                    criarNoArvore({
                        nivel: 1,
                        temFilhos: true,
                        aberto: abertoManual,
                        selecionado:
                            estado.atual.manual === manual.codigo &&
                            estado.atual.origem === manual.origem &&
                            estado.atual.capitulo === null,
                        icone: abertoManual ? ICONE_PASTA_ABERTA : ICONE_PASTA,
                        rotulo: rotuloManual,
                        contagem: manual.documentos,
                        onClickLinha: () => {
                            estado.manuaisAbertos.add(chaveM);
                            irPara({ manual: manual.codigo, origem: manual.origem, capitulo: null, offset: 0 });
                        },
                        onClickChevron: () => {
                            if (estado.manuaisAbertos.has(chaveM)) {
                                estado.manuaisAbertos.delete(chaveM);
                                renderArvore();
                            } else {
                                estado.manuaisAbertos.add(chaveM);
                                renderArvore();
                                carregarCapitulos(manual.codigo, manual.origem).then(renderArvore);
                            }
                        },
                    })
                );

                const filhosManual = document.createElement("div");
                filhosManual.className = "pub-acervo-filhos" + (abertoManual ? " is-aberto" : "");
                if (abertoManual) {
                    const capitulos = estado.capitulosPorManual.get(chaveM);
                    if (!Array.isArray(capitulos)) {
                        const carregando = document.createElement("div");
                        carregando.className = "pub-acervo-node-carregando";
                        carregando.style.setProperty("--pub-acervo-nivel", "2");
                        carregando.textContent = "Carregando capítulos…";
                        filhosManual.appendChild(carregando);
                    } else {
                        capitulos.forEach((cap) => {
                            const rotuloCap = cap.capitulo || "(raiz do manual)";
                            const chaveCap = chaveCapitulo(manual.codigo, manual.origem, cap.capitulo);
                            const abertoCap = estado.capitulosAbertos.has(chaveCap);
                            filhosManual.appendChild(
                                criarNoArvore({
                                    nivel: 2,
                                    temFilhos: true,
                                    aberto: abertoCap,
                                    selecionado:
                                        estado.atual.manual === manual.codigo &&
                                        estado.atual.origem === manual.origem &&
                                        estado.atual.capitulo === cap.capitulo &&
                                        !estado.atual.doc,
                                    icone: abertoCap ? ICONE_PASTA_ABERTA : ICONE_PASTA,
                                    rotulo: cap.ata_codigo ? `ATA ${cap.ata_codigo} — ${rotuloCap}` : rotuloCap,
                                    contagem: cap.documentos,
                                    onClickLinha: () => {
                                        estado.capitulosAbertos.add(chaveCap);
                                        carregarDocumentosDoCapitulo(
                                            manual.codigo,
                                            manual.origem,
                                            cap.capitulo
                                        ).then(renderArvore);
                                        irPara({
                                            manual: manual.codigo,
                                            origem: manual.origem,
                                            capitulo: cap.capitulo,
                                            offset: 0,
                                        });
                                    },
                                    onClickChevron: () => {
                                        if (estado.capitulosAbertos.has(chaveCap)) {
                                            estado.capitulosAbertos.delete(chaveCap);
                                            renderArvore();
                                        } else {
                                            estado.capitulosAbertos.add(chaveCap);
                                            renderArvore();
                                            carregarDocumentosDoCapitulo(
                                                manual.codigo,
                                                manual.origem,
                                                cap.capitulo
                                            ).then(renderArvore);
                                        }
                                    },
                                })
                            );

                            const filhosCapitulo = document.createElement("div");
                            filhosCapitulo.className =
                                "pub-acervo-filhos" + (abertoCap ? " is-aberto" : "");
                            if (abertoCap) {
                                renderDocumentosDaArvore(filhosCapitulo, manual, cap);
                            }
                            filhosManual.appendChild(filhosCapitulo);
                        });
                    }
                }
                filhosCategoria.appendChild(filhosManual);
            });

            els.arvore.appendChild(filhosCategoria);
        });
    }

    // --------------------------------------------------------------------
    // Breadcrumb
    // --------------------------------------------------------------------

    /** Título de um documento já visto em algum capítulo carregado (só para o breadcrumb). */
    function tituloDoDocumento(docId) {
        for (const dados of estado.documentosPorCapitulo.values()) {
            if (!dados || dados === "carregando") continue;
            const achado = dados.results.find((d) => d.doc_id === docId);
            if (achado) return achado.titulo;
        }
        return "Documento";
    }

    function renderBreadcrumb() {
        els.breadcrumb.innerHTML = "";
        const { categoria, manual, origem, capitulo, doc } = estado.atual;

        const segmentos = [
            {
                rotulo: "Acervo",
                onClick: () => irPara({ categoria: null, manual: null, origem: null, capitulo: null, offset: 0 }),
            },
        ];
        if (categoria) {
            segmentos.push({
                rotulo: categoria,
                onClick: () => irPara({ categoria, manual: null, origem: null, capitulo: null, offset: 0 }),
            });
        }
        if (manual) {
            const m = buscarManual(manual, origem);
            const rotuloManual =
                m && estado.filtroOrigem === "TODOS"
                    ? `${m.descricao} (${rotuloOrigem(origem)})`
                    : m
                      ? m.descricao
                      : manual;
            segmentos.push({
                rotulo: rotuloManual,
                onClick: () => irPara({ categoria, manual, origem, capitulo: null, offset: 0 }),
            });
        }
        if (capitulo !== null) {
            segmentos.push({
                rotulo: capitulo || "(raiz do manual)",
                onClick: () => irPara({ categoria, manual, origem, capitulo, doc: null, offset: 0 }),
            });
        }
        if (doc) {
            segmentos.push({ rotulo: tituloDoDocumento(doc), onClick: null });
        }

        segmentos.forEach((seg, i) => {
            if (i > 0) {
                const sep = document.createElement("span");
                sep.className = "pub-acervo-breadcrumb-sep";
                sep.textContent = "›";
                els.breadcrumb.appendChild(sep);
            }
            const btn = document.createElement("button");
            btn.type = "button";
            const ehAtual = i === segmentos.length - 1;
            if (ehAtual) {
                btn.className = "is-atual";
                btn.disabled = true;
            } else {
                btn.addEventListener("click", seg.onClick);
            }
            btn.textContent = seg.rotulo;
            els.breadcrumb.appendChild(btn);
        });
    }

    // --------------------------------------------------------------------
    // Painel de conteúdo
    // --------------------------------------------------------------------

    function criarCard(item, iconeSvg) {
        const el = document.createElement("div");
        if (estado.viewMode === "icones") {
            el.className = "pub-acervo-item-icone";
            el.innerHTML =
                `<span class="pub-acervo-item-icone-icone">${iconeSvg}</span>` +
                `<span class="pub-acervo-item-icone-titulo">${escapeHtml(item.rotulo)}</span>` +
                `<span class="pub-acervo-item-icone-meta">${escapeHtml(item.meta)}</span>`;
        } else {
            el.className = "pub-acervo-item-lista";
            el.innerHTML =
                `<span class="pub-acervo-item-lista-icone">${iconeSvg}</span>` +
                `<span class="pub-acervo-item-lista-info">` +
                `<div class="pub-acervo-item-lista-titulo">${escapeHtml(item.rotulo)}</div>` +
                `<div class="pub-acervo-item-lista-meta">${escapeHtml(item.meta)}</div>` +
                `</span>`;
        }
        el.addEventListener("click", item.onClick);
        return el;
    }

    function renderCards(itens, iconeSvg) {
        els.painel.innerHTML = "";
        if (itens.length === 0) {
            els.painel.innerHTML = '<div class="pub-acervo-estado-vazio">Nada aqui ainda.</div>';
            return;
        }
        const container = document.createElement("div");
        container.className = estado.viewMode === "icones" ? "pub-acervo-grid" : "pub-acervo-lista";
        itens.forEach((item) => container.appendChild(criarCard(item, iconeSvg)));
        els.painel.appendChild(container);
    }

    async function renderDocumentos(codigoManual, origem, capitulo, offset) {
        els.painel.innerHTML = '<div class="pub-acervo-estado-vazio">Carregando documentos…</div>';
        const params = new URLSearchParams({ limit: String(LIMITE_DOCUMENTOS), offset: String(offset) });
        params.set("capitulo", capitulo); // "" (raiz do manual) é valor válido de query string
        if (origem) params.set("origem", origem);

        let resposta;
        try {
            resposta = await apiFetch(
                `/publicacoes/api/manuais/${encodeURIComponent(codigoManual)}/documentos?${params.toString()}`
            );
        } catch (e) {
            els.painel.innerHTML = '<div class="pub-acervo-estado-vazio">Não foi possível carregar os documentos.</div>';
            return;
        }
        if (resposta.results.length === 0) {
            els.painel.innerHTML = '<div class="pub-acervo-estado-vazio">Nenhum documento neste capítulo.</div>';
            return;
        }

        const documentos = ordenarSeNecessario(resposta.results, (d) => d.titulo);
        els.painel.innerHTML = "";
        const container = document.createElement("div");
        container.className = estado.viewMode === "icones" ? "pub-acervo-grid" : "pub-acervo-lista";
        documentos.forEach((doc) => {
            const meta = [`${doc.paginas ?? "—"} pág.`, doc.ata_codigo ? `ATA ${doc.ata_codigo}` : null]
                .filter(Boolean)
                .join(" · ");
            const card = criarCard(
                { rotulo: doc.titulo, meta, onClick: () => abrirDocumento(doc.doc_id) },
                ICONE_DOCUMENTO
            );
            if (!doc.has_text) {
                const alvo = card.querySelector(
                    estado.viewMode === "icones" ? ".pub-acervo-item-icone-titulo" : ".pub-acervo-item-lista-titulo"
                );
                if (alvo) {
                    const aviso = document.createElement("span");
                    aviso.className = "pub-acervo-aviso-sem-texto";
                    aviso.title = "Este PDF não tem camada de texto — não é alcançável pela busca de conteúdo.";
                    aviso.textContent = " ⚠";
                    alvo.appendChild(aviso);
                }
            }
            container.appendChild(card);
        });
        els.painel.appendChild(container);

        const paginacao = document.createElement("div");
        paginacao.className = "pub-acervo-paginacao";
        const de = offset + 1;
        const ate = Math.min(offset + LIMITE_DOCUMENTOS, resposta.total);
        const btnAnt = document.createElement("button");
        btnAnt.type = "button";
        btnAnt.className = "btn btn-outline";
        btnAnt.textContent = "← Anterior";
        btnAnt.disabled = offset <= 0;
        btnAnt.addEventListener("click", () =>
            irPara({ manual: codigoManual, origem, capitulo, offset: Math.max(0, offset - LIMITE_DOCUMENTOS) })
        );
        const spanInfo = document.createElement("span");
        spanInfo.textContent = `${de}–${ate} de ${resposta.total}`;
        const btnProx = document.createElement("button");
        btnProx.type = "button";
        btnProx.className = "btn btn-outline";
        btnProx.textContent = "Próxima →";
        btnProx.disabled = offset + LIMITE_DOCUMENTOS >= resposta.total;
        btnProx.addEventListener("click", () =>
            irPara({ manual: codigoManual, origem, capitulo, offset: offset + LIMITE_DOCUMENTOS })
        );
        paginacao.append(btnAnt, spanInfo, btnProx);
        els.painel.appendChild(paginacao);
    }

    // --------------------------------------------------------------------
    // Viewer embutido — o PDF abre no painel direito, sem trocar de página
    // --------------------------------------------------------------------

    let viewer = null;
    let viewerPromessa = null;

    /**
     * Monta o viewer na primeira vez que um documento é aberto. `import()`
     * dinâmico porque `publicacoes_viewer.js` puxa o build do PDF.js junto —
     * quem só navega pela árvore nunca paga esse download.
     */
    function garantirViewer() {
        if (viewer) return Promise.resolve(viewer);
        if (!viewerPromessa) {
            viewerPromessa = import("/static/js/publicacoes_viewer.js")
                .catch((e) => {
                    viewerPromessa = null; // deixa uma próxima tentativa possível
                    throw e;
                })
                .then((mod) => {
                    viewer = mod.criarViewer({
                        raiz: els.viewerShell,
                        workerSrc: els.viewerContexto.dataset.workerSrc,
                        // A URL desta página é do explorador (`?manual=&capitulo=&doc=`);
                        // o viewer não escreve `#page=` nela.
                        sincronizarHash: false,
                        aoVoltar: () => irPara({ ...estado.atual, doc: null, pagina: 1 }),
                        aoTrocarDocumento: (id) => irPara({ ...estado.atual, doc: id, pagina: 1 }),
                    });
                    return viewer;
                });
        }
        return viewerPromessa;
    }

    function abrirDocumento(docId, pagina = 1) {
        irPara({ ...estado.atual, doc: docId, pagina });
    }

    async function renderPainel() {
        const { categoria, manual, origem, capitulo, doc, offset } = estado.atual;

        if (doc) {
            els.painel.hidden = true;
            els.viewer.hidden = false;
            try {
                const v = await garantirViewer();
                // Só recarrega quando o documento muda de fato: `renderPainel`
                // roda de novo a cada troca de filtro/ordenação, e reabrir o
                // mesmo PDF duplicaria a linha de `service.registrar_acesso`.
                if (v.docIdAtual() !== doc) v.abrir(doc, { pagina: estado.atual.pagina || 1 });
            } catch (e) {
                // PDF.js não carregou — a página dedicada faz o mesmo trabalho.
                window.location.href = `/publicacoes/viewer/${doc}`;
            }
            return;
        }
        els.viewer.hidden = true;
        els.painel.hidden = false;

        if (!categoria) {
            renderCards(
                estado.categoriaOrdem.map((c) => ({
                    rotulo: c,
                    meta: `${(estado.manuaisPorCategoria.get(c) || []).length} manual(is)`,
                    onClick: () => irPara({ categoria: c, manual: null, origem: null, capitulo: null, offset: 0 }),
                })),
                ICONE_PASTA
            );
            return;
        }

        if (!manual) {
            const manuais = ordenarSeNecessario(estado.manuaisPorCategoria.get(categoria) || [], (m) => m.descricao);
            renderCards(
                manuais.map((m) => ({
                    rotulo:
                        estado.filtroOrigem === "TODOS"
                            ? `${m.descricao} · ${rotuloOrigem(m.origem)}`
                            : m.descricao,
                    meta: `${m.codigo} · ${m.documentos} doc(s)`,
                    onClick: () => irPara({ manual: m.codigo, origem: m.origem, capitulo: null, offset: 0 }),
                })),
                ICONE_PASTA
            );
            return;
        }

        if (capitulo === null) {
            const capitulos = estado.capitulosPorManual.get(chaveManual(manual, origem));
            if (!Array.isArray(capitulos)) {
                els.painel.innerHTML = '<div class="pub-acervo-estado-vazio">Carregando capítulos…</div>';
                return;
            }
            const ordenados = ordenarSeNecessario(capitulos, (c) => c.capitulo || "");
            renderCards(
                ordenados.map((c) => ({
                    rotulo: c.capitulo || "(raiz do manual)",
                    meta: c.ata_codigo ? `ATA ${c.ata_codigo} · ${c.documentos} doc(s)` : `${c.documentos} doc(s)`,
                    onClick: () => irPara({ manual, origem, capitulo: c.capitulo, offset: 0 }),
                })),
                ICONE_PASTA
            );
            return;
        }

        await renderDocumentos(manual, origem, capitulo, offset);
    }

    // --------------------------------------------------------------------
    // Barra de ferramentas (voltar/avançar/raiz, lista/ícones, ordenar)
    // --------------------------------------------------------------------

    els.btnVoltar.addEventListener("click", () => history.back());
    els.btnAvancar.addEventListener("click", () => history.forward());
    els.btnRaiz.addEventListener("click", () =>
        irPara({ categoria: null, manual: null, origem: null, capitulo: null, offset: 0 })
    );

    function aplicarFiltroOrigem(valor) {
        estado.filtroOrigem = valor;
        localStorage.setItem(CHAVE_FILTRO_ORIGEM, valor);
        els.filtroOrigemBtns.forEach((b) => b.classList.toggle("is-ativo", b.dataset.origem === valor));
        reconstruirAgrupamento();
        renderArvore();
        renderBreadcrumb();
        renderPainel();
    }
    els.filtroOrigemBtns.forEach((b) => {
        b.classList.toggle("is-ativo", b.dataset.origem === estado.filtroOrigem);
        b.addEventListener("click", () => aplicarFiltroOrigem(b.dataset.origem));
    });

    function aplicarViewMode(modo) {
        estado.viewMode = modo;
        localStorage.setItem(CHAVE_VIEW, modo);
        els.btnLista.classList.toggle("is-ativo", modo === "lista");
        els.btnIcones.classList.toggle("is-ativo", modo === "icones");
        renderPainel();
    }
    els.btnLista.addEventListener("click", () => aplicarViewMode("lista"));
    els.btnIcones.addEventListener("click", () => aplicarViewMode("icones"));
    aplicarViewMode(estado.viewMode);

    els.btnOrdenar.classList.toggle("is-ativo", estado.ordemNome);
    els.btnOrdenar.addEventListener("click", () => {
        estado.ordemNome = !estado.ordemNome;
        localStorage.setItem(CHAVE_ORDEM, estado.ordemNome ? "1" : "0");
        els.btnOrdenar.classList.toggle("is-ativo", estado.ordemNome);
        renderPainel();
    });

    // --------------------------------------------------------------------
    // Busca (dois modos: por nome/caminho e por conteúdo)
    // --------------------------------------------------------------------

    function snippetSeguro(bruto) {
        return escapeHtml(bruto).replaceAll("\x02", "<mark>").replaceAll("\x03", "</mark>");
    }

    function renderResultadosBusca(itens) {
        if (itens.length === 0) {
            els.buscaResultados.innerHTML =
                '<div class="pub-acervo-estado-vazio" style="padding:0.75rem;">Nenhum resultado.</div>';
            return;
        }
        els.buscaResultados.innerHTML = "";
        itens.forEach((item) => {
            const titulo = item.titulo !== undefined ? item.titulo : item.title;
            const caminho =
                item.caminho !== undefined
                    ? item.caminho
                    : `${item.manual.description} (${item.manual.path}) › ${item.chapter || "—"}`;
            const el = document.createElement("div");
            el.className = "pub-acervo-busca-resultado";
            el.innerHTML =
                `<div class="pub-acervo-busca-resultado-titulo">${escapeHtml(titulo)}</div>` +
                `<div class="pub-acervo-busca-resultado-caminho">${escapeHtml(caminho)}</div>` +
                (item.snippet
                    ? `<div class="pub-acervo-busca-resultado-trecho">${snippetSeguro(item.snippet)}</div>`
                    : "");
            el.addEventListener("click", () => {
                els.buscaResultados.classList.remove("is-aberto");
                abrirDocumento(item.doc_id, item.page || 1);
            });
            els.buscaResultados.appendChild(el);
        });
    }

    async function executarBusca(termo) {
        const minhaSeq = ++estado.buscaSeq;
        els.buscaResultados.classList.add("is-aberto");
        els.buscaResultados.innerHTML = '<div class="pub-acervo-estado-vazio" style="padding:0.75rem;">Buscando…</div>';
        const params = new URLSearchParams({ q: termo, limit: "20" });
        const url =
            estado.modoBusca === "conteudo"
                ? `/publicacoes/api/busca?${params.toString()}`
                : `/publicacoes/api/catalogo/busca?${params.toString()}`;
        try {
            const resposta = await apiFetch(url);
            if (minhaSeq !== estado.buscaSeq) return; // resposta atrasada — uma busca mais nova já está em tela
            renderResultadosBusca(resposta.results);
        } catch (e) {
            if (minhaSeq !== estado.buscaSeq) return;
            els.buscaResultados.innerHTML =
                '<div class="pub-acervo-estado-vazio" style="padding:0.75rem;">Busca indisponível.</div>';
        }
    }

    let debounceBusca = null;
    function aoDigitarBusca() {
        clearTimeout(debounceBusca);
        const termo = els.buscaInput.value.trim();
        if (termo.length < 3) {
            els.buscaResultados.classList.remove("is-aberto");
            els.buscaResultados.innerHTML = "";
            return;
        }
        // Debounce >= 400ms: `/api/busca` tem limite de 30/min — busca a cada
        // tecla sem isto estoura o limite em poucos segundos.
        debounceBusca = setTimeout(() => executarBusca(termo), 400);
    }
    els.buscaInput.addEventListener("input", aoDigitarBusca);
    els.buscaInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            clearTimeout(debounceBusca);
            const termo = els.buscaInput.value.trim();
            if (termo.length >= 1) executarBusca(termo);
        }
    });
    function ativarModoBusca(modo) {
        els.buscaModos.forEach((b) => b.classList.toggle("is-ativo", b.dataset.modo === modo));
        estado.modoBusca = modo;
    }
    els.buscaModos.forEach((btn) => {
        btn.addEventListener("click", () => {
            ativarModoBusca(btn.dataset.modo);
            const termo = els.buscaInput.value.trim();
            if (termo.length >= 3) executarBusca(termo);
        });
    });
    document.addEventListener("click", (e) => {
        if (!e.target.closest(".pub-acervo-busca")) {
            els.buscaResultados.classList.remove("is-aberto");
        }
    });

    // --------------------------------------------------------------------
    // Mensagem do CAS/EICAS (FIM)
    // --------------------------------------------------------------------

    async function resolverFim() {
        const mensagem = els.fimInput.value.trim();
        if (!mensagem) {
            showToast("Digite a mensagem exibida no CAS/EICAS.", "info");
            return;
        }
        els.fimResultados.innerHTML = "";
        try {
            const resposta = await apiFetch(
                `/publicacoes/api/fim?${new URLSearchParams({ mensagem }).toString()}`
            );
            if (resposta.results.length === 0) {
                els.fimResultados.innerHTML =
                    '<div style="color:var(--text-secondary); font-size:0.82rem;">Nenhuma mensagem encontrada com esse prefixo.</div>';
                return;
            }
            resposta.results.forEach((item) => {
                const linha = document.createElement("div");
                linha.className = "pub-acervo-fim-resultado";
                const alvo = item.viewer_url
                    ? `<a href="${item.viewer_url}">${escapeHtml(item.title || item.procedimento)}</a>`
                    : `${escapeHtml(item.procedimento)} <em style="color:var(--text-secondary);">(sem PDF no acervo)</em>`;
                linha.innerHTML = `<strong>${escapeHtml(item.mensagem)}</strong> → ${alvo}`;
                els.fimResultados.appendChild(linha);
            });
        } catch (e) {
            // apiFetch já notificou.
        }
    }
    els.fimBtn.addEventListener("click", resolverFim);
    els.fimInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") resolverFim();
    });

    // --------------------------------------------------------------------
    // Inicialização
    // --------------------------------------------------------------------

    (async function inicializar() {
        await carregarManuais();
        await irPara(alvoDaUrl(), { historico: false });
        els.btnVoltar.disabled = false;
        els.btnAvancar.disabled = false;

        // `?q=` — contrato com quem já linkava para a busca desta página
        // (checklist de inspeção, inspecao_detalhe.js): abre com o termo
        // pré-preenchido e a busca "no conteúdo" já disparada.
        const qInicial = new URLSearchParams(window.location.search).get("q");
        if (qInicial) {
            els.buscaInput.value = qInicial;
            ativarModoBusca("conteudo");
            executarBusca(qInicial);
        }
    })();
})();
