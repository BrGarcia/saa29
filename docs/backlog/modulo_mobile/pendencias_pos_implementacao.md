# Pendências pós-implementação — Módulo Mobile

**Contexto:** o módulo mobile (`/m/`) foi implementado, finalizado (Etapa 7 fechada) e mesclado em `development` (commit `c4ad06b`, 2026-08-20). A especificação e o plano de implementação completos foram arquivados em `docs/backlog/resolvidos/modulo_mobile/`. Este documento existe só para não perder de vista o que ainda está genuinamente em aberto: 3 falhas de teste pré-existentes descobertas durante o fechamento, e as pendências de verificação manual que nenhuma rodada de testes automatizados conseguiu fechar.

---

## 1. As 3 falhas pré-existentes em `tests/unit/test_publicacoes_catalog.py`

Não são bugs no módulo mobile nem no código do projeto — são testes de regressão do módulo **Publicações** que comparam o índice de busca contra o acervo real de manuais em disco (`var/publicacoes/acervo/Manuais/`, ~1 GB, fora do Git). Apareceram durante o fechamento do mobile só porque a suíte completa (`pytest tests -q`) roda os dois módulos juntos.

| Teste | O que verifica |
|---|---|
| `test_regressao_acervo_real_numeros_do_documento` | 34 manuais indexados, 5.719 documentos no total, distribuição de `revision` bate com `{U:2256, R:3266, N:181, 0:8, 1:2, 2:6}` |
| `test_regressao_acervo_real_todo_filename_casa_com_pdf_fisico` | Todo filename citado no índice Lucene tem PDF físico correspondente no disco (100%) |
| `test_regressao_fim_json_e_cobertura_do_piloto` | 1.377 mensagens de CAS/EICAS → 253 procedimentos únicos, todos com PDF no acervo |

Os três têm `@sem_acervo` (`pytest.mark.skipif`), que deveria pulá-los quando `var/publicacoes/acervo/Manuais/` não existe — o caso esperado em CI e na maioria dos ambientes. Nesta máquina de desenvolvimento específica, porém, essa pasta **existe** (a cópia real do acervo está presente), então o skip não dispara e os três rodam de verdade — e falham com `assert 0 == 34`, `assert 0 == 5719` etc., não com um valor parcialmente errado.

### Causa raiz confirmada

A pasta local tem uma camada extra de subdiretórios por categoria que o layout canônico não tem:

```
var/publicacoes/acervo/Manuais/
├── 01_Operacoes/          ← vazia (0 manuais dentro)
└── 02_Manutencao/
    ├── AIPC_1742/
    │   └── index_2.0/
    ├── FIM_1741/
    │   └── index_2.0/
    └── ... (34 manuais ao todo, todos aqui dentro)
```

O layout que o código (e os testes) esperam é **flat** — um manual por subpasta direta de `Manuais/`, sem a camada de categoria:

```
var/publicacoes/acervo/Manuais/
├── AIPC_1742/
│   └── index_2.0/
├── FIM_1741/
│   └── index_2.0/
└── ... (34 manuais, direto na raiz)
```

Três fontes independentes confirmam que o layout flat é o contrato real, não um detalhe dos testes:

1. **Os próprios testes** — `ACERVO.iterdir()` itera diretamente os filhos de `Manuais/`, esperando que cada um já seja um manual (`manual_dir / "index_2.0"`).
2. **`scripts/publicacoes/indexar.py::descobrir_manuais`** — a função que faz a indexação real também itera `entrada.iterdir()` esperando um manual por subpasta direta; com a camada de categoria, ela trataria `02_Manutencao` inteiro como um único "manual" (código `02_Manutencao`), o que quebraria a indexação de produção do mesmo jeito que quebra os testes aqui.
3. **`config/categorias_manuais.toml`** (comentário de cabeçalho, linha ~18): *"CHAVE = nome do diretório em `PUBLICACOES_ACERVO_DIR/Manuais/`, exato."* — o arquivo que mapeia categoria (Operações/Manutenção) para manual já existe e é só metadado (TOML), justamente para não precisar de pasta física por categoria. A categoria virou pasta física nesta cópia local por engano — provavelmente de algum processo de export/organização manual, não do pipeline oficial (`indexar.py`).

**Os dados em si estão completos, só mal-posicionados:** contei exatamente 34 pastas de manual sob `02_Manutencao/` (bate com o `assert indices_ok == 34` esperado) e `01_Operacoes/` está vazia — não é um manual "faltando", é uma pasta de categoria sem conteúdo dentro.

