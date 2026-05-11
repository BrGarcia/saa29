# Explicação das Correções de Auditoria — SAA29

> **Para quem é este documento?**
> Este arquivo explica, em linguagem simples, o que foi corrigido no sistema SAA29 ao longo das rodadas de auditoria de código. Não é necessário ter conhecimento técnico para entender os problemas e as soluções aqui descritos.

---

## O que é uma "auditoria de código"?

É uma revisão detalhada feita por uma IA especializada (Claude) que lê todo o código do sistema em busca de falhas de segurança, bugs e problemas de arquitetura — assim como um oficial de segurança de voo revisa procedimentos para encontrar riscos antes que causem acidentes.

---

## Rodada 1 — 05/05/2026

### ✅ Sessão não encerrava corretamente (Segurança)
**Problema:** Quando um usuário clicava em "Sair", o sistema apagava o acesso principal, mas deixava uma "porta dos fundos" aberta. Se alguém tivesse capturado essa chave de acesso secundária, poderia continuar usando o sistema mesmo após o logout.

**Correção:** Agora o logout fecha todas as portas — a principal e a secundária — e registra o encerramento no banco de dados.

---

### ✅ Usuário desativado ainda entrava no sistema (Segurança)
**Problema:** Quando um militar era desligado do efetivo e sua conta era desativada no sistema, ele ainda conseguia continuar usando o sistema pelo tempo que sua senha ativa durasse (até 15 minutos).

**Correção:** Agora, ao receber qualquer requisição, o sistema verifica se o usuário ainda está ativo. Se a conta foi desativada, o acesso é bloqueado imediatamente.

---

### ✅ Cancelar inspeção liberava aeronave indevidamente (Bug)
**Problema:** Imagine que uma aeronave está em duas inspeções simultâneas (de tipos diferentes). Se a inspeção A fosse cancelada, o sistema marcava a aeronave como "disponível" — mesmo que a inspeção B ainda estivesse em andamento.

**Correção:** Antes de liberar a aeronave, o sistema agora verifica se há outras inspeções ativas. A aeronave só fica "disponível" quando **todas** as inspeções forem encerradas.

---

### ✅ Tarefa obrigatória podia virar opcional (Bug)
**Problema:** Quando uma inspeção misturava vários tipos, tarefas que apareciam em mais de um tipo eram "mescladas". Se o primeiro tipo tinha a tarefa como opcional e o segundo como obrigatória, a tarefa final ficava opcional — permitindo que a inspeção fosse concluída sem realizá-la.

**Correção:** Agora, se uma tarefa é obrigatória em **qualquer** tipo de inspeção, ela é sempre obrigatória — sem exceção.

---

### ✅ Registro de acesso em estado inconsistente (Arquitetura)
**Problema:** O módulo de autenticação finalizava o registro de tentativas de login em um momento diferente do resto do sistema. Isso poderia causar situações onde o login de tentativas era salvo mas o token de acesso não era criado — ou vice-versa.

**Correção:** O processo de autenticação agora segue o mesmo padrão do resto do sistema, garantindo que tudo é salvo junto ou descartado junto.

---

## Rodada 2 — 06/05/2026

### ✅ Proteção anti-ataque podia ser desativada em ambiente de teste (Segurança)
**Problema:** O sistema possui uma proteção chamada CSRF que impede que sites externos façam ações em nome do usuário. Porém, essa proteção podia ser desligada enviando um cabeçalho especial em ambientes que não fossem "produção" (como staging ou homologação), onde existem dados reais de militares. Um atacante que conhecesse esse mecanismo poderia explorar isso.

**Correção:** Agora essa "válvula de escape" só funciona em ambiente de testes automatizados (ambiente interno da equipe de desenvolvimento), nunca em ambientes com dados reais.

---

### ✅ Equipamento novo não entrava no controle de vencimentos (Bug)
**Problema:** Quando um técnico registrava um número de série novo diretamente pelo ajuste de inventário, o equipamento era cadastrado mas não recebia as regras de vencimento (prazos de calibração, inspeção, etc.) que são definidas para aquele modelo. O item ficava "invisível" para o controle de prazos.

**Correção:** Agora, ao criar um novo item pelo ajuste de inventário, o sistema copia automaticamente todas as regras de vencimento definidas para aquele modelo de equipamento.

---

