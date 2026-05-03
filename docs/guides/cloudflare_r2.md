# Integracao Cloudflare R2

Este documento descreve o uso atual do Cloudflare R2 no SAA29.

## 1. O que o R2 cobre hoje

- armazenamento opcional de anexos;
- backup e restore do banco SQLite;
- URLs pre-assinadas para download de arquivos.

## 2. Componentes Envolvidos

### `app/shared/core/storage.py`

Implementa a abstracao de storage com duas opcoes:

- `LocalStorageService`
- `R2StorageService`

### `scripts/maintenance/r2_manager.py`

Gerencia backup e restore do banco SQLite com o bucket R2.

Comandos:

```bash
python scripts/maintenance/r2_manager.py backup
python scripts/maintenance/r2_manager.py restore
```

### `app/bootstrap/main.py`

Quando `STORAGE_BACKEND=r2` e `R2_BUCKET_NAME` estao configurados, o bootstrap pode acionar o fluxo de backup orientado a eventos no shutdown.

## 3. Variaveis de Ambiente

Configure no `.env`:

```env
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=<account_id>
R2_ACCESS_KEY_ID=<access_key_id>
R2_SECRET_ACCESS_KEY=<secret_access_key>
R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
R2_BUCKET_NAME=saa29-storage
```

Observacoes:

- o nome usado no codigo e `R2_ENDPOINT`, nao `R2_ENDPOINT_URL`;
- se `STORAGE_BACKEND=local`, o sistema salva arquivos na pasta definida em `UPLOAD_DIR`.

## 4. Comportamento do Storage

### Local

- grava arquivos em disco;
- usa a pasta configurada em `UPLOAD_DIR`;
- retorna caminho absoluto para o router ler o arquivo depois.

### R2

- grava objetos no bucket em `anexos/<uuid>.<ext>`;
- gera URL pre-assinada valida por 60 minutos;
- usa `boto3` em thread separada para nao bloquear o event loop.

## 5. Regras de Arquivo

O storage valida:

- extensoes permitidas: `.jpg`, `.jpeg`, `.png`, `.pdf`, `.doc`, `.docx`;
- nomes com `..`, `/` ou `\` sao rejeitados por seguranca.

## 6. Backup do Banco

O arquivo `scripts/maintenance/r2_manager.py` trabalha com o banco SQLite apontado por `DATABASE_URL`.

Fluxo:

1. `backup` envia o arquivo SQLite para `database/saa29_local.db` no bucket.
2. `restore` baixa o mesmo objeto, se existir.

Observacao:

- esse fluxo e voltado para SQLite. Se voce migrar para PostgreSQL, nao use esse script como backup principal do banco.

## 7. Uso Recomendado

- desenvolvimento local: `STORAGE_BACKEND=local`;
- ambiente com anexos remotos: `STORAGE_BACKEND=r2`;
- banco SQLite em volume: combine R2 com persistencia local do arquivo do banco;
- producao com Postgres: revise a estrategia de backup separadamente.

## 8. Checklist de Implantacao

- bucket privado criado;
- credenciais R2 configuradas;
- `STORAGE_BACKEND=r2` definido;
- `UPLOAD_DIR` valido;
- restore testado com um arquivo de banco existente;
- upload e download de anexo validados na aplicacao.
