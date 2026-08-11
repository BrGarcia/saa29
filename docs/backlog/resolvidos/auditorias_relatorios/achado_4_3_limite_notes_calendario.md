# Backlog Item 4.3: Ausência de Limites no campo de anotações (notes) de eventos

## 1. Descrição do Problema
Os schemas de entrada `CalendarEventCreate` e `CalendarEventUpdate` não continham validação de limite de comprimento para o campo de notas (`notes`), permitindo que clientes maliciosos ou payloads exagerados inflassem o banco de dados armazenando megabytes de texto no campo `Text` da tabela `calendar_events`.

## 2. Plano de Implementação
1. **Importação do Field do Pydantic:** Modificar o arquivo `app/modules/calendario/schemas.py`.
2. **Definição de limite de caracteres:** Ajustar o campo `notes` nos schemas de criação e atualização de eventos:
   ```python
   notes: str | None = Field(default=None, max_length=2000, description="Observações do evento")
   ```
3. **Revisar serializadores:** Assegurar que o schema de saída `CalendarEventOut` também documente a restrição.

## 3. Critérios de Aceitação
* Qualquer requisição com o campo `notes` contendo mais de 2000 caracteres é rejeitada na borda da API pelo Pydantic, retornando erro de validação com status `422 Unprocessable Entity`.
* A documentação da API em `/docs` exibe a restrição `max_length: 2000` para o campo `notes` de criação e edição.
* Um teste unitário tenta cadastrar notas com 2001 caracteres e confirma a falha.
