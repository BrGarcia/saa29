# SAA29 — Estado Atual do Projeto e Roadmap Futuro

Bem-vindo ao guia do **SAA29 (Sistema de Gestão de Panes – Eletrônica A-29)**. Este documento foi escrito em linguagem natural e descomplicada para que, se você precisar mexer no projeto no futuro, compreenda imediatamente a proposta, como ele funciona e por onde começar.

---

## 1. O que é o SAA29? (A Ideia Geral)

O SAA29 é um sistema web desenvolvido para gerenciar e acompanhar a manutenção dos sistemas eletrônicos (aviônicos) da frota de aeronaves **A-29 Super Tucano**. 

Em termos práticos, ele funciona como uma "torre de controle" para os mecânicos e gestores de hangar. Em vez de usar planilhas soltas ou papéis para anotar quando um rádio quebrou ou quando um painel precisa de calibração, tudo é registrado de forma centralizada e transparente no SAA29. 

O sistema garante que:
*   Os mecânicos saibam exatamente quais falhas resolver.
*   Os inspetores validem a segurança do trabalho antes da aeronave voar.
*   Os chefes de manutenção (encarregados) vejam na tela a disponibilidade de toda a frota em tempo real.
*   Nenhum componente voe com prazo de calibração ou manutenção vencido.

---

## 2. O que o Sistema já Faz Hoje? (Funcionalidades Atuais)

O SAA29 é um software completo e funcional. Suas principais engrenagens são:

1.  **Dashboard Central (Painel de Controle):** 
    Uma tela visual moderna e limpa que resume a situação da frota inteira (quantos aviões estão prontos para voar, quantos estão em manutenção, as falhas mais críticas pendentes de conserto, e um calendário semanal resumido).
2.  **Controle de Panes (Falhas):**
    Registro detalhado de falhas eletrônicas. Permite anexar fotos dos problemas no avião, registrar quem trabalhou para resolver, e manter um histórico completo de manutenção da aeronave.
3.  **Controle de Inventário e Equipamentos:**
    Gerenciamento de "quem está onde". O sistema sabe quais equipamentos eletrônicos (com número de série único) estão instalados em quais posições físicas de cada aeronave, mantendo a rastreabilidade caso um rádio ou computador de bordo seja trocado de avião.
4.  **Monitoramento de Vencimentos (Alertas):**
    Acompanhamento automático dos prazos de validade de calibrações e testes de vida útil dos equipamentos. O sistema emite alertas visuais coloridos (Verde = OK, Laranja = Próximo ao Vencimento, Vermelho = Vencido).
5.  **Gestão de Inspeções Programadas:**
    Gerenciamento de revisões periódicas das aeronaves. Cada revisão tem um checklist de tarefas obrigatórias. O sistema bloqueia a liberação da aeronave se houver tarefas pendentes ou panes impeditivas em aberto.
6.  **Calendário de Escalas e Ausências:**
    Planejamento visual de equipe e prazos. Permite registrar quando um militar estará de férias, licença ou serviço, e exibe os prazos das inspeções das aeronaves.
7.  **Controle de Níveis de Acesso (Perfis):**
    *   **Mantenedor (Mecânico):** Executa o trabalho físico, abre panes, faz substituições no inventário.
    *   **Inspetor:** Confere e valida o trabalho executado para garantir a segurança.
    *   **Encarregado (Chefe):** Coordena prioridades e altera a disponibilidade da frota.
    *   **Administrador:** Cadastra usuários e gerencia o catálogo geral.
8.  **Backup e Recuperação Automática no Cloudflare R2:**
    Toda vez que a aplicação inicializa, ela baixa automaticamente o banco de dados seguro salvo na nuvem da Cloudflare (R2). Ao sofrer modificações, ela atualiza o backup remoto de forma inteligente. Se a conexão falhar criticamente, o sistema aborta a inicialização para evitar que um banco vazio sobrescreva os dados históricos.

---

## 3. Como o Sistema se Organiza por Dentro? (Estrutura)

Para quem precisa olhar as pastas do projeto, a divisão é muito intuitiva:

```text
SAA29/
├── app/                      # Onde bate o coração do sistema
│   ├── bootstrap/            # Configurações iniciais, banco e tarefas de backup
│   ├── modules/              # A Lógica do negócio (a parte inteligente)
│   │   ├── aeronaves/        # Regras das células físicas
│   │   ├── auth/             # Cadastro de usuários, senhas e permissões
│   │   ├── calendario/       # Prazos e afastamentos
│   │   ├── dashboard/        # Estatísticas rápidas da tela inicial
│   │   ├── efetivo/          # Cadastro de mantenedores e inspetores
│   │   ├── equipamentos/     # Cadastro de peças e itens físicos
│   │   ├── inspecoes/        # Checklist de revisões periódicas
│   │   ├── panes/            # Gestão e histórico de panes
│   │   └── vencimentos/      # Cálculo de prazos de calibração
│   └── web/                  # A cara do sistema (o que o usuário vê)
│       ├── pages/            # Rotas das páginas web (links)
│       ├── static/           # Arquivos de design (CSS, JS, imagens)
│       └── templates/        # Arquivos de página HTML (Jinja2)
├── docs/                     # Documentações do sistema, manuais e planos de melhorias
├── migrations/               # Histórico de alterações estruturais do banco de dados
├── scripts/                  # Scripts utilitários e de manutenção (seeds, backups)
└── tests/                    # Testes automatizados para garantir que nada quebre
```

---

## 4. Ideias de Implementações Futuras (Onde Expandir)

Caso o sistema precise ser continuado ou aprimorado no futuro, as ideias já especificadas e estruturadas nas pastas de desenvolvimento são:

1.  **Consulta Rápida ao Manual FIM (Fault Isolation Manual):**
    *   **Ideia:** Integrar a lista de mensagens de falha do avião (arquivo `fim.json` e os PDFs manuais da pasta `docs/fim/`) na tela de registro de panes. Ao digitar uma mensagem de falha, o sistema sugerirá e abrirá automaticamente o PDF técnico do procedimento de correção correto para o mecânico.
2.  **Notificações Automáticas no WhatsApp:**
    *   **Ideia:** Enviar alertas diretamente para o celular dos inspetores quando uma tarefa precisar de validação, ou avisar o encarregado quando uma aeronave tiver seu status alterado para indisponível devido a uma pane grave.
3.  **Carregamento de Inventário via Excel (XLSX):**
    *   **Ideia:** Permitir que o administrador atualize ou importe centenas de equipamentos físicos de uma vez carregando uma planilha formatada, em vez de cadastrar item por item na tela.
4.  **Interface Otimizada para Celular (Mobile / PWA):**
    *   **Ideia:** Melhorar e otimizar os botões e visualizações da tela para que os mecânicos no pátio de voo consigam tirar fotos de panes e registrá-las diretamente usando celulares ou tablets de serviço.
5.  **Lista de Afazeres (ToDo List) Integrada:**
    *   **Ideia:** Um painel de tarefas de rotina menores do hangar que não geram necessariamente ordens de serviço, mas ajudam a organizar a divisão de faxinas, serviços de escala e pendências administrativas diárias do efetivo.

---

### Dica de Ouro para o Futuro
Toda vez que você realizar alterações na estrutura do banco de dados, utilize a ferramenta **Alembic** para gerar as migrações automáticas:
```bash
.venv/Scripts/alembic revision --autogenerate -m "sua_descricao"
.venv/Scripts/alembic upgrade head
```
E não se esqueça de rodar a suíte completa de testes para garantir que tudo continue funcionando sem problemas:
```bash
.venv/Scripts/pytest
```
