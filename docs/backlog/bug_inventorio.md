[TÍTULO]
Bug | Inventário | Mapeamento incorreto de equipamentos por slot (seed)

[CONTEXTO]
Módulo: Inventário de Equipamentos  
Tela: Seleção de aeronave → tabela de equipamentos  
Origem dos dados: seed inicial do banco

[COMPORTAMENTO ATUAL]
- Equipamentos estão sendo mapeados por nome do item  
- Não há distinção correta por SLOT  
- Itens redundantes (ex: CMFD1, CMFD2) estão sendo tratados como equipamentos distintos ou inconsistentes

[COMPORTAMENTO ESPERADO]
- tabela contendo a localizacao, slots e equipamentos  : docs\legacy\inventario.md
- Equipamentos devem ser associados a um SLOT específico  
- SLOT deve representar a posição física/lógica do equipamento  
- Estrutura correta PARA A PAGINA "Inventario de Equipamentos":
  LOCALIZAÇÃO | SLOT | EQUIPAMENTO | PN | SN | Atualização/Trigrama | S/N (REAL) | Anv Ant.

[REGRAS DE NEGÓCIO]
- LOCALIZAÇÃO define a área da aeronave (1P, 2P, CEI, CES)  
- SLOT define a posição dentro da localização (ex: CMFD1, CMFD2, CMFD3, CMFD4, MDP1, MDP2)  
- EQUIPAMENTO é o tipo (ex: CMFD, MDP), não o slot  
- Slots são entidades independentes (não são equipamentos)  
- Um mesmo equipamento pode existir em múltiplos slots (redundância)

[REPRODUÇÃO]
1. Acessar Inventário de Equipamentos  
2. Selecionar aeronave  
3. Observar tabela carregada  
4. Verificar inconsistência na associação equipamento x slot

[HIPÓTESE]
- Seed está populando equipamentos sem entidade de SLOT  
- Relacionamento está sendo feito por nome ao invés de chave de slot  
- Ausência de tabela/relacionamento explícito de slots

[IMPACTO]
- Representação incorreta da configuração física da aeronave  
- Compromete rastreabilidade e manutenção  
- Pode afetar lógica futura de trocas e auditoria

[RESTRIÇÕES]
- Não alterar lógica de outras tabelas além do necessário  
- Preservar dados existentes quando possível  
- Manter compatibilidade com estrutura atual do inventário

[ACEITE]
- Cada equipamento corretamente associado a um SLOT  
- Slots representados como entidade própria  
- Tabela exibe dados conforme estrutura definida  
- Redundâncias (ex: CMFD1/CMFD2) corretamente representadas  
- Seed populando dados corretamente