# Especificação Técnica de Migração: SAA29 (Python → Node.js)

> **Documento de Handoff Técnico para Equipe de Desenvolvimento**  
> **Sistema:** SAA29 – Sistema de Gestão de Panes e Manutenção Aeronáutica (A-29 Super Tucano)  
> **Data de Emissão:** 13/08/2026  
> **Versão:** 1.0
> **Objetivo:** Orientar o planejamento, estimativa e reescrita do sistema mantendo total paridade de dados e funcionalidades.

---

## 1. Visão Geral do Sistema

O **SAA29** é um sistema monólito web de gestão técnica e manutenção aeronáutica para a frota A-29 Super Tucano. Ele combina **páginas HTML com renderização no servidor (SSR)** e **endpoints de API REST** para operações assíncronas no frontend (JavaScript vanilla).

### Principais Casos de Uso:
1. **Gestão de Panes:** Registro de falhas, vinculação com sistemas ATA, anexos fotográficos e responsabilização de mantenedores.
2. **Controle de Equipamentos e Inventário:** Registro de componentes por lote/série, slots de instalação em aeronaves e ciclo de vida.
3. **Controle de Vencimentos:** Alertas e histórico de vencimentos de equipamentos por horas de voo, calendário ou ciclos.
4. **Gestão de Inspeções:** Aplicação de templates de tarefas e acompanhamento de inspeções periódicas.
5. **Módulo de Publicações e Manuais:** Consulta e busca textual indexada em documentos/manuais PDF de manutenção.
6. **Controle de Efetivo e Encarregado:** Notificações de ciência, controle de indisponibilidades do efetivo e pedidos de suprimentos.

---

## 2. Métricas e Dimensões do Projeto Atual

* **Linguagem Original:** Python 3.12 (FastAPI)
* **Arquitetura de Banco de Dados:** Relacional (SQLite em desenvolvimento/produção leve ou PostgreSQL).
* **Total de Tabelas de Negócio:** **38 tabelas** (+ 1 de controle de migração `alembic_version`).
* **Total de Rotas HTTP Mapeadas:** **176 rotas** (rotas de renderização de páginas HTML + rotas de API REST `/api/...`).
* **Volume Médio de Dados Atual (Exemplo de Carga Local):**
  * ~1,3 MB de banco SQLite pré-populado.
  * **22** Aeronaves cadastradas.
  * **26** Modelos de Equipamento.
  * **33** Slots de Inventário.
  * **726** Itens de Equipamento registrados.
  * **726** Instalações ativas.
  * **39** Templates de Tarefas de Inspeção.
  * **16** Tipos de Inspeção.
  * **66** Controles de Vencimento ativos.
* **Perfis de Usuário:** Administrador, Encarregado, Mantenedor/Técnico e Leitor.

---

## 3. Stack Tecnológica Atual vs. Stack Proposta (Node.js)

| Camada / Recurso | Stack Atual (Python) | Stack Alvo Proposta (Node.js) | Observações de Migração |
| :--- | :--- | :--- | :--- |
| **Linguagem** | Python 3.12 | Node.js (v20+ LTS / TypeScript) | Mantém compatibilidade com Node puro. |
| **Framework Web** | FastAPI 0.115 (Uvicorn / Gunicorn) | **Express.js** ou **Fastify** | Express garante 100% de suporte em hospedagem compartilhada (cPanel/Hostinger). |
| **Template Engine** | Jinja2 | **Nunjucks** | **Reaproveito de HTML:** Nunjucks possui sintaxe 99% idêntica ao Jinja2. |
| **ORM / Banco** | SQLAlchemy 2.0 + Alembic | **Prisma ORM** ou **Drizzle ORM** | O Prisma pode fazer `db pull` no banco existente sem alterar colunas ou dados. |
| **Banco de Dados** | SQLite (`saa29_local.db`) ou Postgres | SQLite ou PostgreSQL | **Zero alteração no banco físico.** |
| **Autenticação** | `python-jose` (JWT) + `passlib` (Bcrypt) | `jsonwebtoken` + **`bcryptjs`** | O `bcryptjs` valida as hashes `$2b$` já salvas no banco atual sem recriar senhas. |
| **Upload de Mídia** | `python-magic` (`libmagic1`) | `multer` + **`file-type`** | `file-type` é JS puro (elimina dependência de C/`libmagic` no SO). |
| **Leitura de PDF** | `pypdfium2` | `pdf-parse` ou `pdfjs-dist` | Usado no indexador de busca offline de manuais PDF. |

