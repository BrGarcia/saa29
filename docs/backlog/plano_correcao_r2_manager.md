# Plano de Correção: Vulnerabilidades e Integridade no `r2_manager.py` (Revisado)

Este documento apresenta o plano detalhado e revisado para corrigir as vulnerabilidades e fragilidades de integridade identificadas no script de gerenciamento do Cloudflare R2 (`scripts/maintenance/r2_manager.py`). 

Esta versão incorpora as análises de risco e melhorias sugeridas nos pareceres técnicos **Codex** e **Opus** (`parecer_codex.md` e `parecer_opus.md`).

---

## 1. Vulnerabilidades e Riscos Mapeados

### Falha 1: Risco Crítico de Perda de Dados (Sobrescrita do Banco)
* **Cenário**: O método `restore_db()` captura qualquer erro de conexão ou credenciais (`Exception`) de forma genérica. Ele imprime o erro e segue em frente, assumindo que o banco de dados não existe no R2.
* **Impacto**: O container inicializa com um banco SQLite vazio local. Logo em seguida, o script de inicialização executa o comando `backup`, enviando esse banco vazio por cima do backup real no R2, destruindo o histórico operacional.
* **Correção**: Capturar especificamente a exceção `ClientError` do `botocore.exceptions`. Se o erro for `404` (arquivo não existe no R2), prosseguir normalmente para iniciar um novo banco. Caso seja qualquer outro erro (403, 401, erro de rede/timeout), abortar imediatamente a execução com `sys.exit(1)`.

### Falha 2: Concorrência e Risco de Corrupção de Banco (Não-Atomicidade)
* **Cenário**: O download é feito diretamente por cima do arquivo ativo `db_path` da aplicação.
* **Impacto**: Se o script for chamado manualmente enquanto a aplicação estiver aberta e executando conexões, a sobrescrita imediata quebrará a integridade do SQLite, corrompendo o banco local (`database disk image is malformed`).
* **Correção**: 
  1. Realizar o download para um arquivo temporário no mesmo diretório do banco (`.r2tmp`) para garantir atomicidade sob o mesmo sistema de arquivos.
  2. Executar validação de integridade local do SQLite (`PRAGMA quick_check`) antes de fazer a substituição.
  3. Substituir o banco ativo usando a chamada de sistema atômica `os.replace()` em vez de múltiplos renomes, evitando janelas de falha no meio da substituição.
  4. Garantir a limpeza de resíduos temporários em qualquer fluxo de exceção.

### Falha 3: Inconsistência no Backup (Modo WAL e Escrita Ativa)
* **Cenário**: A aplicação utiliza o modo `journal_mode=WAL`. Fazer upload direto do arquivo `.db` ativo pode ignorar commits que ainda estão nos arquivos temporários `-wal` e `-shm`, resultando em perda de dados recentes ou inconsistência no restore.
* **Impacto**: Perda de integridade ou dados salvos logo antes do backup em ambiente concorrente.
* **Correção**: Gerar um snapshot consistente do banco SQLite utilizando a API nativa de backup do Python (`sqlite3.Connection.backup()`) com execução de checkpoint prévio (`PRAGMA wal_checkpoint(TRUNCATE)`). O upload é feito a partir deste snapshot consistente e limpo, evitando fazer o upload direto do arquivo ativo em escrita.

### Falha 4: Fragilidade no Parsing da DATABASE_URL
* **Cenário**: O parsing da URL do SQLite é feito via `split("///")[-1]`. Se o plano original fizesse `parsed.path.lstrip("/")`, ele quebraria caminhos absolutos do container (como `/app/data/saa29.db`), transformando-os em relativos.
* **Impacto**: Riscos de salvar/ler o banco de dados local no caminho errado em produção.
* **Correção**: Empregar a biblioteca padrão `urllib.parse` para analisar o path preservando caminhos absolutos, tratando especificamente a notação relativa `/.` das URLs SQLite clássicas (ex: `sqlite+aiosqlite:///./saa29_local.db`).

### Falha 5: Redundância de Scripts de Backup
* **Cenário**: Existe o script legado `scripts/backup_r2.py` com comportamento redundante e vulnerável (captura genérica de erros e caminhos diferentes).
* **Impacto**: Confusão de manutenção em ambientes produtivos.
* **Correção**: Remover o script `scripts/backup_r2.py` ou substituí-lo por um import/redirecionamento direto para a lógica contida em `scripts/maintenance/r2_manager.py`.

---

## 2. Código Proposto (`scripts/maintenance/r2_manager.py`)

Abaixo está o código revisado e seguro a ser aplicado ao script de manutenção:

