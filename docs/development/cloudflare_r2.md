# Integração Cloudflare R2 Storage

Este documento descreve a arquitetura e o procedimento de configuração do **Cloudflare R2** no SAA29, utilizado para persistência do banco SQLite e armazenamento seguro de anexos.

## 1. Objetivos

- **Persistência do DB:** Garantir que o arquivo `saa29_local.db` sobreviva a novos deploys e reinicializações do container no Railway.
- **Armazenamento de Arquivos:** Migrar o armazenamento de anexos da pasta local `/uploads` para um Bucket R2 (S3-Compatible).
- **Escalabilidade e Custo:** Utilizar o plano gratuito do R2 (Free Tier: 10GB e 0 egress fee).

## 2. Configuração do Cloudflare

### Bucket
- **Nome:** `saa29-storage`
- **Tipo:** Privado (sem acesso público)

### API Token
- **Tipo:** Account API Token
- **Permissão:** `Object Read & Write`
- **Escopo:** Bucket específico `saa29-storage`

### Credenciais Necessárias

| Variável | Descrição |
| :--- | :--- |
| `R2_ACCOUNT_ID` | ID da conta Cloudflare |
| `R2_ACCESS_KEY_ID` | Access Key gerada no painel R2 |
| `R2_SECRET_ACCESS_KEY` | Secret Key gerada no painel R2 |
| `R2_ENDPOINT` | `https://<account_id>.r2.cloudflarestorage.com` |
| `R2_BUCKET_NAME` | `saa29-storage` |
| `STORAGE_BACKEND` | `r2` (ou `local` para desenvolvimento sem R2) |

## 3. Arquitetura

### `app/core/storage.py`
Implementa a abstração de storage com duas implementações:
- **`LocalStorageService`:** Salva arquivos na pasta `uploads/` (desenvolvimento).
- **`R2StorageService`:** Salva arquivos diretamente no Cloudflare R2 via `boto3` (produção). Utiliza pre-signed URLs com expiração de 60 minutos para acesso seguro.

### `scripts/r2_manager.py`
Script de CLI para gerenciar o ciclo de vida do banco SQLite:
- `python scripts/r2_manager.py backup` – Envia o arquivo `.db` atual para o R2.
- `python scripts/r2_manager.py restore` – Baixa o último backup do R2 (executado automaticamente no boot do container).

### `scripts/start.sh`
Fluxo de inicialização do container em produção:
1. Restaurar backup do DB do R2 (se `R2_BUCKET_NAME` estiver definido).
2. Rodar migrações (`alembic upgrade head`).
3. Rodar bootstrap (`scripts/init_db.py`).
4. Iniciar o servidor Gunicorn.

## 4. Configuração no Railway

Adicionar as seguintes variáveis no painel **Variables** do Railway:

```text
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=<seu_account_id>
R2_ACCESS_KEY_ID=<sua_access_key>
R2_SECRET_ACCESS_KEY=<sua_secret_key>
R2_ENDPOINT=https://<seu_account_id>.r2.cloudflarestorage.com
R2_BUCKET_NAME=saa29-storage
```

## 5. Segurança e Boas Práticas

- **Bucket Privado:** O bucket R2 não tem acesso público. Todo acesso é mediado pelo backend.
- **Pre-signed URLs:** Arquivos de panes (imagens/PDFs) são acessados via links que expiram em 60 minutos.
- **Egress Free:** O Cloudflare não cobra transferência de saída, reduzindo custos operacionais.
- **Credenciais:** Nunca versionar as chaves no Git. Usar `.env` local e variáveis de ambiente no Railway.

## 6. Status de Implementação

- [x] Adicionar `boto3` ao `requirements.txt`.
- [x] Atualizar `app/config.py` e `.env.example` com as variáveis R2.
- [x] Criar `app/core/storage.py` com `LocalStorageService` e `R2StorageService`.
- [x] Criar `scripts/r2_manager.py` com funções `backup_db` e `restore_db`.
- [x] Integrar `r2_manager.py` no `scripts/start.sh`.
- [x] Alterar `app/panes/service.py` para usar o `StorageService`.
- [x] Implementar geração de pre-signed URLs.
- [x] Criar bucket `saa29-storage` no Cloudflare.
- [x] Gerar credenciais R2 (Account API Token com `Object Read & Write`).
- [x] Validar conexão e backup local com `python scripts/r2_manager.py backup`.
- [x] Configurar variáveis R2 no Railway.
- [x] Deploy realizado com integração R2 ativa.
