# Backlog Item 8.1: Migração de Banco de Dados para PostgreSQL (Produção/Homologação)

## 1. Descrição do Problema
O SQLite é um banco de dados em arquivo local inadequado para operações simultâneas de gravação concorrentes (como múltiplos mecânicos atualizando inventários e inspeções no hangar). A migração para o PostgreSQL assíncrono (`asyncpg`) garante escalabilidade, estabilidade sob concorrência e integridade referencial nativa.

## 2. Plano de Implementação
1. **Instalar Dependências:** Adicionar `asyncpg` ao `requirements.txt`.
2. **Configuração de Variáveis de Ambiente:** Ajustar `app/bootstrap/config/__init__.py` para ler as variáveis de conexão do PostgreSQL (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`).
3. **Configuração de Múltiplos Dialetos no Alembic:** Atualizar `migrations/env.py` para rodar migrações compatíveis com SQLite (ambiente de desenvolvimento) e PostgreSQL (homologação/produção).
4. **Subir container Docker:** Configurar a imagem do PostgreSQL em `docker-compose.yml` para desenvolvimento e testes integrados.

## 3. Critérios de Aceitação
* O sistema inicializa e conecta com sucesso ao banco PostgreSQL usando `DATABASE_URL` configurada no `.env`.
* A suíte de testes passa utilizando o PostgreSQL como backend de testes em ambiente de integração.
* Transações complexas e concorrentes de movimentação de inventário finalizam com sucesso sob estresse de requisições paralelas sem deadlocks.
