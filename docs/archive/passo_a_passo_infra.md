# Planejamento de Infraestrutura e Persistência – SAA29

Este documento detalha a estratégia de hospedagem, persistência e segurança de dados para o sistema SAA29, considerando o cenário de frota de 15 aeronaves, 5 usuários e baixo volume de transações (~4 panes/dia).

---

## 1. O Cenário Atual
*   **Banco de Dados:** SQLite (arquivo único `saa29_local.db`).
*   **Hospedagem Alvo:** Railway (Plano Free).
*   **Desafio:** O Railway possui sistema de arquivos efêmero (apaga tudo o que não está no Git a cada deploy ou reinício). Sem configuração extra, o banco de dados e os anexos seriam perdidos diariamente.

---

## 2. A Solução Escolhida: Cloudflare R2 + Railway Volumes
Para unir a simplicidade do SQLite com a segurança necessária para registros aeronáuticos, utilizaremos uma arquitetura híbrida:

### Por que Cloudflare R2?
*   **Custo de Saída Zero (Egress):** Diferente da AWS S3, o Cloudflare não cobra quando você baixa arquivos ou visualiza fotos.
*   **Plano Gratuito Generoso:** 10GB de armazenamento gratuito (vitalício), suficiente para o SAA29 e seus outros 3 projetos pessoais.
*   **Compatibilidade:** Usa o mesmo padrão (API S3) da Amazon, permitindo usar as mesmas ferramentas.

---

## 3. Plano de Implementação (Passo a Passo)

### Passo 1: Configuração no Cloudflare
1.  Criar uma conta no Cloudflare.
2.  Ativar o **R2 Storage** (pode exigir a inserção de um cartão para verificação, mas não haverá cobrança dentro dos 10GB).
3.  Criar um **Bucket** chamado `saa29-data`.
4.  Gerar **API Tokens** (Access Key ID e Secret Access Key) com permissão de leitura e escrita.

### Passo 2: Configuração no Railway (Persistência Local)
Para o banco de dados funcionar em tempo real, ele precisa de um disco.
1.  No painel do Railway, adicionar um **Mount (Volume/Disk)** de 1GB.
2.  Configurar o ponto de montagem para `/app/data`.
3.  No `.env` do Railway, apontar:
    ```env
    DATABASE_URL=sqlite+aiosqlite:////app/data/saa29_prod.db
    UPLOAD_DIR=/app/data/uploads
    ```

### Passo 3: Backup Automatizado com Litestream
O Litestream é a peça que garante que, se o Railway falhar, os dados estão salvos no R2.
1.  Instalar o Litestream no container (via Dockerfile).
2.  Configurá-lo para observar o arquivo `/app/data/saa29_prod.db`.
3.  Toda alteração feita no banco será replicada para o bucket `saa29-data` no R2 em milissegundos.

### Passo 4: Migração dos Anexos (Opcional, mas Recomendado)
Alterar o código do SAA29 para que os uploads de fotos e PDFs não fiquem apenas no servidor, mas sejam enviados diretamente para o R2.
*   Isso economiza espaço no volume do Railway.
*   Torna os anexos permanentes, mesmo que você decida deletar o volume do Railway no futuro.

---

## 4. Estratégia Multi-Projeto
Como você possui outros 3 projetos em SQLite, você pode reutilizar o Cloudflare R2:
*   Crie pastas dentro do mesmo bucket (ex: `/projeto2`, `/projeto3`) ou buckets separados.
*   Configure o Litestream em cada um desses projetos apontando para sua respectiva pasta no R2.
*   **Resultado:** Todos os seus bancos de dados estarão protegidos centralizadamente sob o limite de 10GB do Cloudflare.

---

## 5. Próximas Ações Técnicas
1.  **Ajustar Dockerfile:** Incluir a instalação do binário do Litestream.
2.  **Criar `litestream.yml`:** Arquivo de configuração que define o destino do backup (R2).
3.  **Refatorar `app/panes/service.py`:** Adicionar suporte a `boto3` (biblioteca S3) para uploads no R2 se as chaves estiverem presentes no `.env`.

---
*Documento gerado em 14 de abril de 2026 como guia de infraestrutura para o projeto SAA29.*
