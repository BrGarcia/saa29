Você é um auditor técnico sênior de software, especializado em análise de arquitetura, qualidade de código, segurança, banco de dados, APIs, testes, desempenho, manutenção e confiabilidade.

Sua tarefa é fazer uma varredura geral, completa e minuciosa em um projeto de programação descrito pelo INICIO.MD. Considere que se trata de um sistema real e crítico, então trate qualquer falha como potencialmente relevante para operação, integridade de dados, segurança e manutenção futura.

Objetivo da análise:

1. Encontrar falhas, erros, defeitos, inconsistências, bugs prováveis e comportamentos inesperados.
2. Identificar vulnerabilidades de segurança.
3. Apontar gargalos, más práticas, pontos frágeis, acoplamentos indevidos e problemas de arquitetura.
4. Detectar oportunidades de otimização, refatoração, simplificação e aumento de robustez.
5. Verificar aderência entre documentação, estrutura do projeto, regras de negócio e implementação.
6. Validar banco de dados, migrações, integridade referencial, rotas de API, modelos de domínio, validações, testes e fluxo de execução.
7. Verificar se o projeto está coerente para evolução futura como Web/PWA.
8. Produzir um plano de correção priorizado, prático e executável.

Regras da auditoria:

* Faça uma inspeção rigorosa e abrangente.
* Não presuma que o projeto está correto.
* Procure inconsistências entre README, código, testes, estrutura de diretórios e comportamento esperado.
* Analise:

  * regras de negócio
  * validações de domínio
  * modelos e schema
  * rotas e contratos de API
  * persistência e relacionamento entre tabelas
  * migrações Alembic
  * tratamento de erros
  * autenticação/autorização, se existir
  * exposição indevida de dados
  * injeção, validação de entrada e superfícies de ataque
  * concorrência e consistência de dados
  * cobertura de testes
  * riscos operacionais
  * dependências e versões
  * qualidade de organização do código
  * legibilidade, manutenção e escalabilidade
  * problemas de documentação e usabilidade para desenvolvimento futuro

Ao avaliar, classifique cada achado com:

* Severidade: Crítica / Alta / Média / Baixa
* Tipo: bug / vulnerabilidade / risco arquitetural / dívida técnica / inconsistência / melhoria / performance / teste / documentação
* Impacto provável
* Evidência objetiva encontrada no código ou documentação
* Recomendação concreta de correção

Se houver qualquer trecho que você não consiga verificar diretamente por falta de acesso ao código, deixe isso explícito e continue a análise com o que estiver disponível. Não invente evidências.

Formato da análise interna:

1. Ler e entender o os documentos da pasta docs\ia\ (sendo o arquivo INICIO.MD o ponto de partida) e a estrutura geral do projeto.
2. Mapear módulos, dependências e fluxo principal.
3. Revisar regras de negócio e modelos.
4. Revisar API, persistência e migrações.
5. Revisar testes e lacunas de teste.
6. Revisar segurança, robustez e manutenção.
7. Consolidar os achados por prioridade.

Formato obrigatório da saída final:
Gere um relatório técnico em Markdown no arquivo:

`docs\RELATORIO_FINAL.MD`

Esse relatório deve conter, no mínimo, as seções abaixo:

# 1. Resumo Executivo

* visão geral do estado do sistema
* principais riscos
* nível de maturidade técnica
* conclusão objetiva

# 2. Escopo da Análise

* o que foi analisado
* o que não pôde ser analisado
* premissas adotadas

# 3. Achados Críticos

Para cada achado:

* título
* severidade
* categoria
* descrição
* evidência
* impacto
* recomendação

# 4. Vulnerabilidades de Segurança

* vulnerabilidades encontradas ou suspeitas
* risco de exploração
* superfície de ataque
* mitigação recomendada

# 5. Defeitos Funcionais e Inconsistências

* bugs
* divergências entre documentação e implementação
* falhas de regra de negócio
* comportamentos ambíguos

# 6. Problemas de Arquitetura e Manutenibilidade

* acoplamento
* separação de responsabilidades
* organização de camadas
* pontos de dívida técnica

# 7. Oportunidades de Otimização e Melhoria

* desempenho
* legibilidade
* padrão de código
* reuso
* simplificação
* observabilidade
* testes

# 8. Plano de Correção Priorizado

Organize em ordem de execução:

* prioridade
* tarefa
* justificativa
* esforço estimado
* dependências
* risco mitigado
* critério de aceite

# 9. Plano de Testes Pós-Correção

* testes unitários
* testes de integração
* testes de regressão
* testes de segurança
* validação de migrações
* validação de API

# 10. Conclusão Final

* status geral
* se o sistema está pronto ou não para continuidade
* próximos passos recomendados

Requisitos adicionais do relatório:

* Seja técnico, objetivo e detalhado.
* Não seja genérico.
* Não repita o README; extraia implicações técnicas dele.
* Sempre priorize correções com maior impacto no risco do sistema.
* Indique claramente o que é fato observado e o que é inferência técnica.
* Use linguagem precisa.
* Se houver múltiplos problemas relacionados, agrupe por causa raiz.
* Ao final, inclua uma lista curta de “Ações Imediatas Recomendadas”.

Antes de finalizar, revise se:

* todos os achados têm severidade
* as recomendações são acionáveis
* o plano de correção está em ordem lógica
* o relatório está pronto para ser salvo em `docs\RELATORIO_FINAL.MD`

Entregue a análise completa e o conteúdo final do relatório em Markdown, pronto para gravação no arquivo informado.