### ✅ Arquivo anexo podia ficar "fantasma" no armazenamento em nuvem (Bug)
**Problema:** Ao excluir um anexo (foto ou PDF de uma pane), o sistema primeiro apagava o registro do banco de dados e depois tentava apagar o arquivo na nuvem. Se a nuvem estivesse instável ou indisponível, o arquivo continuava lá — sem nenhum registro no banco que permitisse encontrá-lo e apagá-lo depois. Resultado: arquivos sensíveis (fotos de panes) acumulando-se na nuvem sem controle.

**Correção:** A ordem foi invertida. Agora o sistema tenta apagar o arquivo na nuvem **primeiro**. Só se essa operação for bem-sucedida o registro é removido do banco.

---

### ✅ Foto em processamento podia ficar "travada" para sempre (Bug)
**Problema:** Quando uma foto era enviada, ela era processada em segundo plano para otimizar o tamanho. Se o processamento falhasse, o sistema deixava o anexo registrado com o status "processando" indefinidamente. O usuário via um ícone quebrado e acreditava que o upload tinha funcionado.

**Correção:** Se o processamento falhar completamente, o sistema agora marca o anexo como "ERRO" (ou remove o registro), deixando claro para o usuário que precisa enviar o arquivo novamente.

---

### ✅ Módulo de efetivo também salvava dados fora de ordem (Arquitetura)
**Problema:** Assim como o problema do login (corrigido anteriormente), as funções de registro e remoção de indisponibilidade de militares também salvavam os dados no banco antes da hora, em vez de seguir o padrão de esperar o fim de toda a operação para confirmar. Isso poderia causar inconsistências se outra operação encadeada falhasse.

**Correção:** As funções agora seguem o padrão do resto do sistema.

---

## Rodada 3 — 06/05/2026 (continuação)

### ✅ Botão de "inativar" aeronave em inspeção causava problema (Bug)
**Problema:** Se um encarregado clicava no botão de alternar status de uma aeronave que estava em inspeção, o sistema a marcava como "INATIVA" — sem cancelar a inspeção no banco. A inspeção continuava registrada como ativa, mas a aeronave estava com status inconsistente.

**Correção:** Agora o sistema bloqueia essa ação com uma mensagem clara: "Aeronave está em inspeção. Encerre a inspeção antes de alterar o status."

---

### ✅ Prazo de calibração calculado com periodicidade errada (Bug — Risco Operacional)
**Problema:** Se um equipamento não tivesse uma regra de periodicidade cadastrada (por inconsistência nos dados), o sistema usava silenciosamente 12 meses como padrão. Para um equipamento de calibração semestral (6 meses), isso dobrava o prazo — e a anomalia não era sinalizada em lugar nenhum.

**Correção:** O sistema agora lança um erro explícito quando não encontra a regra de periodicidade, forçando a equipe a corrigir os dados antes de registrar a execução.

---

### ✅ Mudança de periodicidade não atualizava equipamentos existentes (Bug)
**Problema:** Quando a periodicidade de um tipo de equipamento era alterada (por exemplo, de 12 para 6 meses), os itens já cadastrados continuavam com a data de vencimento calculada pelo prazo antigo. A matriz de vencimentos continuava mostrando dados incorretos até o próximo registro de execução.

**Correção:** Ao alterar a periodicidade, o sistema recalcula automaticamente a data de vencimento de todos os itens que já tiveram pelo menos uma execução registrada.

---

## Rodada 4 — 07/05/2026

### ✅ Falha na nuvem não era detectada ao excluir anexo (Bug + Segurança)
**Problema:** A correção da Rodada 2 (excluir da nuvem antes do banco) tinha uma brecha: o serviço de armazenamento na nuvem R2 capturava qualquer erro e retornava silenciosamente "falhou" (false) sem lançar exceção. O sistema de exclusão de anexo não checava esse retorno, então continuava e apagava o registro do banco mesmo com o arquivo ainda na nuvem. O resultado era idêntico ao problema original — arquivos sensíveis órfãos na nuvem.

**Correção:** Agora o serviço de nuvem lança uma exceção real quando falha, e a função de exclusão do anexo verifica o resultado antes de prosseguir.

---

### ✅ Inspeção podia ser aberta em aeronave inativa (Bug)
**Problema:** Um encarregado podia abrir uma inspeção em uma aeronave marcada como "INATIVA" (deliberadamente retirada de serviço). Ao abrir a inspeção, o sistema mudava automaticamente o status da aeronave para "EM INSPEÇÃO" — reativando-a sem nenhum registro de quem autorizou isso.

**Correção:** O sistema agora bloqueia a abertura de inspeção em aeronaves inativas, exigindo que a reativação seja feita de forma explícita e rastreável.

---