```python
#!/usr/bin/env python
"""
scripts/r2_manager.py
Script responsável por realizar backup e restore do banco de dados SQLite
usando o Cloudflare R2 com garantia de integridade, atomicidade e consistência.
"""
import os
import sys
import boto3
import sqlite3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from dotenv import load_dotenv

# Carrega as variáveis do .env (se existir)
load_dotenv()

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db")

def is_sqlite():
    return "sqlite" in DATABASE_URL.lower()

def get_db_path():
    parsed = urlparse(DATABASE_URL)
    path = parsed.path
    
    # Tratamento para URLs do SQLite relativas clássicas contendo '/.' (ex: ///./db)
    if path.startswith("/."):
        return path[1:]
    return path

def get_s3_client():
    if not all([R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
        print("Erro: Variáveis de ambiente R2 incompletas.")
        sys.exit(1)
        
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto"
    )

def backup_db():
    if not is_sqlite():
        print("Backup R2 abortado: Banco não é SQLite.")
        return
        
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Erro: Arquivo do banco {db_path} não encontrado para backup.")
        return

    print("Iniciando backup para o R2...")
    s3 = get_s3_client()
    key = "database/saa29_local.db"
    
    backup_tmp = f"{db_path}.backup.r2tmp"
    
    try:
        # Gera snapshot consistente usando a API de backup nativa do SQLite
        src_conn = sqlite3.connect(db_path)
        # Executa checkpoint para forçar sincronização do WAL com o banco de dados principal
        src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        
        dst_conn = sqlite3.connect(backup_tmp)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        # Envia o snapshot consistente
        s3.upload_file(backup_tmp, R2_BUCKET_NAME, key)
        print("Backup efetuado com sucesso!")
    except ClientError as e:
        print("Erro ao fazer backup para R2: Acesso negado ou credenciais inválidas.")
        sys.exit(1)
    except Exception as e:
        print("Erro inesperado ao realizar backup para o R2.")
        sys.exit(1)
    finally:
        # Garante a limpeza do snapshot temporário gerado no disco
        if os.path.exists(backup_tmp):
            os.remove(backup_tmp)

def restore_db():
    if not is_sqlite():
        print("Restore R2 abortado: Banco não é SQLite.")
        return
        
    db_path = get_db_path()
    s3 = get_s3_client()
    key = "database/saa29_local.db"
    
    print("Tentando baixar banco de dados do R2...")
    tmp_path = f"{db_path}.r2tmp"
    
    # Garante que o diretório pai existe
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    try:
        # Tenta verificar se o objeto existe antes de transferir
        s3.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        
        # Download para temporário no mesmo diretório do banco
        s3.download_file(R2_BUCKET_NAME, key, tmp_path)
        
        # Validação de integridade física básica do SQLite baixado
        try:
            conn = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check;")
            result = cursor.fetchone()
            conn.close()
            if not result or result[0].lower() != "ok":
                raise ValueError(f"Falha no quick_check: {result}")
        except Exception as val_err:
            print(f"Erro de integridade no banco baixado do R2: {val_err}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            sys.exit(1)
            
        # Substituição atômica no nível do SO
        os.replace(tmp_path, db_path)
        print("Restore efetuado com sucesso. Banco de dados sincronizado.")
        
    except ClientError as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        # Se for erro 404 (Objeto não existe no bucket), inicia um banco novo
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404" or "Not Found" in str(e):
            print("Banco de dados não encontrado no R2. Iniciando com banco limpo local.")
        else:
            print("Erro crítico ao acessar o R2: Acesso não autorizado ou rede inoperante.")
            sys.exit(1)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print("Erro de comunicação inesperado com o serviço de armazenamento R2.")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python r2_manager.py [backup|restore]")
        sys.exit(1)
        
    command = sys.argv[1].lower()
    if command == "backup":
        backup_db()
    elif command == "restore":
        restore_db()
    else:
        print(f"Comando desconhecido: {command}")
```

---

## 3. Plano de Testes de Validação

1. **Teste de Credenciais Inválidas (Falha de Comunicação)**:
   * **Como testar**: Alterar temporariamente o valor de `R2_ACCESS_KEY_ID` no `.env` local para dados aleatórios.
   * **Execução**: `python scripts/maintenance/r2_manager.py restore`.
   * **Resultado Esperado**: O script deve printar o erro de acesso não autorizado e terminar com código de saída `1` (`sys.exit(1)`), garantindo que o boot da aplicação falhe em vez de iniciar um banco limpo local.

2. **Teste de Arquivo Inexistente no R2 (Novo Deploy)**:
   * **Como testar**: Acessar o R2 com credenciais corretas, mas configurar a variável `DATABASE_URL` para apontar para um arquivo de teste inexistente no R2.
   * **Execução**: `python scripts/maintenance/r2_manager.py restore`.
   * **Resultado Esperado**: O script deve identificar o erro `404` (não encontrado) e prosseguir sem falhar, imprimindo que iniciará um banco limpo local (exit code `0`).

3. **Teste de Download Atômico e Cancelamento**:
   * **Como testar**: Iniciar o `restore` e forçar o encerramento abrupto (Ctrl+C) durante a transferência do arquivo.
   * **Resultado Esperado**: O arquivo original de banco em `db_path` deve permanecer intacto, e o arquivo temporário `.r2tmp` gerado pela metade deve ser limpo/removido na tratativa do sinal ou ao rodar novamente.

4. **Teste de Backup Concorrente (Modo WAL)**:
   * **Como testar**: Rodar uma escrita concorrente em loop no banco de dados e chamar `python scripts/maintenance/r2_manager.py backup`.
   * **Resultado Esperado**: O arquivo carregado no R2 deve conter todas as transações devidamente aplicadas sem corromper ou bloquear a aplicação em andamento.
