# INSTRUCOES.MD: Metodologia de Desenvolvimento com IA (Método Akita)

## Dia 1: AI Jail (Isolamento e Governança)
* **Objetivo:** Isolar o ambiente em que a IA irá operar [00:34:37].
* **Ação:** Utilizar ferramentas de contêinerização (como Docker) para evitar que o agente de IA tenha acesso irrestrito à sua máquina física ou sistema operacional. Isso previne a execução acidental de comandos destrutivos e garante maior controle e segurança sobre o escopo do agente.

## Dia 2: Fundação (Arquitetura e Planejamento)
* **Objetivo:** Criar toda a estrutura teórica e de configuração do projeto sem escrever código funcional [00:35:10].
* **Ações:**
  * Escrever as histórias e descrever em detalhes cada funcionalidade do projeto.
  * Tomar decisões definitivas de arquitetura (ex: escolha entre banco de dados relacional ou não relacional, divisão de microsserviços, linguagens de back-end).
  * Criar configurações básicas, como o `docker-compose`, chaves de API e definir a estrutura de diretórios (como a organização de um monorepo).
  * Documentar absolutamente todas essas decisões técnicas no arquivo central de memória do projeto (geralmente nomeado como `cloud.md`).

## Dia 3: Testes (TDD Rigoroso)
* **Objetivo:** Estabelecer a rede de segurança através da cobertura de testes antes de qualquer implementação [00:37:23].
* **Ação:** Exigir que a IA escreva testes baseados nas funcionalidades planejadas no Dia 2. Os testes devem utilizar dados "mocados" (simulados) neste primeiro momento. Se a IA sugerir uma função de código sem o respectivo teste, recuse imediatamente. A regra inviolável desta etapa é: primeiro escreve-se o teste, depois a funcionalidade.

## Dia 4: Mão na Massa (Codificação)
* **Objetivo:** Fazer os testes do dia anterior passarem com sucesso [00:38:11].
* **Ação:** Começar a gerar e escrever o código funcional, garantindo que toda nova linha passe na suíte de testes do Dia 3. Neste momento, não se preocupe com performance, otimização de queries de banco de dados ou sistemas de cache. Se surgir a necessidade de uma nova *feature* durante o processo, pare o desenvolvimento, escreva o teste para ela primeiro, e só então gere o código correspondente.

## Dia 5: Otimização e Refatoração
* **Objetivo:** Melhorar a qualidade e o desempenho do código que já está funcionando e passando nos testes [00:38:52].
* **Ação:** Analisar gargalos do sistema, refatorar arquivos que ficaram muito extensos ou acoplados, melhorar tempos de resposta lentos e reavaliar componentes da arquitetura (por exemplo, implementando filas, *jobs* assíncronos ou adaptando lógicas para eventos se a abordagem REST inicial não performar bem).

## Dia 6: Interface de Saída
* **Objetivo:** Construir a camada através da qual o usuário final vai interagir com o sistema [00:40:23].
* **Ação:** Focar no desenvolvimento visual e de interação, como um Front-end (Next.js, React, etc.), um aplicativo mobile, ou até mesmo interfaces alternativas (como um bot no Discord). A essa altura, toda a fundação e a lógica de negócios central já devem estar prontas e testadas.

## Dia 7: Deploy e CI/CD
* **Objetivo:** Colocar o projeto em produção com segurança e automação contínua [00:41:05].
* **Ações:** * Estruturar a esteira de CI/CD criando scripts que rodem validadores de código automáticos (linters e detectores de *code smells*).
  * Configurar ferramentas focadas na análise de vulnerabilidades de segurança do código.
  * Executar automaticamente toda a bateria de testes de integração.
  * Configurar o servidor de produção (como Vercel, VPS dedicada ou instâncias rodando Coolify) e efetuar o deploy final da aplicação de forma automatizada.