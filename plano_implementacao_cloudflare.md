# Plano de Implementação: Cloudflare R2 Storage

Este documento detalha a estratégia de integração do **Cloudflare R2** ao projeto SAA29 para resolver a persistência do banco de dados SQLite e o armazenamento seguro de anexos.

## 1. Objetivos
- **Persistência do DB:** Garantir que o arquivo `saa29.db` sobreviva a novos deploys e reinicializações do container no Railway.
- **Armazenamento de Arquivos:** Migrar o armazenamento de anexos da pasta local `/uploads` para um Bucket R2 (S3-Compatible).
- **Escalabilidade e Custo:** Utilizar o plano gratuito do R2 (Free Tier: 10GB e 0 egress fee).

## 2. Requisitos Prévios (Setup Cloudflare)
Antes de iniciar o código, os seguintes itens devem ser configurados no painel da Cloudflare:
1.  **Criar Bucket:** Nome sugerido `saa29-storage`.
2.  **R2 API Token:** Criar um token com permissão de `Edit` (Leitura/Escrita) no bucket específico.
3.  **Credenciais:** Obter os seguintes dados:
    - `R2_ACCOUNT_ID` (Id da conta Cloudflare).
    - `R2_ACCESS_KEY_ID`.
    - `R2_SECRET_ACCESS_KEY`.
    - `R2_ENDPOINT` (Ex: `https://<account_id>.r2.cloudflarestorage.com`).
    - `R2_BUCKET_NAME`.

## 3. Mudanças Arquiteturais

### A. Camada de Configuração (`app/config.py`)
- Adição das novas variáveis de ambiente.
- Configuração de flags para alternar entre `local` e `r2` (opcional para testes).

### B. Camada de Serviço de Storage (`app/core/storage.py`)
- Implementação de uma interface abstrata para operações de arquivo (`upload`, `get_url`, `delete`).
- Criação do `R2StorageService` utilizando a biblioteca `boto3`.

### C. Ciclo de Vida do Banco de Dados (`scripts/r2_manager.py`)
- **Download (Restore):** No início do container, baixar o último backup do `.db` se ele existir no R2.
- **Upload (Backup):** Script periódico ou disparado no shutdown para enviar o `.db` atual para o R2.

### D. Atualização do Script de Inicialização (`scripts/start.sh`)
- Integração do `r2_manager.py` no fluxo de boot:
    1.  Tentar baixar DB do R2.
    2.  Rodar migrações.
    3.  Rodar Bootstrap (`init_db.py`).
    4.  Iniciar App.

## 4. Cronograma de Implementação

### Fase 1: Fundação (Infra)
- [x] Adicionar `boto3` ao `requirements.txt`.
- [x] Atualizar `app/config.py` e `.env.example`.
- [x] Criar classe base de Storage.

### Fase 2: Persistência do Banco (SQLite Backup)
- [x] Criar `scripts/r2_manager.py` com funções `backup_db` e `restore_db`.
- [x] Integrar no `scripts/start.sh`.
- [x] Validar lógica de inicialização com R2 (Testado localmente com scripts de fallback).

### Fase 3: Migração de Anexos
- [x] Alterar `app/panes/service.py` para usar o novo serviço de Storage.
- [x] Implementar geração de URLs temporárias (Pre-signed URLs) para visualização segura.
- [x] Remover dependência da pasta física `/uploads` em produção.

### Fase 4: Próximos Passos (Finalização e Deploy)
- [ ] **Configurar Cloudflare:** Criar o bucket `saa29-storage` e gerar as credenciais (Access e Secret Keys).
- [ ] **Testar Conexão R2 Localmente:** Configurar as credenciais R2 no `.env` local e testar `python scripts/r2_manager.py backup`.
- [ ] **Configurar Railway:** Definir todas as variáveis R2 no painel do Railway (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET_NAME`, `STORAGE_BACKEND=r2`).
- [ ] **Implantar e Validar:** Executar o deploy remoto (git push no Railway app) e validar a funcionalidade do serviço de Anexos em nuvem.

## 5. Segurança e Boas Práticas
- **Bucket Privado:** O bucket R2 não terá acesso público. Todo acesso será mediado pelo backend.
- **Pre-signed URLs:** Arquivos de panes (imagens/pdfs) serão acessados via links que expiram em 30 minutos.
- **Egress Free:** Aproveitar que a Cloudflare não cobra transferência de saída para reduzir custos operacionais.

## 6. Verificação e Testes
- Testar falha de conexão com R2 (fallback para local em dev).
- Validar integridade do SQLite após processo de download/upload.
- Verificar se o `Content-Type` dos anexos está sendo preservado no R2.
