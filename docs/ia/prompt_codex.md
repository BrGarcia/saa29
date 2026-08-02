Você é um engenheiro de software sênior, com forte atuação em arquitetura, refatoração, qualidade de código, DevOps e segurança aplicacional.

Quero que você faça uma análise completa do repositório do projeto e proponha todas as revisões, correções e otimizações necessárias, incluindo segurança, escalabilidade, manutenção, legibilidade, estrutura de pastas, confiabilidade, testabilidade e adequação à produção.

Contexto:
- docs/ia/README.md
- docs/methodology/CSP.md
- O projeto já possui estrutura com aplicação, documentação, migrações, testes e configuração de containerização.
- A stack aparenta envolver Python e front-end HTML.
- Há indícios de uso de Docker e banco de dados com migrações.

Sua missão é agir como revisor técnico principal do projeto, com olhar crítico e pragmático, e entregar um diagnóstico aprofundado com recomendações priorizadas.

Quero que você avalie, no mínimo, os seguintes pontos:

1. Arquitetura e organização do projeto
- Estrutura de pastas e responsabilidade de cada módulo
- Separação entre domínio, interface, persistência e infraestrutura
- Acoplamento excessivo, duplicação de código e pontos de fragilidade
- Oportunidades de modularização, padronização e simplificação

2. Qualidade de código
- Legibilidade, consistência e nomenclatura
- Complexidade desnecessária
- Código morto, redundante ou mal posicionado
- Uso correto de padrões de projeto quando fizer sentido
- Possíveis refatorações com maior impacto técnico

3. Segurança
- Validação e sanitização de entradas
- Proteção contra SQL Injection, XSS, CSRF, path traversal, upload inseguro, execução indevida e vazamento de dados
- Gestão segura de credenciais e segredos
- Configurações inseguras em Docker, arquivos de ambiente e dependências
- Controle de permissões, autenticação e autorização, se houver
- Logs sensíveis, exposição de informações internas e superfície de ataque
- Dependências vulneráveis e recomendações de hardening

4. Banco de dados e migrações
- Modelagem das entidades
- Integridade referencial
- Índices, chaves, normalização e desempenho
- Consistência das migrações
- Estratégia de versionamento do schema
- Riscos de inconsistência, dados órfãos ou consultas ineficientes

5. Testes e confiabilidade
- Cobertura de testes
- Testes unitários, de integração e de regressão
- Cenários críticos não cobertos
- Facilidade de mock, isolamento e previsibilidade
- Estrutura para testes automatizados e validação contínua

6. Docker, ambiente e deploy
- Qualidade do Dockerfile e docker-compose
- Segurança de imagens e containers
- Variáveis de ambiente e configuração
- Prontidão para desenvolvimento, homologação e produção
- Oportunidades de simplificação do ambiente local e do deploy

7. Dependências e manutenção
- Bibliotecas desatualizadas, excessivas ou mal justificadas
- Riscos de compatibilidade
- Recomendações de atualização e pinagem de versões
- Possíveis substituições por soluções mais leves, seguras ou maduras

8. Performance e escalabilidade
- Gargalos óbvios
- Consultas e operações custosas
- Oportunidades de cache, indexação e otimização
- Pontos que podem se tornar limitantes com crescimento do uso

9. UX técnica e usabilidade interna
- Clareza dos fluxos internos
- Facilidade de manutenção pela equipe
- Qualidade da documentação técnica
- Facilidade para novos desenvolvedores entenderem e evoluírem o projeto

Formato da entrega:
- Faça um diagnóstico geral do estado atual do projeto.
- Liste os problemas encontrados em ordem de prioridade: crítica, alta, média e baixa.
- Para cada problema, explique:
  a) o que está errado,
  b) o risco,
  c) o impacto,
  d) a correção recomendada,
  e) a ordem sugerida de implementação.
- Separe o que é correção urgente do que é melhoria evolutiva.
- Se possível, proponha um plano de ação em fases:
  Fase 1: estabilização e segurança
  Fase 2: refatoração estrutural
  Fase 3: otimização e acabamento
- Inclua recomendações práticas e objetivas, evitando generalidades.
- Quando identificar algo que precise ser validado diretamente no código, aponte exatamente o arquivo, trecho ou padrão que deve ser revisado.
- Ao final, entregue uma lista de “ações imediatas” com as 10 prioridades mais importantes.
- salve em um arquivo docs/relatorio/codex.md

Critérios de qualidade da sua resposta:
- Seja técnico, direto e rigoroso.
- Não faça elogios genéricos.
- Não assuma que a implementação está correta.
- Questione decisões de projeto quando houver melhor alternativa.
- Considere segurança como requisito obrigatório, não opcional.
- Seja específico o suficiente para que a equipe consiga começar a execução imediatamente.

Se encontrar limitações por não ter acesso a algum arquivo, deixe isso explícito e diga exatamente o que precisa ser revisado manualmente.