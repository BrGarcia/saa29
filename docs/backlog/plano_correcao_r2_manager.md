# Plano de Correção: Vulnerabilidades e Integridade no `r2_manager.py`

Este documento apresenta o plano detalhado para corrigir as vulnerabilidades e fragilidades de integridade identificadas no script de gerenciamento do Cloudflare R2 (`scripts/maintenance/r2_manager.py`).

---

## 1. Vulnerabilidades e Riscos Mapeados

### Falha 1: Risco Crítico de Perda de Dados (Sobrescrita do Banco)
* **Cenário**: O método `restore_db()` captura qualquer erro de conexão ou credenciais (`Exception`) de forma genérica. Ele imprime o erro e segue em frente, assumindo que o banco de dados não existe no bucket R2.
* **Impacto**: O container inicializa com um banco SQLite vazio local. Logo em seguida, o script de inicialização executa o comando `backup`, enviando esse banco vazio por cima do backup real no R2, destruindo o histórico operacional.
* **Correção**: Capturar especificamente a exceção `ClientError` do `botocore.exceptions`. Se o erro for `404` (arquivo não existe no R2), prosseguir normalmente para iniciar um novo banco. Caso seja qualquer outro erro (403, 401, erro de rede/timeout), abortar imediatamente a execução com `sys.exit(1)`.

### Falha 2: Concorrência e Risco de Corrupção de Banco (Não-Atomicidade)
* **Cenário**: O download é feito diretamente por cima do arquivo ativo `db_path` da aplicação.
* **Impacto**: Se o script for chamado enquanto a aplicação estiver aberta e executando conexões (ex: contêiner rodando ou execução simultânea de rotinas), a sobrescrita imediata quebrará a integridade do SQLite, corrompendo o banco local (`database disk image is malformed`).
* **Correção**: Baixar a imagem do banco de dados para um arquivo temporário (`db_path.tmp`) e, após a conclusão total sem erros, substituí-lo no disco utilizando uma operação atômica (`os.replace`).

### Falha 3: Vazamento de Credenciais nos Logs (Security Disclosure)
* **Cenário**: O script exibe logs crus de exceções do `boto3`.
* **Impacto**: Exceções de rede ou autenticação do SDK AWS podem imprimir detalhes de requisição e respostas HTTP contendo chaves, tokens de sessão ou hashes de autorização que serão arquivados nos logs persistentes de produção (como o Railway logs).
* **Correção**: Exibir mensagens sanitizadas e controladas em caso de exceções nas operações com R2, ocultando o objeto de erro cru do console se necessário.

### Falha 4: Parsing Incompleto da DATABASE_URL
* **Cenário**: O parsing da URL do SQLite é feito via `split("///")[-1]`.
* **Impacto**: Se a string contiver query parameters (ex: `sqlite+aiosqlite:///./data.db?timeout=30&cache=shared`), o script tentará criar um arquivo com caracteres de interrogação e parâmetros no nome no sistema de arquivos.
* **Correção**: Empregar a biblioteca padrão `urllib.parse` para analisar a URI de conexão de maneira robusta.

---

## 2. Proposta de Modificações no Código

Abaixo está o esboço das alterações recomendadas para o arquivo `scripts/maintenance/r2_manager.py`:

```python
import os
import sys
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from dotenv import load_dotenv

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
    # Extração robusta do caminho do banco usando urllib
    parsed = urlparse(DATABASE_URL)
    # Remove as barras iniciais do path se houverem
    path = parsed.path.lstrip("/")
    # Se o path for vazio ou relativo (como ./saa29_local.db)
    if not path and parsed.netloc:
        path = parsed.netloc.lstrip("/")
    # Garante a remoção de possíveis query parameters
    return path.split("?")[0]

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
    
    try:
        s3.upload_file(db_path, R2_BUCKET_NAME, key)
        print("Backup efetuado com sucesso!")
    except ClientError as e:
        print("Erro ao fazer backup para R2: Acesso negado ou credenciais inválidas.")
        sys.exit(1)
    except Exception:
        print("Erro inesperado ao realizar backup para o R2.")
        sys.exit(1)

def restore_db():
    if not is_sqlite():
        print("Restore R2 abortado: Banco não é SQLite.")
        return
        
    db_path = get_db_path()
    s3 = get_s3_client()
    key = "database/saa29_local.db"
    
    print("Tentando baixar banco de dados do R2...")
    tmp_path = f"{db_path}.tmp"
    
    try:
        # Tenta verificar se o objeto existe antes de transferir
        s3.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        
        # Download seguro para arquivo temporário
        s3.download_file(R2_BUCKET_NAME, key, tmp_path)
        
        # Substituição atômica de arquivos para evitar corrupção
        if os.path.exists(db_path):
            backup_local = f"{db_path}.bak"
            if os.path.exists(backup_local):
                os.remove(backup_local)
            os.rename(db_path, backup_local)
            
        os.rename(tmp_path, db_path)
        print("Restore efetuado com sucesso. Banco de dados sincronizado.")
        
    except ClientError as e:
        # Se for erro 404 (Objeto não existe), inicia um banco novo
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404" or "Not Found" in str(e):
            print("Banco de dados não encontrado no R2. Iniciando com banco limpo local.")
            # Remove arquivo temporário se sobrou algum resíduo
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        else:
            # Outro erro do R2 (ex: Credenciais inválidas 403)
            print(f"Erro crítico ao acessar o R2: Acesso não autorizado ou rede inoperante.")
            sys.exit(1)
    except Exception:
        print("Erro de comunicação inesperado com o serviço de armazenamento R2.")
        sys.exit(1)
```

---

## 3. Plano de Testes de Validação

1. **Teste de Credenciais Inválidas**:
   * Alterar temporariamente o valor de `R2_ACCESS_KEY_ID` no `.env` para dados aleatórios.
   * Rodar `python scripts/maintenance/r2_manager.py restore`.
   * **Resultado Esperado**: O script deve acusar o erro e falhar com código de saída `1` (`sys.exit(1)`), em vez de criar um banco SQLite limpo local e prosseguir.
2. **Teste de Arquivo Inexistente**:
   * Alterar a variável `R2_BUCKET_NAME` para um bucket vazio.
   * Rodar `python scripts/maintenance/r2_manager.py restore`.
   * **Resultado Esperado**: O script deve identificar o erro `404` (não encontrado) e prosseguir sem falhar, indicando que iniciará um banco limpo local.
3. **Teste de Download Atômico**:
   * Rodar `restore` simulado e forçar o cancelamento (Ctrl+C) ou erro no meio da transferência.
   * **Resultado Esperado**: O arquivo original de banco (`saa29_local.db`) deve permanecer intacto, e apenas o arquivo temporário `.tmp` deve ser limpo/ignorado.
