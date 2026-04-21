# CTX

@meta:purpose=ctx,opt=tokens,mode=machine
@rules:no_narrative,no_dup,short_keys,state_first,delta_only
@io:read=preload,write=reusable_only,rm=stale
@hist:on,scope=decisions,fmt=yyyymmdd
@fmt:kv,list[],no_text

sys:{name:SAA29,type:web_mng,stack:[fastapi,sqlalchemy,pydantic,alembic,jinja2,docker,magic,slowapi]}

goals:[gestao_panes,obs_internas_manutencao,remocao_anexos_gestor,deploy_railway_docker,seguranca_hardened]

arch:{be:fastapi,fe:vanilla_js,db:sqlite,pat:service_layer,sec:[csrf_sync,csp_rigid,rate_limit,magic_bytes]}

data:{entities:[Pane,Anexo,PaneResponsavel,Usuario,Aeronave,Equipamento,ItemEquipamento,Instalacao,ControleVencimento,TokenRefresh,TokenBlacklist]}

rules:[RN-03_edit_aberta_only,RN-04_auto_conclusao,RN-05_desc_default,soft_delete,delete_anexo_gestor_only,sec-01_csrf_required,sec-02_refresh_rotation]

state:{phase:producao_local,focus:testes_seguranca_regressao}

decisions:[
  {id:CSRF_HANDSHAKE_FIX,ts:20260420,d:token_bruto_no_header_e_assinado_no_cookie_conforme_fastapi-csrf-protect},
  {id:CSRF_AJAX_SYNC,ts:20260420,d:sincronizacao_dinamica_csrf_via_header_X-CSRF-Token_em_todas_respostas_api},
  {id:CSP_GOOGLE_FONTS,ts:20260420,d:ajuste_csp_para_permitir_google_fonts_e_scripts_inline_legados},
  {id:SEC_HARDENING,ts:20260420,d:implementado_rate_limiting_e_account_lockout_pos_5_tentativas},
  {id:REFRESH_TOKEN_FIX,ts:20260420,d:conversao_explicita_usuario_id_para_uuid_no_endpoint_refresh},
  {id:TEST_STABILIZATION,ts:20260420,d:bypass_csrf_em_testes_via_header_X-Skip-CSRF_para_isolar_logica_de_negocio},
  {id:UI_FIX_LISTENERS,ts:20260420,d:restaurado_event_listeners_js_pos_limpeza_de_scripts_inline}
]

open:[]

todo:[exportacao_inventario_pdf,validacao_vencimentos_ui,gestao_de_estoque_bancada]

hist:[
  {id:FIX_CSRF_LOGOUT,ts:20260420,d:resolvido_logout_automatico_em_post_ajuste_por_descompasso_de_assinatura},
  {id:FEAT_SEC_Fase2,ts:20260420,d:implementado_protecao_csrf_global_com_excecao_login_logout},
  {id:FEAT_SEC_Fase3,ts:20260420,d:hardening_de_headers_seguranca_e_validacao_tipo_real_arquivo_upload},
  {id:FIX_INVENTARIO_UI,ts:20260420,d:corrigido_filtro_aeronave_e_sincronia_sn_na_interface},
  {id:TESTS_SECURITY,ts:20260420,d:adicionados_testes_de_csrf_e_refresh_token_alcancando_91_casos_passando}
]