---

## 4. Estrutura dos Módulos do Sistema (Visão de Código)

O código atual está organizado em 11 módulos bem definidos em `app/modules/`:

```
app/
├── modules/
│   ├── auth/           # Autenticação, Usuários, Tokens Refresh/Blacklist
│   ├── aeronaves/      # Cadastro e status operacional das aeronaves (22 registros)
│   ├── equipamentos/   # Modelos, Slots, Itens e Instalações (726 registros)
│   ├── panes/          # Sistemas ATA, Registro de Panes, Anexos e Responsáveis
│   ├── vencimentos/    # Tipos de controle, Alertas, Prorrogações e Histórico
│   ├── inspecoes/      # Tipos, Tarefas Catálogo, Templates e Inspeções Ativas
│   ├── publicacoes/    # Manuais PDF, Edições, Documentos, FIM Map e Anexos
│   ├── pedidos/        # Solicitação de peças e suprimentos de manutenção
│   ├── efetivo/        # Militares e controle de indisponibilidades
│   ├── encarregado/    # Registro de ciências e assinaturas do encarregado
│   └── calendario/     # Tipos de evento e agenda de manutenção
├── pages/              # Controllers que renderizam as telas HTML via Jinja2
└── web/                # Middlewares de sessão, CSRF e tratamento de erros
```

---

## 5. Dicionário de Tabelas do Banco de Dados (38 Tabelas)

Para a criação dos schemas no Node.js (via Prisma/Drizzle), o banco relacional atual contém os seguintes grupos de tabelas:

### 5.1. Núcleo & Autenticação
1. `usuarios` (id, nome, email, senha_hash, perfil, ativo, etc.)
2. `token_blacklist` (tokens revogados)
3. `token_refresh` (tokens de renovação de sessão)

### 5.2. Frota & Equipamentos
4. `aeronaves` (id, matricula, modelo, status, horas_voo, etc.)
5. `modelos_equipamento` (id, part_number, descricao, fabricante, etc.)
6. `slots_inventario` (id, modelo_aeronave, posicao, descricao)
7. `itens_equipamento` (id, modelo_id, serial_number, status, etc.)
8. `instalacoes` (id, item_id, aeronave_id, slot_id, data_instalacao, etc.)

### 5.3. Panes & Ocorrências
9. `sistemas_ata` (capítulo ATA, código, descrição)
10. `panes` (id, aeronave_id, ata_id, descricao_pane, acao_corretiva, status, data_abertura, etc.)
11. `anexos` (id, pane_id, caminho_arquivo, tipo_mime, data_upload)
12. `pane_responsaveis` (id, pane_id, usuario_id, papel)

### 5.4. Controle de Vencimentos
13. `tipos_controle` (horas_voo, calendario, ciclos)
14. `equipamento_controles` (vinculação de controle com modelo)
15. `controle_vencimentos` (limite, horas_atuais, proximo_vencimento)
16. `prorrogacoes_vencimento` (historico de prorrogacoes autorizadas)
17. `execucoes_vencimento_historico` (registro de cumprimento)

### 5.5. Inspeções Periódicas
18. `tipos_inspecao` (id, nome, periodicidade, horas_intervalo)
19. `tarefas_catalogo` (descricao da tarefa, sistema ATA)
20. `tarefas_template` (vinculo de tarefa com tipo de inspecao)
21. `inspecoes` (id, aeronave_id, tipo_inspecao_id, status, data_inicio, data_fim)
22. `inspecao_tarefas` (id, inspecao_id, tarefa_id, status_cumprimento, executante_id)
23. `inspecao_evento_tipos` (tipos de eventos do ciclo de vida da inspeção)