### Sugestão de correção

**Recomendado — reorganizar a pasta local, não o código:**

```bash
# 1. Backup antes de mexer (é ~1GB, mas mover é rápido; copiar é mais seguro)
# 2. Mover os 34 manuais de dentro de 02_Manutencao/ para a raiz de Manuais/
mv var/publicacoes/acervo/Manuais/02_Manutencao/*/ var/publicacoes/acervo/Manuais/
# 3. Remover as pastas de categoria, agora vazias
rmdir var/publicacoes/acervo/Manuais/01_Operacoes
rmdir var/publicacoes/acervo/Manuais/02_Manutencao
# 4. Confirmar
pytest tests/unit/test_publicacoes_catalog.py -v
```

Por que esta é a correção certa e não um workaround: alinha a cópia local com o contrato que o próprio pipeline de produção (`indexar.py`) e o mapa de categorias (`categorias_manuais.toml`) já documentam. Mudar o teste ou o `catalog.py` para aceitar uma camada extra de categoria só esconderia o problema aqui e deixaria a indexação real (`scripts/publicacoes/indexar.py`) quebrada do mesmo jeito se alguém rodasse contra esta mesma cópia.

**Não recomendado:** ajustar os testes para caminhar um nível a mais (`rglob` em vez de `iterdir`) — resolveria os 3 testes locais, mas mascararia um problema real de organização de dados que também afetaria a indexação de produção contra esta cópia, e divergiria do contrato documentado em `categorias_manuais.toml`.

**Antes de mover:** confirmar que nenhum outro processo/script deste ambiente depende da camada `01_Operacoes/`/`02_Manutencao/` para algo (não encontrei nenhuma referência no código do projeto — só o TOML de categorias, que já não usa pasta física). Se for uma reorganização manual recente e intencional para outro fim, vale confirmar com quem a fez antes de desfazer.

---

## 2. Pendências de verificação manual do módulo mobile

Herdadas do fechamento da Etapa 7 (`docs/backlog/resolvidos/modulo_mobile/02_plano_implementacao.md`, §9 e §11) — cobertas por `pytest`/leitura de código, mas nunca exercidas visualmente porque este ambiente de desenvolvimento não tem nenhuma ferramenta de automação de navegador (sem Playwright, sem MCP de browser).

| Item | Status | O que falta |
|---|---|---|
| Checklist de inspeção, Vencimentos, Inventário (Etapas 4-6) | Implementado + testado via `pytest` | Nunca aberto num navegador de verdade |
| Publicações normalizada + viewer de PDF (Etapa 7) | Implementado + testado via `pytest` | CSS do viewer em 393px ajustado por leitura de código, não por captura visual; gestos de pinça/zoom no `<canvas>` nunca exercidos |
| PWA instalável (manifest, SW, ícones) | Implementado + testado via `pytest` (arquivos existem, SW serve no escopo certo) | Instalação de fato num Android/iOS físico nunca confirmada |
| Captura de foto pela câmera (relato de pane) | Implementado | Fluxo com foto real de câmera física nunca testado (só sem foto, via HTTP) |
| Sessão > 15 min sem cair para `/login` (renovação silenciosa de token) | Implementado | Janela de 15 min nunca exercida manualmente |

### Sugestão de correção

Duas rotas possíveis, não excludentes:

1. **Teste manual humano** — checklist rápido para alguém com acesso a um Android/iPhone físico ou emulador: abrir `/m/` com o app rodando (`python scripts/run_app.py`), percorrer as 4 abas do hub numa aeronave, testar "Adicionar à Tela de Início", tirar uma foto real no relato de pane, deixar a sessão parada 15+ min e interagir de novo. Nenhum destes itens exige conhecimento de código — é o caminho mais rápido para fechar de vez.
2. **Habilitar automação de navegador neste ambiente** — instalar Playwright (`pip install playwright && playwright install chromium`) permitiria repetir aqui o mesmo tipo de verificação que as Etapas 1-3 tiveram (conforme registrado no plano arquivado). É uma mudança de ambiente (~300MB de download do Chromium), não de código — vale decisão explícita antes de fazer, não é algo para assumir por conta própria.

Nenhum dos itens desta seção bloqueia o uso do sistema — são lacunas de *verificação*, não bugs conhecidos.
