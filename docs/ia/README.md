# ia_docs_index

meta:
- purpose: low_token_machine_context
- scope: summarized_mirror_of_official_docs
- source_of_truth: docs/README.md, docs/architecture/, docs/api/, docs/development/, docs/requirements/, docs/SECURITY.md, docs/ROADMAP.md, docs/CHANGELOG.md
- rule: if_conflict_use_official_docs

read_order:
- 1: docs/ia/contex.md
- 2: docs/ia/resumo_arquitetura.md
- 3: docs/ia/resumo_desenvolvimento.md
- 4: docs/ia/resumo_seguranca.md
- 5: docs/ia/mapa_repositorio.md
- 6: docs/ia/roadmap_resumido.md
- 7: docs/ia/glossario.md
- 8: docs/ia/prompts_base.md

update_policy:
- update_after: code_change, doc_change, api_change, security_change, roadmap_change
- keep: short, deterministic, machine_friendly
- avoid: narrative, duplicated_examples, stale_paths

files:
- contex.md: project_state
- resumo_arquitetura.md: architecture_state
- resumo_desenvolvimento.md: dev_run_test_state
- resumo_seguranca.md: security_controls_state
- mapa_repositorio.md: path_map
- roadmap_resumido.md: backlog_now_next
- glossario.md: domain_terms
- prompts_base.md: reusable_llm_prompts
