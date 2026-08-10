# Workflow: Merge Main (SAA29)
ATENÇÃO: SEMPRE QUE O USUARIO PEDIR PARA FAZER O MERGE, ATRAVES DESSE WORKFLOW
PERGUNTE PARA ELE SE JA FOI REALIZADO O BACKUP MANUAL DO BANCO DE DADOS.

REPITO: SEMPRE QUE ELE SOLICITAR O MERGE, PERGUNTE PRIMEIRO SE JA FOI FEITO O BACKUP MANUAL, CASO NÃO TENHA SIDO, NÃO FAÇA O MERGE E EXPLIQUE PARA ELE QUE ELE PRECISA FAZER O BACKUP MANUAL.
CASO O USUARIO RESPONDA QUE JA FOI FEITO O BACKUP MANUAL, PROSSIGA COM O WORKFLOW.


meta:
- purpose: automated_deploy_logic
- truth: docs/methodology/merge_main.md
- trigger: "realize branch conforme merge_main.md"

steps:
1: Preparation
- git add .
- git commit -m "feat/fix: <msg>"
- git push origin <current_branch>

2: Integration (Development)
- git checkout development
- git pull origin development
- git merge <previous_branch>
- git push origin development

3: Safety Checks
- check_migrations: migrations/versions/
- check_r2: env STORAGE_BACKEND=r2
- run_tests: pytest

4: Production (Main)
- git checkout main
- git pull origin main
- git merge development
- git push origin main

post_deploy:
- monitor_deploy_logs: scripts/start.sh (R2 restore check)
- check_alembic: alembic upgrade head success
- verify_data_persistence: UI check
- vps_redeploy_instructions: "Sempre que finalizar o merge da main, forneça uma explicação rápida ao usuário e oriente a execução do comando único de redeploy na VPS:"
- vps_redeploy_command: "cd ~/saa29 && git stash && git pull origin main && docker-compose down && docker-compose up -d --build"

rules:
- NO_R2_NO_MERGE: Fail if R2 connection is suspect.
- PERSISTENCE: R2 is the off-site backup and must be healthy before merging.
- GLOBAL: Always git push after git commit.

# Nota (04/08/2026): nao ha provedor de hospedagem contratado. O Railway encerrou o plano
# gratuito; o alvo passou a ser uma VPS de entrada, com disco persistente. Por isso a regra
# PERSISTENCE foi corrigida: a antiga dizia "sqlite is ephemeral; R2 is the only truth", o que
# so valia em plataforma de filesystem efemero. Numa VPS o banco em disco e a fonte de verdade
# e o R2 e backup — mas o backup continua sendo pre-requisito de merge, agora com mais razao:
# em no unico, sem redundancia, ele e a unica copia fora do servidor.