### ✅ Token de acesso roubado não era completamente invalidado (Segurança)
**Problema:** Ao refrescar o acesso (trocar o token antigo por um novo), o sistema invalidava o antigo. Porém, se alguém usasse um token já invalidado (sinal claro de que foi copiado ou roubado), o sistema apenas retornava "acesso negado" sem tomar nenhuma ação adicional. O atacante com a cópia do token antigo e o usuário legítimo podiam continuar trocando tokens alternadamente.

**Correção:** Se um token já invalidado for usado novamente, o sistema interpreta isso como indício de comprometimento e revoga **todos** os tokens ativos daquele usuário — forçando um novo login completo e eliminando o acesso do possível atacante.

---

### ✅ Qualquer usuário podia movimentar inventário (Segurança — RBAC)
**Problema:** As rotas de instalação e remoção de equipamentos em aeronaves estavam abertas a qualquer usuário autenticado, incluindo perfis como INSPETOR, que só deveriam vistoriar — não mover peças. Não havia controle de quem tinha permissão para realizar essas ações.

**Correção:** Agora as rotas de instalação e remoção exigem o papel de MANTENEDOR, ENCARREGADO ou ADMINISTRADOR. O ajuste de inventário (ainda mais sensível) exige ENCARREGADO ou ADMINISTRADOR.

---

## Rodada 5 — 07/05/2026 (continuação)

### ✅ Papel do responsável numa pane podia ser forjado (Segurança)
**Problema:** Ao adicionar um responsável a uma pane, o sistema permitia que o próprio usuário informasse qual era o seu papel (ex: "ADMINISTRADOR"), mesmo sendo um MANTENEDOR. Esse dado era salvo sem verificação, corrompendo registros de responsabilidade aeronáutica.

**Correção:** O sistema agora ignora o que o usuário informa como papel e busca o papel real do banco de dados, garantindo que o registro de responsabilidade é sempre fidedigno.

---

### ✅ Instalação de equipamento não registrava quem a fez (Bug — Rastreabilidade)
**Problema:** Ao instalar um equipamento em uma aeronave, o campo "quem instalou" era gravado como nulo (vazio). O histórico de instalações ficava com "buracos" — sem identificar o responsável pela movimentação.

**Correção:** O sistema agora captura o usuário autenticado e grava corretamente no registro de instalação.

---

### ✅ Senha com caracteres especiais podia causar falha (Bug)
**Problema:** O algoritmo de segurança de senhas (bcrypt) tem um limite de 72 bytes. O código truncava a senha em 72 *caracteres* — mas letras com acento ou emojis podem ocupar 2 a 4 bytes cada. Uma senha com muitos desses caracteres podia exceder o limite, causando erros imprevisíveis ou divergência entre o cadastro e o login.

**Correção:** Agora a senha é convertida para um formato de tamanho fixo (hash SHA-256 + Base64 = sempre 44 bytes) antes de ser processada pelo bcrypt, eliminando completamente o problema do limite de bytes.

---

## Rodada 6 — 11/05/2026 (Módulo Calendário)

### ✅ Inspeções encerradas apareciam no calendário (Bug)
**Problema:** O calendário mostrava a data prevista de encerramento (DPE) de **todas** as inspeções, inclusive as que já tinham sido concluídas ou canceladas. O resultado era um calendário poluído com prazos que já não existiam mais, podendo confundir o planejamento da frota.

**Correção:** O calendário agora exibe apenas inspeções que estejam com status ABERTA ou EM ANDAMENTO. Inspeções já encerradas desaparecem automaticamente.

---

### ✅ Evento particular vazava informações sensíveis (Segurança/Privacidade)
**Problema:** Quando um evento era marcado como "Particular" (privado), o sistema ocultava o título — mas ainda enviava no JSON: o trigrama do militar (ex: "FUL"), o UUID do usuário e a cor do tipo de evento (que é única por tipo). Com essas informações, qualquer colega podia deduzir "Sgt FUL tem um compromisso médico na quarta-feira" — exatamente o que a privacidade deveria proteger.

**Correção:** Eventos privados agora enviam apenas informações neutras: trigrama nulo, UUID nulo, cor genérica cinza (`#9CA3AF`) e tipo de evento nulo. Nenhuma informação que permita identificar a pessoa ou a natureza do compromisso é exposta.

---

