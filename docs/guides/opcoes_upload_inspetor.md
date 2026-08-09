# Guia — Opções de Upload Autônomo de Publicações (Role INSPETOR)

> Este guia documenta as alternativas de arquitetura para permitir que usuários com a role **`INSPETOR`** (perfil operacional/negócio, sem conhecimento técnico ou de linha de comando) realizem o envio e a atualização do acervo de publicações diretamente pela interface Web do SAA29, preservando a stack atual do projeto.

---

## 1. Contexto e Desafio Técnico

* **Usuário Alvo**: Inspetor / Usuário Operacional.
* **Necessidade**: Atualizar o acervo de manuais (`.zip` ou pastas) de forma autônoma e visual na tela `/configuracoes`.
* **Desafio**: O acervo de publicações pode possuir tamanhos elevados (de centenas de MBs até ~3 GB). O envio HTTP tradicional via formulário simples em uma única requisição causa estouro de memória (*Out Of Memory - OOM Kill*) ou *timeout* de requisição (30s do Gunicorn) no servidor FastAPI/VPS.
* **Premissa Fundamental**: Manter 100% da stack técnica já estabelecida no projeto (FastAPI, Vanilla HTML/CSS/JS, Cloudflare R2, Python, SQLite/PostgreSQL, autenticação `AdminRequired`/`CurrentUser`).

---

## 2. Opções Viáveis de Arquitetura

### 📌 Opção 1 (Recomendada): Upload Direto do Navegador para Cloudflare R2 (Presigned URL) + Job Assíncrono

#### **Como Funciona:**
1. No menu `/configuracoes` (no Card *Publicações*), o Inspetor clica no botão **"Carregar Nova Edição (.zip)"** e seleciona o arquivo.
2. O JavaScript do navegador faz uma requisição leve à API FastAPI (`POST /publicacoes/api/edicoes/solicitar-upload`).
3. A FastAPI gera uma **URL Pré-Assinada (Presigned Upload URL)** temporária do Cloudflare R2 (usando o SDK `boto3`) e retorna ao navegador.
4. O navegador realiza o upload do arquivo `.zip` **diretamente para o Cloudflare R2** via requisição HTTP `PUT` em partes, exibindo uma barra de progresso em tempo real para o Inspetor.
5. Assim que o upload para o R2 termina, o navegador avisa a FastAPI (`POST /publicacoes/api/edicoes/processar-upload`).
6. A FastAPI dispara uma tarefa em segundo plano (`BackgroundTask` nativa do FastAPI) que:
   - Valida a segurança do `.zip` (proteção contra *Zip-Slip* e descompactação isolada).
   - Executa a rotina de inventário, diff por hash, extração de texto e geração do `catalog.<edicao>.db` (mesma lógica do script `publicar.py`).
   - Registra a edição no banco com o status `AGUARDANDO_ATIVACAO`.
7. O Inspetor acompanha o status na tela em tempo real (`Processando acervo... [ 75% ]`). Ao finalizar, o relatório de diff é exibido e o botão **`[ ATIVAR EDIÇÃO ]`** fica disponível.

#### **Prós:**
* ✅ **Experiência 100% Web e Amigável**: O Inspetor apenas arrasta e solta o arquivo `.zip` na interface web.
* ✅ **Bypassa limites da VPS**: O arquivo de 3 GB não passa pela memória RAM nem pelo processo HTTP da VPS; vai direto do navegador para o storage em nuvem R2.
* ✅ **Preserva 100% a Stack Atual**: Utiliza recursos nativos da stack (FastAPI `BackgroundTasks`, SDK R2 `boto3`, Vanilla JS no front-end).
* ✅ **Segurança**: URL pré-assinada de curta duração com validação prévia de autorização (`INSPETOR`/`ADMIN`).

#### **Contras:**
* ⚠️ Exige configurar a regra de CORS no bucket do Cloudflare R2 para permitir requisições diretas do domínio da aplicação web.

---

### 📌 Opção 2: Upload Fragmentado (Chunked / Resumable Upload em 5MB) para Disco da VPS + Job Assíncrono

#### **Como Funciona:**
1. O Inspetor seleciona o arquivo `.zip` na interface web.
2. O JavaScript do front-end divide o arquivo de 3 GB em pequenos pedaços (*chunks*) de 5 MB cada.
3. O navegador envia cada chunk sequencialmente para a rota FastAPI (`POST /publicacoes/api/edicoes/upload-chunk`).
4. Cada pedaço de 5 MB é muito leve, não sobrecarrega a RAM da VPS e respeita o timeout de 30s do Gunicorn.
5. À medida que os chunks chegam, a FastAPI os grava em um diretório temporário (`var/publicacoes/uploads_temp/`).
6. Ao receber o último chunk, o servidor une os pedaços, inicia o job de processamento em segundo plano (inventário, indexação e envio ao R2) e libera o botão de ativação na UI.

