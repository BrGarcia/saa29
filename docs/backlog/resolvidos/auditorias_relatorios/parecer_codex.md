# Parecer Codex sobre `plano_correcao_r2_manager.md`

Data: 2026-05-23

## Conclusao

As implementacoes propostas sao coerentes na direcao geral e tratam um risco real de producao: falha de restore do R2 sendo confundida com ausencia de backup, seguida de inicializacao local e novo backup para o R2. No fluxo atual de `scripts/start.sh`, isso pode sobrescrever o backup remoto com um banco recem-criado. Portanto, a correcao tem potencial de melhoria significativa para seguranca operacional, integridade e recuperacao de desastre.

O plano, porem, nao deve ser aplicado literalmente como esta. Ele contem ajustes que reduzem risco, mas tambem introduz pelo menos um risco relevante para producao: o parsing proposto para `DATABASE_URL` remove barras iniciais e pode transformar o caminho absoluto `sqlite+aiosqlite:////app/data/saa29.db` em `app/data/saa29.db`, fazendo restore/backup no local errado dentro do container.

Parecer: **aprovado com ressalvas obrigatorias**. Recomendo implementar a correcao, mas com ajustes antes de levar a producao.

## Analise das propostas

### 1. Diferenciar 404 de falha de acesso ao R2

Coerente e altamente recomendavel.

O `restore_db()` atual captura `Exception` de forma generica e continua a execucao para qualquer erro. Como `scripts/start.sh` executa `restore`, depois `alembic upgrade`, depois `init_db` e depois `backup`, uma falha temporaria de rede, credencial invalida, bucket inacessivel ou permissao negada pode ser seguida por criacao/atualizacao de banco local e upload para o R2. Esse e o maior risco do plano e deve ser tratado com prioridade.

Recomendacao:

- capturar `botocore.exceptions.ClientError`;
- permitir continuidade apenas para erro de objeto inexistente, normalmente `404`, `NoSuchKey` ou `NotFound`, conforme retorno do provider S3/R2;
- abortar com exit code diferente de zero para `403`, `401`, `AccessDenied`, erro de credencial, timeout ou falha de rede;
- manter `set -e` em `scripts/start.sh`, pois isso impede que o boot prossiga para migracao/bootstrap/backup quando o restore falha de forma critica.

Impacto esperado: **alto**. Reduz diretamente o risco de perda de dados por sobrescrita do backup remoto.

### 2. Download para arquivo temporario e substituicao atomica

Coerente, mas precisa de refinamento.

Baixar diretamente sobre o arquivo ativo e perigoso se houver interrupcao durante a transferencia. O uso de arquivo temporario melhora bastante a seguranca do restore. Entretanto, o esboco usa `os.rename` e ainda faz backup local removendo `.bak` anterior. Para o objetivo declarado, a operacao mais adequada e `os.replace(tmp_path, db_path)`, que substitui atomicamente no mesmo filesystem.

Recomendacao:

- criar o diretorio de destino antes do download, se necessario;
- baixar para temporario no mesmo diretorio do banco, por exemplo `saa29.db.r2tmp`, para preservar atomicidade no mesmo filesystem;
- apos download completo, validar minimamente o SQLite antes da troca, por exemplo abrir em modo read-only e executar `PRAGMA quick_check`;
- usar `os.replace(tmp_path, db_path)`;
- limpar temporario em caso de erro;
- preservar um backup local versionado apenas se houver politica clara de retencao. Remover sempre o `.bak` anterior reduz a utilidade em incidente.

Impacto esperado: **medio a alto**. Reduz risco de banco parcial/corrompido durante restore.

### 3. Sanitizacao de logs

Coerente e recomendavel, com impacto moderado.

Evitar imprimir excecoes cruas de SDK em logs de producao e uma boa pratica. Mesmo que o boto3 normalmente nao exponha a chave secreta diretamente, logs de excecao podem conter detalhes de endpoint, bucket, payload, request id e mensagens internas que nao precisam ficar persistidas.

Recomendacao:

- imprimir mensagem controlada para o operador;
- se for necessario diagnostico, registrar apenas codigo do erro e request id, sem headers de autorizacao, URL assinada ou credenciais;
- evitar `print(f"... {e}")` para erros de autenticacao, acesso e rede.

