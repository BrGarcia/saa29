# Backlog Item 4.2: Exposição Indevida de Dados de Privacidade em Eventos Particulares

## 1. Descrição do Problema
O calendário de escalas permitia que usuários comuns sem papel de gerência visualizassem dados parciais de eventos com status de visibilidade privada (`visibility_type='private'`). O payload da API mantinha o trigrama do militar (`owner_trigram`) e a cor original associada ao tipo de evento (`backgroundColor` derivada de `EventType.color`), expondo de forma indireta motivos de afastamento (ex: consultas médicas).

## 2. Plano de Implementação
1. **Verificação de privilégio e propriedade:** Na função `format_event_for_user` do arquivo `app/modules/calendario/service.py`, implementar a guarda `_should_censor(event, current_user)` que retorna verdadeiro se o evento for privado E o usuário não for o criador/dono do evento E o usuário não possuir papel privilegiado (ENCARREGADO ou ADMINISTRADOR).
2. **Censura Completa:** No caso de censura, retornar o payload com:
   - `title="Particular"`
   - `owner_trigram=None` (oculta a identidade)
   - `owner_user_id=None`
   - `event_type_id=None` (oculta o tipo de categoria)
   - `notes=None`
   - `backgroundColor = event.event_type.private_color or "#9CA3AF"` (cor cinza neutra estipulada para privacidade).

## 3. Critérios de Aceitação
* Um mantenedor buscando os eventos de calendário só visualiza o título "Particular" e uma cor cinza neutra em eventos privados de terceiros.
* Os campos `owner_trigram`, `owner_user_id`, `event_type_id` e `notes` chegam nulos no JSON de resposta para eventos privados censurados.
* O teste `test_rbac_censura_privado_para_terceiro_sem_privilegio` em `tests/test_calendario.py` valida esse comportamento.
