# ia_docs_index

meta:
- purpose: low_token_machine_context
- scope: summarized_mirror_of_official_docs
- source_of_truth: docs/README.md, docs/architecture/, docs/core/, docs/guides/, docs/backlog/, docs/summaries/, docs/SECURITY.md, docs/ROADMAP.md, docs/CHANGELOG.md, docs/methodology/merge_main.md
- rule: if_conflict_use_official_docs

read_order:
- 1: docs/ia/CTX.md
- 2: docs/ia/modules.ctx, flows.ctx, api.ctx, rules.ctx, db.ctx
- 3: docs/ia/resumo_seguranca.md
- 4: docs/ia/mapa_repositorio.md
- 5: docs/ia/glossario.md
- 6: docs/ia/prompts_base.md

update_policy:
- update_after: code_change, doc_change, api_change, security_change, roadmap_change
- keep: short, deterministic, machine_friendly
- avoid: narrative, duplicated_examples, stale_paths

operational_rules:
- preserve_active_database: mandatory
- preserve_existing_pane_records: mandatory
- before_db_schema_or_data_change: create_backup_of_original_db
- never_assume: active_db_can_be_reset_recreated_or_reseeded
- merge_to_main_workflow: follow docs/methodology/merge_main.md strictly

files:
- CTX.md: project_state_and_current_focus
- modules.ctx: architecture_structure
- flows.ctx: core_system_flows
- api.ctx: endpoint_contracts
- rules.ctx: business_and_access_rules
- db.ctx: data_model_summary
- resumo_seguranca.md: security_controls_state
- mapa_repositorio.md: path_map
- glossario.md: domain_terms
- prompts_base.md: reusable_llm_prompts