Impacto esperado: **medio**. Melhora higiene de logs e reduz exposicao acidental.

### 4. Parsing robusto de `DATABASE_URL`

A intencao e correta, mas o codigo sugerido tem risco de regressao.

O ambiente de producao no `docker-compose.yml` usa:

```text
sqlite+aiosqlite:////app/data/saa29.db
```

Nesse formato, o caminho real e absoluto: `/app/data/saa29.db`. O esboco do plano faz `parsed.path.lstrip("/")`, que transformaria esse caminho em `app/data/saa29.db`. Dentro do container isso apontaria para outro local, provavelmente `/app/app/data/saa29.db` dependendo do working directory, causando restore/backup do arquivo errado.

Recomendacao:

- nao remover barras iniciais de caminhos absolutos;
- usar API de URL do SQLAlchemy quando possivel, por exemplo `sqlalchemy.engine.make_url(settings.database_url).database`;
- se usar `urllib.parse`, preservar caminhos absolutos quando a URL tiver quatro barras;
- remover query string pelo parser, nao por `split("?")`;
- testar explicitamente estes casos:
  - `sqlite+aiosqlite:///./saa29_local.db` -> `./saa29_local.db`;
  - `sqlite+aiosqlite:////app/data/saa29.db` -> `/app/data/saa29.db`;
  - `sqlite+aiosqlite:///./data.db?timeout=30&cache=shared` -> `./data.db`.

Impacto esperado: **medio**, mas com risco de regressao se implementado literalmente.

## Riscos nao cobertos pelo plano

O plano melhora o restore, mas nao resolve por completo a consistencia do backup de SQLite.

A aplicacao habilita `PRAGMA journal_mode=WAL` em `app/bootstrap/database.py`. Fazer upload apenas do arquivo principal `.db` pode nao capturar transacoes que ainda estejam no arquivo `-wal`, dependendo do momento e das conexoes abertas. No boot atual, o backup ocorre antes do Gunicorn iniciar, o que reduz o risco, mas nao elimina a necessidade de uma rotina correta se o script for usado manualmente ou em outro horario.

Recomendacao adicional:

- antes do backup, executar checkpoint do WAL quando o banco existir e estiver acessivel;
- preferir gerar um snapshot consistente usando a API de backup do SQLite para um arquivo temporario e fazer upload desse snapshot, em vez de subir diretamente o arquivo ativo;
- documentar que `r2_manager.py backup` nao deve rodar em paralelo com escrita ativa sem mecanismo de snapshot/lock;
- considerar lock de processo para impedir execucoes concorrentes de restore/backup.

Tambem ha um script legado `scripts/backup_r2.py` com comportamento semelhante de captura generica de excecoes. Se ele ainda for usado em algum ambiente, deve ser corrigido ou removido para evitar duas implementacoes divergentes.

## Parecer de risco para producao

As mudancas propostas, quando ajustadas, oferecem ganho relevante e justificavel de seguranca operacional. O maior beneficio e impedir que falhas de acesso ao R2 sejam tratadas como "backup inexistente", o que hoje pode levar a perda de dados remotos.

Os riscos ao sistema em producao sao baixos se a implementacao respeitar estes pontos obrigatorios:

- preservar corretamente caminhos absolutos de SQLite;
- abortar o boot em falhas criticas de R2;
- substituir o banco apenas apos download completo e validado;
- nao fazer backup de arquivo SQLite ativo sem snapshot/checkpoint;
- adicionar testes automatizados para parsing de URL e tratamento de erros R2.

Sem esses ajustes, especialmente sem corrigir o `get_db_path()` proposto, o plano pode causar restore/backup em caminho errado e criar uma falsa sensacao de protecao.

## Recomendacao final

Implementar a correcao em duas etapas:

1. **Etapa critica imediata**: tratamento correto de `ClientError`, abortar em falhas nao-404, logs sanitizados e parsing seguro de `DATABASE_URL`.
2. **Etapa de robustez**: restore atomico com validacao SQLite, snapshot consistente no backup, limpeza segura de temporarios e testes cobrindo os cenarios de falha.

Com esses ajustes, a proposta e tecnicamente adequada e deve trazer melhoria significativa de seguranca e integridade sem oferecer risco material ao sistema ja em producao.
