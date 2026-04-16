# CTX

@meta:purpose=ctx,opt=tokens,mode=machine
@rules:no_narrative,no_dup,short_keys,state_first,delta_only
@io:read=preload,write=reusable_only,rm=stale
@hist:on,scope=decisions,fmt=yyyymmdd
@fmt:kv,list[],no_text

sys:{name:SAA29,type:web_mng,stack:[fastapi,sqlalchemy,pydantic,alembic,jinja2,docker]}

goals:[gestao_panes,obs_internas_manutencao,remocao_anexos_gestor,deploy_railway_docker]

arch:{be:fastapi,fe:vanilla_js,db:sqlite,pat:service_layer}

data:{entities:[Pane,Anexo,PaneResponsavel,Usuario,Aeronave,Equipamento,ItemEquipamento,Instalacao,ControleVencimento]}

rules:[RN-03_edit_aberta_only,RN-04_auto_conclusao,RN-05_desc_default,soft_delete,delete_anexo_gestor_only]

state:{phase:estavel_local,focus:deploy_railway}

decisions:[
  {id:FIELD_COMENTARIOS,ts:20260414,d:adicionado_campo_comentarios_independente_status},
  {id:ADMIN_SEED_ENV,ts:20260414,d:admin_credentials_moved_to_env_and_username_updated},
  {id:DELETE_ANEXO,ts:20260414,d:implementado_remocao_anexo_restrita_gestores},
  {id:DOCKER_START_SCRIPT,ts:20260414,d:criado_start_sh_para_migracoes_e_seed_no_boot},
  {id:FIX_MODEL_IMPORT_ORDER,ts:20260416,d:equipamentos_models_deve_preceder_aeronaves_models_no_import_do_main},
  {id:FIX_SQLALCHEMY_CAST,ts:20260416,d:func_Integer_substituido_por_Integer_importado_no_cast_do_year_func}
]

open:[]

todo:[configurar_volumes_railway,verificar_testes_regressao,interface_equipamentos_ui]

hist:[
  {id:ADD_COMENTARIOS,ts:20260414,d:implementado_box_comentarios_detalhe_pane_backend_frontend},
  {id:UPDATE_ADMIN_LOGIN,ts:20260414,d:atualizado_login_senha_admin_via_seed_e_env},
  {id:FEAT_DELETE_ANEXO,ts:20260414,d:adicionado_icone_excluir_anexo_e_endpoint_delete},
  {id:DEPLOY_PREP,ts:20260414,d:preparado_dockerfile_e_script_de_boot_para_railway},
  {id:BUG_500_MAPPER,ts:20260416,d:corrigido_InvalidRequestError_Instalacao_not_found_por_ordem_de_import_errada_em_main_py},
  {id:BUG_500_CAST,ts:20260416,d:corrigido_AttributeError_static_cache_key_por_uso_incorreto_de_func_Integer_em_panes_service}
]
