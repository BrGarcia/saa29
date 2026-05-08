========================================================
CALENDÁRIO — REGRAS DE ACESSO E VISIBILIDADE
========================================================

ROLES DO SISTEMA
--------------------------------------------------------

1. MANTENEDOR
2. ENCARREGADO
3. INSPETOR
4. ADMINISTRADOR


========================================================
CONCEITOS
========================================================

EVENTO PÚBLICO
--------------------------------------------------------
Eventos visíveis integralmente para os usuários
autorizados.

Exemplos:
- Férias
- Serviço
- Escala


EVENTO PARTICULAR
--------------------------------------------------------
Eventos privados do usuário.

Exemplos:
- Dispensa
- Consulta Médica

Dependendo da role do observador, o motivo poderá
ser censurado.


========================================================
TRIGRAMA
========================================================

Todo evento exibido no calendário deve possuir
uma BADGE contendo o TRIGRAMA do usuário dono
do lançamento.

O trigrama já existe na tabela users.

Exemplo visual:

[ ABC ]
[ JSM ]
[ TRF ]

O trigrama deve aparecer:
- no card do evento
- no tooltip
- no modal de detalhes
- nas listagens


========================================================
ESTRUTURA DE DADOS
========================================================

Tabela: users
--------------------------------------------------------

id
name
trigram
role


Tabela: event_types
--------------------------------------------------------

id
name
visibility_type
color
icon
active


Tabela: calendar_events
--------------------------------------------------------

id
owner_user_id
created_by_user_id
event_type_id
start_date
end_date
notes
created_at


========================================================
DIFERENÇA IMPORTANTE
========================================================

owner_user_id
--------------------------------------------------------
Usuário ao qual a indisponibilidade pertence.

Exemplo:
- João está de férias


created_by_user_id
--------------------------------------------------------
Usuário que realizou o lançamento.

Exemplo:
- encarregado lançou as férias de João


========================================================
PERMISSÕES POR ROLE
========================================================

--------------------------------------------------------
ROLE: MANTENEDOR
--------------------------------------------------------

PODE:
- criar suas próprias indisponibilidades
- visualizar:
  - seus eventos públicos
  - seus eventos particulares
  - eventos públicos dos outros
  - eventos particulares dos outros (censurados)

NÃO PODE:
- criar eventos para outros usuários
- editar eventos de outros usuários
- excluir eventos de outros usuários

VISUALIZAÇÃO DE EVENTO PARTICULAR DE OUTRO USUÁRIO:
--------------------------------------------------------

Exibir:

Título:
"Particular"

Sem mostrar:
- Consulta Médica
- Dispensa
- motivo real

Exemplo:

[ JSM ]
🔒 Particular


========================================================

ROLE: ENCARREGADO
--------------------------------------------------------

PODE:
- visualizar todos os eventos integralmente
- criar eventos para qualquer usuário
- editar eventos
- visualizar detalhes completos

VISUALIZAÇÃO:
--------------------------------------------------------

Sem censura.

Exemplo:

[ ABC ]
🏥 Consulta Médica

ou

[ TRF ]
🌴 Férias


========================================================

ROLE: INSPETOR
--------------------------------------------------------

PODE:
- visualizar:
  - eventos públicos
  - eventos particulares censurados

NÃO PODE:
- criar eventos
- editar eventos
- excluir eventos

VISUALIZAÇÃO DE EVENTO PARTICULAR:
--------------------------------------------------------

Exibir apenas:

[ JSM ]
🔒 Particular

Sem motivo detalhado.


========================================================

ROLE: ADMINISTRADOR
--------------------------------------------------------

PODE:
- visualizar tudo
- criar eventos para qualquer usuário
- editar qualquer evento
- excluir qualquer evento
- acessar detalhes completos

VISUALIZAÇÃO:
--------------------------------------------------------

Sem censura.


========================================================
MATRIZ DE ACESSO
========================================================

Legenda:
✔ = permitido
✖ = não permitido
◐ = permitido com censura


AÇÃO                                    MANT  ENC  INSP  ADMIN
--------------------------------------------------------------
Ver público                             ✔     ✔    ✔     ✔
Ver privado próprio                     ✔     ✔    ◐     ✔
Ver privado de terceiros                ◐     ✔    ◐     ✔
Criar próprio                           ✔     ✔    ✔     ✔
Criar para terceiros                    ✖     ✔    ✖     ✔
Editar próprio                          ✔     ✔    ✔     ✔
Editar terceiros                        ✖     ✔    ✖     ✔
Excluir eventos                         ✖     ✖    ✖     ✔
Ver motivo real privado                 próprio✔   ✖     ✔


========================================================
REGRAS DE CENSURA
========================================================

Quando o usuário NÃO possui permissão para visualizar
o motivo real do evento particular:

O backend deve substituir:

--------------------------------------------------------
ANTES:
--------------------------------------------------------

{
  "title": "Consulta Médica",
  "visibility": "private"
}

--------------------------------------------------------
DEPOIS:
--------------------------------------------------------

{
  "title": "Particular",
  "visibility": "private"
}

O frontend nunca deve receber o motivo real.


========================================================
REGRA DE SEGURANÇA
========================================================

O frontend NÃO decide censura.

O backend deve:
- filtrar
- mascarar
- remover informações sensíveis

antes de enviar os dados.


========================================================
EXEMPLO DE EVENTO RETORNADO
========================================================

Usuário autorizado:

{
  "title": "Consulta Médica",
  "owner_trigram": "JSM",
  "visibility": "private"
}


Usuário sem permissão:

{
  "title": "Particular",
  "owner_trigram": "JSM",
  "visibility": "private"
}


========================================================
REGRAS VISUAIS RECOMENDADAS
========================================================

Público:
🌐

Privado:
🔒

Badge:
[ ABC ]

Exemplo completo:

[ ABC ] 🌴 Férias

[ JSM ] 🔒 Particular

[ TRF ] 🏥 Consulta Médica


========================================================
REGRA DE OURO
========================================================

A role do usuário autenticado determina:

- o que ele pode criar
- o que ele pode editar
- o que ele pode excluir
- o que ele pode visualizar
- o que deve ser censurado

Toda lógica deve existir no BACKEND.
========================================================