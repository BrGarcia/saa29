[TÍTULO]
Bug | Vencimentos | Erro 403 (CSRF) ao confirmar execução de item vencido

[CONTEXTO]
Módulo: Controle de Vencimentos  
Tela: Registrar Execução  
Ação: Confirmar execução de item vencido  
Endpoint: /vencimentos/{id}/executar

[COMPORTAMENTO ATUAL]
- Notificação: “Falha na sincronia de segurança (CSRF). Por favor, recarregue a página (F5).”
- Console: 403 (Forbidden) ao chamar endpoint de execução

[COMPORTAMENTO ESPERADO]
- Execução registrada com sucesso  
- Sem erro de CSRF  
- Retorno 200/201  
- UI atualizada corretamente

[REPRODUÇÃO]
1. Acessar Controle de Vencimentos  
2. Selecionar item vencido  
3. Abrir “Registrar Execução”  
4. Clicar em “Confirmar” → erro 403

[HIPÓTESE]
- Token CSRF ausente, expirado ou não enviado na requisição  
- Cabeçalho CSRF não incluído no fetch/AJAX  
- Cookie de sessão/CSRF não sincronizado  
- Possível diferença entre método HTTP esperado e enviado (POST/PUT)

[ANÁLISE CSP]
- CSP (Content Security Policy) não está diretamente relacionada ao erro 403  
- CSP afeta carregamento de recursos (scripts, estilos), não validação CSRF  
- Baixa probabilidade de relação com CSP

[RESTRIÇÕES]
- Não alterar política CSP existente  
- Não remover proteção CSRF  
- Manter segurança da aplicação

[ACEITE]
- Requisição inclui token CSRF válido  
- Execução realizada sem erro 403  
- Sem necessidade de recarregar página  
- Fluxo funcional mantido seguro