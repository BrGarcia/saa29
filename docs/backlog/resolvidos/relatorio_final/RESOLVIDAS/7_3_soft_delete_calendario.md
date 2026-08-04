# Backlog Item 7.3: Falta de Rastreabilidade em Remoções de Eventos (Hard Delete)

## 1. Descrição do Problema
O módulo de calendário realizava a remoção física de eventos (`db.delete()`), deletando registros permanentes do banco sem deixar trilha de auditoria. Como o calendário gerencia indisponibilidades e escalas de mecânicos que impactam voos, a falta de histórico de deleção constituía falha de conformidade na rastreabilidade militar.

## 2. Plano de Implementação
1. **Adicionar colunas ao modelo:** Adicionar os campos `deleted_at: DateTime | None` e `deleted_by_user_id: UUID | None` na classe `CalendarEvent` do arquivo `app/modules/calendario/models.py`.
2. **Nova Migração Alembic:** Gerar o script de migração do banco correspondente para incluir as colunas.
3. **Mudar para Soft Delete no Service:** Em `delete_event` no service de calendário:
   - Substituir `db.delete(event)` por `event.deleted_at = datetime.now(timezone.utc)` e `event.deleted_by_user_id = current_user.id`.
   - Adicionar log de auditoria `logger.warning("calendar_event_deleted", extra=...)` registrando o executor e os dados apagados.
4. **Filtro de Consulta:** Garantir que a busca de eventos de calendário filtre os registros ativos (`deleted_at.is_(None)`).

## 3. Critérios de Aceitação
* A deleção de um evento do calendário não apaga o registro do banco, apenas preenche as colunas `deleted_at` e `deleted_by_user_id`.
* O evento removido desaparece das requisições comuns de listagem `/api/v1/calendario/eventos`.
* Logs estruturados registram os dados da remoção para conformidade e segurança da auditoria.
