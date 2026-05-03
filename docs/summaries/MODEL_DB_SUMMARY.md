# MODEL_DB_SUMMARY
- Auth: `usuarios`, `token_blacklist`, `token_refresh`.
- Aeronaves: `aeronaves` (UUID PK).
- Equipamentos: `modelos_equipamento`, `slots_inventario`, `itens_equipamento`, `instalacoes`.
- Vencimentos: `tipos_controle`, `equipamento_controles`, `controle_vencimentos`.
- Panes: `panes`, `anexos`, `pane_responsaveis`.
- Inspeções: `tipos_inspecao`, `tarefas_catalogo`, `tarefas_template`, `inspecoes`, `inspecao_tarefas`.
- Efetivo: `indisponibilidades`.
- Auditoria: `created_at`, `updated_at`, `usuario_id`/`trigrama` em tabelas de execução.
