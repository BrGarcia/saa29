# CTX

@meta:purpose=ctx,opt=tokens,mode=machine
@rules:no_narrative,no_dup,short_keys,state_first,delta_only
@io:read=preload,write=reusable_only,rm=stale
@hist:on,scope=decisions,fmt=yyyymmdd
@hist:on,scope=decisions,fmt=yyyymmdd
@fmt:kv,list[],no_text

sys:{name:SAA29,type:web_mng,stack:[fastapi,sqlalchemy,pydantic,alembic,jinja2]}

goals:[gestao_panes,obs_internas_manutencao,remocao_anexos_gestor]

arch:{be:fastapi,fe:vanilla_js,db:sqlite,pat:service_layer}

data:{entities:[Pane,Anexo,PaneResponsavel,Usuario,Aeronave]}

rules:[RN-03_edit_aberta_only,RN-04_auto_conclusao,RN-05_desc_default,soft_delete,delete_anexo_gestor_only]

state:{phase:ajuste_fino,focus:remocao_anexos}

decisions:[
  {id:FIELD_COMENTARIOS,ts:20260414,d:adicionado_campo_comentarios_independente_status},
  {id:ADMIN_SEED_ENV,ts:20260414,d:admin_credentials_moved_to_env_and_username_updated},
  {id:DELETE_ANEXO,ts:20260414,d:implementado_remocao_anexo_restrita_gestores}
]

open:[]

todo:[verificar_testes_regressao]

hist:[
  {id:ADD_COMENTARIOS,ts:20260414,d:implementado_box_comentarios_detalhe_pane_backend_frontend},
  {id:UPDATE_ADMIN_LOGIN,ts:20260414,d:atualizado_login_senha_admin_via_seed_e_env},
  {id:FEAT_DELETE_ANEXO,ts:20260414,d:adicionado_icone_excluir_anexo_e_endpoint_delete}
]
