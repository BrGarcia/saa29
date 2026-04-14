
EM DESENVOLVIMENTO 
FAVOR DESCONSIDERAr
NAO LEIA 
PULE PARA PRóXIMO PASSO

# CTX
Identificador do arquivo
Indica que é um context store (memória compartilhada)

@meta:purpose=ctx,opt=tokens,mode=machine
purpose=ctx → arquivo usado como contexto global
opt=tokens → otimizado para baixo consumo de tokens
mode=machine → formato voltado para IA (não humano)

rules:no_narrative,no_dup,short_keys,state_first,delta_only
Regras de escrita:
no_narrative → sem texto explicativo
no_dup → não repetir informação
short_keys → usar nomes curtos
state_first → priorizar estado atual
delta_only → só registrar mudanças relevantes

@io:read=preload,write=reusable_only,rm=stale
Regras de leitura/escrita:
read=preload → IA deve ler antes de qualquer ação
write=reusable_only → só salvar info reutilizável
rm=stale → remover dados obsoletos

@hist:on,scope=decisions,fmt=yyyymmdd
Controle de histórico:
on → histórico habilitado
scope=decisions → só decisões são registradas
fmt=yyyymmdd → formato de data compacto

@fmt:kv,list[],no_text
Formato dos dados:
kv → key:value
list[] → listas com colchetes
no_text → sem blocos de texto
🧩 SEÇÕES DE DADOS

sys:{name:,type:,stack:[]}
Sistema principal:
name → nome do projeto
type → tipo (web, API, etc.)
stack → tecnologias usadas
goals:[]

Lista de objetivos:
funcionalidades principais
propósito do sistema

arch:{be:,fe:,db:,pat:}
Arquitetura:
be → backend
fe → frontend
db → banco de dados
pat → padrão arquitetural
data:{entities:[]}

Modelo de dados:

lista de entidades principais
ex: user, pane, aircraft
rules:[]

Regras de negócio:

validações
comportamentos importantes
state:{phase:,focus:}

Estado atual do projeto:

phase → fase (ex: scaffold, impl, test)
focus → módulo atual

👉 essa é a seção mais importante para IA

decisions:[ {id:,ts:,d:} ]

Decisões ativas:

id → identificador único
ts → timestamp
d → decisão (forma compacta)
open:[]

Pontos em aberto:

dúvidas
decisões pendentes
todo:[]

Tarefas pendentes:

próximas ações
backlog simplificado
hist:[ {id:,ts:,d:} ]

Histórico mínimo:

mesmo formato de decisions
guarda mudanças relevantes

👉 usado apenas para rastreabilidade

🎯 RESUMO CONCEITUAL

Esse arquivo é dividido em 3 camadas:

🧠 1. CONFIG (linhas @)

Controla:

comportamento da IA
regras de escrita
formato
🧩 2. STATE (sys, arch, data…)

Representa:

o estado atual do sistema

⏱️ 3. HISTORY (decisions, hist)

Representa:

mudanças importantes ao longo do tempo

🔥 Insight importante

Esse arquivo funciona como:

uma “memória estruturada de baixo custo” para múltiplos agentes de IA