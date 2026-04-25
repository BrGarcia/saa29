# roadmap_summary

state_now:
- track: v1_x_stabilization
- docs_sync: done
- current_system: auth_aeronaves_panes_inventory_vencimentos_configuracoes_active

completed_backlog:
- settings_page_vencimentos_ui: DONE (tabela matricial /vencimentos, endpoint /equipamentos/vencimentos/matriz)
- settings_page_equipamentos_ui: DONE (catalogo PN via modal em configuracoes, criar_modelo com uppercase e unicidade)
- settings_tipos_controle_crud: DONE (cadastrar e editar tipos de controle via UI)
- settings_regras_pn_controle: DONE (vincular PN a tipo de controle com periodicidade)
- vencimentos_registrar_execucao_backend: DONE (endpoint PATCH /vencimentos/{id}/executar no service)

immediate_backlog:
- vencimentos_prorrogacao: implementar modelo, CRUD e UI para Prorrogação de Vencimento (Engenharia)
- settings_slots_ui: gerenciar slots via UI de configuracoes (hoje via seed)
- logout_backend_client_alignment
- cookie_only_auth_hardening
- dead_code_and_unused_schema_cleanup

next_versions:
- v1_2: data_export_and_search_improvements
- v2_0: mobility_pwa_qr_offline_hangar
- v3_0: analytics_mttr_mtbf_alerts_stock
- v4_0: formal_docs_signature_tbo_inspections (modulo_inspecoes planejado em docs/implementacao_inspecao.md)
- v5_0: predictive_ai_supply_chain_readiness

note:
- detailed_source: docs/ROADMAP.md
- if_task_relates_to_backlog_check_this_file_first