#### **Prós:**
* ✅ **100% Web e Autônomo**: Interface amigável com barra de progresso no navegador.
* ✅ **Resiliente a Quedas de Conexão**: Permite pausar e retomar o upload de onde parou em caso de oscilação na internet.
* ✅ **Sem dependência de CORS no R2**: Todo o envio ocorre diretamente entre o navegador do usuário e a VPS.

#### **Contras:**
* ⚠️ Requer que o disco da VPS tenha espaço temporário suficiente para montar o arquivo `.zip` antes do processamento (~3 GB a 6 GB livres).
* ⚠️ Requer implementar a lógica de controle e montagem de chunks no backend FastAPI.

---

### 📌 Opção 3: Pasta de Entrada / Monitoramento Automatizado (Dropzone / Compartilhamento de Rede)

#### **Como Funciona:**
1. Configura-se uma pasta de monitoramento no servidor (ex: `var/publicacoes/dropzone/`) acessível como pasta compartilhada na rede interna ou via cliente SFTP amigável.
2. O Inspetor copia o arquivo `.zip` (ou a pasta descompactada) para esse diretório usando o próprio Windows Explorer ("Copiar e Colar").
3. Um serviço em segundo plano na FastAPI verifica a pasta periodicamente.
4. Ao encontrar um novo arquivo, o SAA29 inicia automaticamente a validação, extração, indexação e upload para o R2.
5. Ao concluir, a edição fica disponível na tela `/configuracoes` para o Inspetor revisar o relatório e clicar em **`[ ATIVAR ]`**.

#### **Prós:**
* ✅ **Familiar para o usuário**: O Inspetor usa apenas o Windows Explorer sem precisar aprender novas ferramentas.
* ✅ **Zero carga de upload HTTP no navegador**: Não sofre com limitações do browser.
* ✅ **Código web simples**: A interface web só precisa exibir a lista de edições prontas para ativação.

#### **Contras:**
* ⚠️ Exige suporte de infraestrutura de TI para mapear a pasta de rede na máquina dos inspetores.
* ⚠️ Não é um fluxo 100% contido dentro da aplicação web.

---

## 3. Tabela Comparativa de Opções

| Opção | Usabilidade do Inspetor | Carga na VPS / Memória | Preserva Stack Atual? | Complexidade de Código |
|---|---|---|---|---|
| **Opção 1: Presigned R2 (Recomendada)** | 🟢 100% Web (Drag & Drop na UI) | 🟢 Mínima (Upload direto na nuvem) | ✅ Sim (FastAPI + R2 + JS) | Média |
| **Opção 2: Chunked Upload (5MB)** | 🟢 100% Web (Com pausa/retomada) | 🟡 Média (Requer disco temporário) | ✅ Sim (FastAPI + JS) | Média |
| **Opção 3: Dropzone de Rede** | 🟡 Copiar/Colar no Windows Explorer | 🟢 Baixa | ✅ Sim (FastAPI Background) | Baixa |

---

## 4. Conclusão e Recomendação

A **Opção 1 (Presigned URL para o Cloudflare R2 + Job de Segundo Plano na FastAPI)** representa a solução ideal para o projeto SAA29. Ela resolve o desafio do envio de arquivos volumosos para usuários não técnicos com as seguintes vantagens:
1. Elimina completamente comandos de terminal ou acessos SSH para o perfil `INSPETOR`.
2. Mantém 100% da stack existente sem adicionar novas dependências externas.
3. Garante que a VPS permaneça estável e responsiva durante o processo de upload.

---

## 5. Referências

- [envio_publicacoes_zip.md](file:///c:/Users/brgar/Projetos/SAA29/docs/guides/envio_publicacoes_zip.md) — Motivações arquiteturais de limites de upload e fluxo CLI original.
- [operacao_publicacoes.md](file:///c:/Users/brgar/Projetos/SAA29/docs/guides/operacao_publicacoes.md) — Runbook operacional completo do módulo de publicações.
- [opus_plano_de_incorporacao.md](file:///c:/Users/brgar/Projetos/SAA29/docs/backlog/modulo_publicacoes/opus_plano_de_incorporacao.md) — Parecer arquitetural do acervo de publicações (§5.11 e §8.3).
