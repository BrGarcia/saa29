# prompt.md — Prompt de Inicialização do Projeto

> Copie o bloco abaixo e cole em uma IA de programação (ex.: Claude Code) aberta na
> raiz deste diretório. Ele instrui a IA a ler a documentação existente e iniciar a
> implementação pelo ponto correto (Fase 0), sem reinventar decisões já tomadas.

---

```
# Papel

Atue como desenvolvedor sênior Python encarregado de implementar o "Sistema Web de
Consulta de Manuais Técnicos — EMB-314 Super Tucano". Todo o planejamento já foi
feito e está documentado neste diretório. Seu trabalho é EXECUTAR o plano, não
redesenhá-lo.

# Antes de escrever qualquer código

Leia, nesta ordem, os documentos na raiz do projeto:

1. README.md        — visão geral e mapa da documentação
2. Projeto.MD       — arquitetura, stack e roadmap (o QUÊ e POR QUÊ)
3. Especificacao.MD — telas, contrato de API, regras de negócio RN-01..RN-10,
                      casos de borda E-01..E-12, critérios de aceite CA-01..CA-07
4. Runbook.MD       — deploy e operação (informa decisões de empacotamento)

RAG.MD é Fase 3 (futuro) — leia apenas para não fechar portas; não implemente nada dele.

# Regras de execução (invioláveis)

- Decisões de arquitetura e stack JÁ ESTÃO TOMADAS (Projeto.MD §3): Python 3.12,
  FastAPI + Uvicorn, SQLite FTS5, PyMuPDF, Jinja2 + htmx, PDF.js, Caddy, Docker
  Compose. Não proponha alternativas; se encontrar um impedimento técnico real,
  pare e explique antes de desviar.
- Sem Java em nenhuma etapa. Sem serviços externos (Postgres, Elasticsearch, Redis).
- Toda regra de negócio implementada deve citar seu código (ex.: "# RN-07") e todo
  caso de borda da Especificacao.MD §6 deve ter teste automatizado (pytest) usando
  amostras reais do acervo em tests/fixtures/.
- O esquema SQL de referência está em Projeto.MD §7 — siga-o.
- Encoding: leitura de metadados legados sempre via UTF-8 com fallback cp1252 (RN-07).
- A indexação nunca pode abortar por causa de um arquivo ruim (E-02) e nunca bloqueia
  a aplicação (RN-09).
- Alvos de recursos: processo < 200 MB RSS; busca p95 < 300 ms (Especificacao.MD §8).

# Contexto dos dados (já verificado — não precisa redescobrir)

- Acervo legado: pastas Program/Data (2,0 GB) e Program_Operational/Data (1,1 GB),
  ~12.100 PDFs, 53 manuais, 51 sobrepostos entre as duas pastas.
- Estrutura: data/<MANUAL>/<CAPÍTULO>/arquivo.PDF + sidecar .title (linha 2 = título,
  linha 3 = UNCHANGED/REVISED).
- Metadados: manual_details.xml (descrições PT), manual_type.xml (categorias catid),
  collections.ini (nomes amigáveis, em Latin-1), version/<MANUAL>.txt (Rev. e data).

# Por onde começar — Fase 0 (Projeto.MD §11)

Primeira entrega: scripts/merge_data.py, que unifica Program/Data e
Program_Operational/Data em data/, conforme RN-08:
- mesmo caminho relativo + hash igual → mantém um;
- hash diferente → mantém o de mtime mais recente, move o preterido para
  _merge_conflicts/ e registra em merge_report.txt;
- nada é descartado silenciosamente; o script tem modo --dry-run (padrão) e --apply;
- copiar também manual_details.xml, manual_type.xml, collections.ini e a pasta
  version/ para dentro de data/;
- ao final, imprimir resumo: manuais, PDFs, bytes, duplicatas resolvidas, conflitos.

Depois do merge validado, siga a ordem da Especificacao.MD §12:
catalog.py (parsers + testes) → indexer.py → search.py → rotas/templates → viewer →
Dockerfile/docker-compose/Caddyfile (referências no Runbook.MD §3).

# Pendências que NÃO bloqueiam o início

D-01..D-05 (Especificacao.MD §10) são decisões do dono do produto. Use os valores
provisórios documentados (ex.: mapeamento de categorias da RN-04 em arquivo de
configuração categories.toml, nunca hardcoded) e siga em frente.

# Formato de trabalho

- Crie o repositório git com a estrutura de Projeto.MD §4; primeiro commit = docs.
- Trabalhe em entregas pequenas e verificáveis; ao final de cada módulo, rode os
  testes e mostre o resultado real.
- Ao concluir cada item do roadmap, marque o checkbox correspondente em Projeto.MD §11.
- Em caso de conflito entre documentos, a precedência é:
  Especificacao.MD > Projeto.MD > Runbook.MD — e sinalize o conflito para correção.

Comece agora: leia os quatro documentos e, em seguida, implemente e execute
scripts/merge_data.py em modo --dry-run, apresentando o relatório para minha
aprovação antes de aplicar o merge.
```

---

## Notas de uso

- **Onde rodar:** com a IA aberta na raiz deste diretório (`Manuais A-29 19MAIO26/`),
  onde estão os `.MD` e as pastas legadas `Program/` e `Program_Operational/`.
- **O prompt termina em uma ação segura:** o merge roda primeiro em `--dry-run` e
  aguarda sua aprovação — nenhum arquivo é movido sem você revisar o relatório.
- **Se a sessão for interrompida:** basta colar o mesmo prompt novamente; os checkboxes
  em Projeto.MD §11 indicam à IA o que já foi concluído.
- **Quando chegar na Fase 3 (IA/RAG):** use um prompt novo apontando para RAG.MD —
  este prompt cobre apenas Fases 0–2.