### 5.6. Publicações & Documentação Técnica
24. `manuais` (id, titulo, codigo, modelo_aeronave)
25. `manuais_edicoes` (revisão, data_edicao, caminho_pdf)
26. `manuais_documentos` (paginas e trechos extraidos para busca)
27. `manuais_fim_map` (mapeamento de solução de panes FIM)
28. `publicacoes_acessos` (logs de auditoria de leitura)
29. `publicacoes_avulsas` (boletins técnicos, diretrizes)
30. `publicacao_avulsa_anexos` (arquivos anexos)
31. `publicacao_avulsa_aeronaves` (aeronaves afetadas pelo boletim)
32. `publicacoes_favoritos` (marcações do usuário)
33. `publicacoes_upload_jobs` (jobs assíncronos de indexação PDF)

### 5.7. Módulos Complementares
34. `pedidos` (pedidos de peças e material de aviação)
35. `indisponibilidades` (afastamento / licença de mantenedores)
36. `encarregado_ciencias` (registro de visto/assintatura de ciência)
37. `event_types` (categorias do calendário)
38. `calendar_events` (eventos agendados)

---

## 6. Diretrizes e Regras de Negócio Inegociáveis na Migração

1. **Preservação de Hashes de Senha:**
   As senhas no banco atual utilizam o algoritmo `bcrypt` (`$2b$12$...`). O módulo de autenticação Node.js DEVE utilizar o pacote `bcrypt` ou `bcryptjs` nativo para garantir que usuários existentes continuem logando sem resetar a senha.

2. **Reaproveitamento de Templates Frontend:**
   O frontend atual utiliza arquivos `.html` com sintaxe Jinja2 em `app/templates/`. Ao utilizar o **Nunjucks** no Express/Fastify, cerca de 95% dos HTMLs e arquivos JavaScript estáticos de `static/js/` poderão ser reutilizados sem alteração.

3. **Independência do Banco de Dados (Zero Data Loss):**
   A equipe de desenvolvimento Node.js deve executar o comando de introspecção do ORM escolhido (ex: `npx prisma db pull`) apontando para uma cópia do arquivo `saa29_local.db`. **Nenhuma tabela ou coluna deve ser renomeada** para evitar quebra de migração.

4. **Tratamento de Arquivos de Upload:**
   Os arquivos de anexos e fotos de panes ficam gravados no diretório de disco `uploads/`. O serviço Node.js deve servir esta pasta como estática ou integrar com S3/Cloudflare R2 mantendo a mesma estrutura de pastas.

---

## 7. Roteiro Sugerido de Migração por Fases

* **Fase 1: Setup & Introspecção do Banco de Dados**
  * Inicializar projeto Node.js (TypeScript recomendado).
  * Executar `prisma db pull` (ou Drizzle Introspect) para gerar os tipos e modelos a partir do `saa29_local.db`.
  * Configurar Express.js com Nunjucks para servir os arquivos estáticos e HTMLs existentes.

* **Fase 2: Autenticação & Sessões**
  * Migrar endpoints `/auth/login`, `/auth/logout`, `/auth/refresh`.
  * Configurar middlewares de verificação de token JWT e proteção de rotas por perfil.

* **Fase 3: Módulos Core de Manutenção**
  * Migrar CRUD e regras de negócio de **Aeronaves**, **Equipamentos**, **Panes** e **Vencimentos**.
  * Validar uploads de anexos com `multer` e `file-type`.

* **Fase 4: Inspeções, Publicações e Efetivo**
  * Migrar o fluxo de abertura e cumprimento de **Inspeções**.
  * Migrar a leitura e busca simples do módulo de **Publicações**.

* **Fase 5: Testes de Integração e Cutover**
  * Testar concorrência de acessos.
  * Validar o deploy em ambiente sem Docker (Hospedagem Node.js padrão com `app.js` / Phusion Passenger).