### ✅ Papéis de acesso duplicados e com alias errado (Arquitetura)
**Problema:** O módulo de calendário tinha sua própria lista de papéis permitidos, separada do resto do sistema, e incluía o alias `"ADMIN"` — que não existe no SAA29 (o papel correto é `"ADMINISTRADOR"`). Isso criava uma inconsistência silenciosa: se no futuro um usuário fosse cadastrado erroneamente como `"ADMIN"`, o calendário o aceitaria enquanto todos os outros módulos o rejeitariam.

**Correção:** Criado um arquivo central (`roles.py`) com os papéis oficiais do sistema. O módulo de calendário agora usa essas constantes centralizadas. O alias `"ADMIN"` foi eliminado completamente.

---

### ✅ Qualquer usuário podia sobrecarregar o servidor com uma consulta (Segurança — DoS)
**Problema:** A rota do calendário aceitava qualquer intervalo de datas sem limitação. Um usuário podia pedir todos os eventos de 1900 até 3000 em uma única requisição — forçando o servidor a buscar, processar e serializar dezenas de milhares de registros de uma vez, podendo derrubá-lo.

**Correção:** O sistema agora rejeita consultas com intervalo maior que 366 dias (um ano civil). Além disso, as consultas internas têm um limite máximo de 5.000 registros, com alerta automático se esse limite for atingido.

---

### ✅ Exclusão de evento não deixava rastro (Rastreabilidade)
**Problema:** Ao excluir um evento do calendário (licença, afastamento médico, etc.), o registro era simplesmente apagado do banco de dados sem nenhum log, sem saber quem apagou e quando. Em um sistema aeronáutico, isso é crítico: se uma licença for apagada indevidamente antes de uma inspeção, não há como saber quem fez isso.

**Correção:** A exclusão agora é um "soft-delete" — o evento não é apagado fisicamente, apenas marcado como excluído (com data e responsável). Um log estruturado é gerado registrando quem excluiu, qual evento, de quem era e quando começava. O evento desaparece das consultas normais, mas permanece no banco para auditoria.

---

## Resumo Geral

| # | Tema | Tipo | Status |
|---|------|------|--------|
| 1 | Logout não encerrava a sessão completamente | Segurança | ✅ Corrigido |
| 2 | Usuário desativado ainda acessava o sistema | Segurança | ✅ Corrigido |
| 3 | Cancelar inspeção liberava aeronave errada | Bug Operacional | ✅ Corrigido |
| 4 | Tarefa obrigatória podia virar opcional | Bug Operacional | ✅ Corrigido |
| 5 | Dados de autenticação salvos fora de ordem | Arquitetura | ✅ Corrigido |
| 6 | Proteção CSRF desligável em staging | Segurança | ✅ Corrigido |
| 7 | Novo equipamento sem controle de prazos | Bug Operacional | ✅ Corrigido |
| 8 | Anexo excluído ficava na nuvem | Bug / Rastreabilidade | ✅ Corrigido |
| 9 | Foto travada em "processando" para sempre | Bug de UX | ✅ Corrigido |
| 10 | Módulo de efetivo com padrão inconsistente | Arquitetura | ✅ Corrigido |
| 11 | Inativar aeronave em inspeção causava inconsistência | Bug Operacional | ✅ Corrigido |
| 12 | Prazo de calibração calculado errado | Bug — Risco Operacional | ✅ Corrigido |
| 13 | Mudança de periodicidade não atualizava itens existentes | Bug Operacional | ✅ Corrigido |
| 14 | Falha na nuvem não era detectada ao excluir anexo | Bug / Segurança | ✅ Corrigido |
| 15 | Inspeção aberta em aeronave inativa | Bug Operacional | ✅ Corrigido |
| 16 | Token roubado não era completamente invalidado | Segurança Crítica | ✅ Corrigido |
| 17 | Qualquer usuário movia inventário | Segurança — RBAC | ✅ Corrigido |
| 18 | Papel de responsável numa pane podia ser forjado | Rastreabilidade | ✅ Corrigido |
| 19 | Instalação sem registro do executor | Rastreabilidade | ✅ Corrigido |
| 20 | Senha com acentos/emojis causava falha no login | Bug de Segurança | ✅ Corrigido |
| 21 | Inspeções encerradas apareciam no calendário | Bug Operacional | ✅ Corrigido |
| 22 | Evento particular vazava dados do militar | Privacidade / LGPD | ✅ Corrigido |
| 23 | Papéis duplicados com alias indevido no calendário | Arquitetura RBAC | ✅ Corrigido |
| 24 | Consulta sem limite podia derrubar o servidor | Segurança — DoS | ✅ Corrigido |
| 25 | Exclusão de evento sem rastro de auditoria | Rastreabilidade | ✅ Corrigido |
