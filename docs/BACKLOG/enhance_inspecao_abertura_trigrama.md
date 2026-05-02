[TÍTULO]
Feature | Inspeções | Capturar TRIGRAMA do usuário na abertura da inspeção

[CONTEXTO]
Módulo: Inspeções  
Tela: Módulo de Inspeções → + Abrir Inspeção → Abrir Nova Inspeção

[OBJETIVO]
Capturar automaticamente o TRIGRAMA do usuário logado que está abrindo a inspeção e salvar esse dado na tabela da inspeção para auditoria futura.

[COMPORTAMENTO ESPERADO]
- Identificar o usuário autenticado no momento da abertura
- Registrar o TRIGRAMA na nova inspeção
- Persistir o dado no backend e na tabela da inspeção
- Permitir uso futuro em auditoria e rastreabilidade

[REGRAS]
- O TRIGRAMA deve ser obtido do usuário que efetivamente abriu a inspeção
- O valor deve ser salvo automaticamente, sem preenchimento manual
- O dado deve permanecer associado à inspeção após persistência

[DEPENDÊNCIAS]
- Sistema de autenticação deve disponibilizar o usuário logado
- Estrutura da tabela/modelo da inspeção deve suportar o campo de auditoria

[RESTRIÇÕES]
- Não alterar regras de negócio existentes da abertura da inspeção
- Não expor o campo como edição manual na interface
- Não implementar lógica de auditoria além da captura e persistência do TRIGRAMA

[ACEITE]
- Nova inspeção salva com TRIGRAMA do usuário logado
- Dado disponível para consultas futuras
- Sem impacto no fluxo atual de abertura