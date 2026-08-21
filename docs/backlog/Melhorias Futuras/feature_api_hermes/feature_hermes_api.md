[REFACTOR] Integração Hermes Agente | Estruturação da arquitetura de integração com SAA29

[CONTEXTO]

Planejar a integração do Hermes Agente com o SAA29, estabelecendo uma arquitetura modular, segura e escalável para acesso a informações de manutenção aeronáutica, preservando as regras de negócio existentes.

[MOTIVAÇÃO]

Criar uma base arquitetural que permita ao Hermes consultar dados operacionais, histórico de manutenção e documentação técnica, sem acoplamento direto às regras internas do sistema e sem comprometer a segurança ou a integridade dos dados.

[ESCOPO]

Fase 1 — API Read-Only
- Criar endpoints REST exclusivos para consumo do Hermes.
- Disponibilizar respostas JSON tipadas e enxutas.
- Escopo inicial apenas de leitura.

Fase 2 — Segurança
- Implementar autenticação por Service Token.
- Definir permissões exclusivas de leitura.
- Impedir qualquer operação que altere dados ou realize aprovações operacionais.

Fase 3 — Function Calling
- Definir JSON Schema para cada ferramenta exposta.
- Mapear intenções do agente para os respectivos endpoints.
- Validar chamadas automáticas às ferramentas.

Fase 4 — Pipeline RAG
- Implementar pipeline de extração dos manuais técnicos.
- Vetorizar documentação técnica.
- Integrar mecanismo de busca semântica utilizando Vector DB.

Fase 5 — Homologação
- Executar testes de integração.
- Validar cenários de timeout, indisponibilidade e limites de requisição.
- Homologar a integração e revisar os logs de interação para ajuste do comportamento do agente.

[DOCUMENTAÇÃO APLICÁVEL]

- docs/methodology/
- docs/ia/

[RESTRIÇÕES]

- Manter arquitetura compatível com Clean Architecture.
- Toda alteração estrutural no banco deve utilizar Alembic.
- Processamentos pesados devem ocorrer em background.
- O Hermes não poderá criar, editar, excluir ou aprovar registros operacionais.
- Não modificar regras de negócio existentes dos módulos do SAA29.

[ACEITE]

- APIs Read-Only disponíveis e documentadas.
- Comunicação autenticada por Service Token.
- Function Calling operacional utilizando JSON Schema.
- Pipeline RAG integrado aos manuais técnicos.
- Testes de integração aprovados.
- Homologação concluída sem impacto nos fluxos existentes.